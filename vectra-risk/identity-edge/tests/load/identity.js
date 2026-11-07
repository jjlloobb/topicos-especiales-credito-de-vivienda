// Prueba de carga de U2 `identity-edge` (U02-T15, Paso 14 del plan; NFR-U2-10..12). La ejecuta el operador en el Paso 16.
//
//   users          200 usuarios `load-001..200`: login del navegador de `vectra-console` (PKCE S256) y renovacion del token.
//   services       10 clientes de servicio: `client_credentials` con `private_key_jwt` ES256 cada 300 s.
//   jwks           lecturas del JWKS del realm.
//   console-burst  rafagas de un mismo usuario contra /api/console/** (el eco del Paso 13): por encima de 20/s, 429 con Retry-After: 1.
//   overhead       el mismo request al eco, por el gateway y directo; NFR-U2-11 se evalua en `handleSummary` (J3).
//
// El init context no exige variables de entorno (`k6 inspect` corre sin ellas): los valores por defecto no sirven para ejecutar y
// la falta de una variable se comprueba en `setup()`. Las variables y el uso estan en README.md.
import encoding from 'k6/encoding';
import exec from 'k6/execution';
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

// --- el diseno --------------------------------------------------------------------------------------------------------------
const USERS = 200; // NFR-U2-10
const USER_PREFIX = 'load-'; // J1: load-001..200
const USER_FIRST = 1;
const USER_LAST = USER_FIRST + USERS - 1;
const RAMP_S = 120; // J7: 2 min de subida
const SUSTAIN_S = 900; // J7: 15 min sostenidos
const RENEW_S = 300; // NFR-U2-10: las identidades de servicio renuevan cada 5 min
// J6: los 14 clientes con service account de realm.kind.yaml, menos keycloak-config-cli, keycloak-reader, verification-reader y channel-simulator.
const SERVICE_CLIENTS = [
  'case-service',
  'case-worker',
  'scoring-service',
  'explainability-service',
  'governance-service',
  'bias-monitoring-service',
  'bias-monitoring-job',
  'model-validation-job',
  'product-metrics',
  'channel',
];
const BASE_RATE = 5; // req/s de la consola entre rafagas (por debajo del limite de 20/s por `sub`)
const BURST_RATE = 40; // req/s de la rafaga: por encima del limite de la consola (routes.yaml)
const BURST_EVERY_S = 30; // una rafaga de 10 s cada 30 s
const JWKS_RATE = 20; // lecturas/s
const OVERHEAD_RATE = 5; // pares gateway+directo por segundo, por debajo del limite de la consola
const OVERHEAD_P95_BUDGET_MS = 5; // NFR-U2-11
const USER_RENEW_S = 60; // el token de acceso dura 300 s (BR-U2-06); el limite de /auth/** de token es de 10/s por IP

// --- entorno (sin exigirlo en el init context) ------------------------------------------------------------------------------
const NOT_SET = 'https://no-configurado.invalid';
const BASE_URL = (__ENV.K6_BASE_URL || NOT_SET).replace(/\/+$/, '');
const ECHO_DIRECT_URL = (__ENV.K6_ECHO_DIRECT_URL || NOT_SET).replace(/\/+$/, '');
const KEYS_DIR = __ENV.K6_CLIENT_KEYS_DIR || '';
const LOAD_PASSWORD = __ENV.K6_LOAD_PASSWORD || '';
const REQUIRED_ENV = ['K6_BASE_URL', 'K6_ECHO_DIRECT_URL', 'K6_CLIENT_KEYS_DIR', 'K6_LOAD_PASSWORD'];

// Una llave PEM (PKCS#8) por cliente; solo se leen si el operador fijo K6_CLIENT_KEYS_DIR (J6).
const KEYS = {};
if (KEYS_DIR) {
  for (const client of SERVICE_CLIENTS) {
    KEYS[client] = open(`${KEYS_DIR}/${client}.pem`);
  }
}

const OIDC = '/auth/realms/vectra/protocol/openid-connect';
const CONSOLE_PATH = '/api/console/v1/load';
const OVERHEAD_PATH = '/api/console/v1/overhead';
// El redirect URI de `vectra-console` registrado en el realm es `https://<PUBLIC_HOSTNAME>/callback`: sin puerto, sin ruta y siempre https,
// aunque K6_BASE_URL lleve un puerto (port-forward) o sea http. El script nunca lo sigue: solo tiene que coincidir con el registrado.
const PUBLIC_ORIGIN = `https://${BASE_URL.replace(/^https?:\/\//, '').replace(/[:/].*$/, '')}`;
const REDIRECT_URI = `${PUBLIC_ORIGIN}/callback`;

const consoleOk = new Counter('console_ok');
const consoleRateLimited = new Counter('console_rate_limited');

// --- opciones ---------------------------------------------------------------------------------------------------------------
function burstStages() {
  // Cada ciclo: 19 s a la tasa base, 1 s de subida, 9 s de rafaga y 1 s de bajada; suma BURST_EVERY_S. El primer ciclo empieza en calma.
  const stages = [];
  for (let t = 0; t < RAMP_S + SUSTAIN_S; t += BURST_EVERY_S) {
    stages.push({ duration: `${BURST_EVERY_S - 11}s`, target: BASE_RATE });
    stages.push({ duration: '1s', target: BURST_RATE });
    stages.push({ duration: '9s', target: BURST_RATE });
    stages.push({ duration: '1s', target: BASE_RATE });
  }
  return stages;
}

export const options = {
  scenarios: {
    users: {
      executor: 'ramping-vus',
      exec: 'usersFlow',
      startVUs: 0,
      // Cada VU hace un solo login (sube a 200 VUs en RAMP_S): 200/120 = 1.7 logins/s, por debajo de 10/s (J5).
      stages: [
        { duration: `${RAMP_S}s`, target: USERS },
        { duration: `${SUSTAIN_S}s`, target: USERS },
      ],
      gracefulRampDown: '0s',
      // Los usuarios de `usersFlow` salen de este env (no de las constantes); el env sale de las constantes del diseno.
      env: { USER_PREFIX, USER_FIRST: String(USER_FIRST), USER_LAST: String(USER_LAST) },
    },
    services: {
      executor: 'constant-arrival-rate',
      exec: 'servicesFlow',
      rate: SERVICE_CLIENTS.length,
      timeUnit: `${RENEW_S}s`,
      duration: `${RAMP_S + SUSTAIN_S}s`,
      preAllocatedVUs: SERVICE_CLIENTS.length,
      maxVUs: 2 * SERVICE_CLIENTS.length,
      env: { CLIENTS: SERVICE_CLIENTS.join(',') },
    },
    jwks: {
      executor: 'constant-arrival-rate',
      exec: 'jwksFlow',
      rate: JWKS_RATE,
      timeUnit: '1s',
      duration: `${RAMP_S + SUSTAIN_S}s`,
      preAllocatedVUs: 5,
      maxVUs: 20,
    },
    'console-burst': {
      executor: 'ramping-arrival-rate',
      exec: 'burstFlow',
      startRate: BASE_RATE,
      timeUnit: '1s',
      stages: burstStages(),
      preAllocatedVUs: 5,
      maxVUs: 15,
      env: { RETRY_AFTER: '1' },
    },
    overhead: {
      executor: 'constant-arrival-rate',
      exec: 'overheadFlow',
      rate: OVERHEAD_RATE,
      timeUnit: '1s',
      duration: `${RAMP_S + SUSTAIN_S}s`,
      preAllocatedVUs: 3,
      maxVUs: 10,
      // `handleSummary` lee el presupuesto de aqui (`exec.test.options`), asi que lo que valida `load_checks` es lo que decide.
      env: { MAX_DIFF_P95_MS: String(OVERHEAD_P95_BUDGET_MS) },
    },
  },
  thresholds: {
    'http_req_duration{flow:login}': ['p(95)<500'], // NFR-U2-10
    'http_req_duration{flow:token}': ['p(95)<200'], // NFR-U2-10
    'http_req_duration{flow:jwks}': ['p(95)<50'], // NFR-U2-10
    http_req_failed: ['rate<0.01'], // J7; un 429 de los logins cuenta como fallo (J5)
    checks: ['rate>0.99'], // 1 - la tolerancia de J7: las comprobaciones de J4 y J5 (429 de login, Retry-After) fallan la corrida
    // Sin un umbral, k6 no entrega estas submetricas a `handleSummary`. Este no restringe nada: NFR-U2-11 se evalua alli (J3).
    'http_req_duration{leg:gateway}': ['max>=0'],
    'http_req_duration{leg:direct}': ['max>=0'],
  },
};

// --- sesion de usuario (por VU) ---------------------------------------------------------------------------------------------
function randomUrlSafe(bytes) {
  const buffer = new Uint8Array(bytes);
  crypto.getRandomValues(buffer);
  return encoding.b64encode(buffer.buffer, 'rawurl');
}

function userName(index, prefix = USER_PREFIX) {
  return `${prefix}${String(index).padStart(3, '0')}`;
}

function unescapeHtml(text) {
  return text.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#x3D;/g, '=').replace(/&#61;/g, '=');
}

function formAction(html) {
  const found = /<form[^>]*\saction="([^"]*login-actions[^"]*)"/.exec(html);
  return found ? unescapeHtml(found[1]) : null;
}

function hiddenFields(html) {
  const fields = {};
  for (const tag of html.match(/<input[^>]*>/g) || []) {
    const name = /name="([^"]+)"/.exec(tag);
    if (/type="hidden"/.test(tag) && name) {
      const value = /value="([^"]*)"/.exec(tag);
      fields[name[1]] = value ? unescapeHtml(value[1]) : '';
    }
  }
  return fields;
}

function tokenSession(body) {
  const renewIn = Math.max(10, Number(body.expires_in || 300) - 60);
  return { accessToken: body.access_token, refreshToken: body.refresh_token, renewAt: Date.now() + renewIn * 1000 };
}

// El login del navegador de vectra-console: GET de autorizacion, POST de la contrasena y canje del codigo (PKCE S256).
async function login(username) {
  // Un jar nuevo por login: Keycloak deja la cookie SSO en `/auth/realms/vectra/` y `clear(BASE_URL)` (ruta `/`) no la borra, con lo que
  // el segundo login del VU entraria solo y el GET de autorizacion respondería 302 en vez del formulario.
  const jar = new http.CookieJar();
  const verifier = randomUrlSafe(48);
  const challenge = encoding.b64encode(
    await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)),
    'rawurl',
  );
  const query = {
    client_id: 'vectra-console',
    redirect_uri: REDIRECT_URI,
    response_type: 'code',
    scope: 'openid',
    state: randomUrlSafe(12),
    nonce: randomUrlSafe(12),
    code_challenge: challenge,
    code_challenge_method: 'S256',
  };
  const qs = Object.keys(query).map((k) => `${k}=${encodeURIComponent(query[k])}`).join('&');
  const page = http.get(`${BASE_URL}${OIDC}/auth?${qs}`, {
    redirects: 0,
    jar,
    tags: { flow: 'login', name: 'GET auth' },
  });
  const action = page.status === 200 ? formAction(page.body) : null;
  if (!check(page, { 'login: formulario de contrasena': () => action !== null })) return null;

  const posted = http.post(action, { ...hiddenFields(page.body), username, password: LOAD_PASSWORD }, {
    redirects: 0,
    jar,
    tags: { flow: 'login', name: 'POST login-actions' },
  });
  const location = posted.headers.Location || '';
  const code = location.startsWith(REDIRECT_URI) ? /[?&]code=([^&]+)/.exec(location) : null;
  if (!check(posted, { 'login: redireccion con codigo': () => code !== null })) return null;

  const exchanged = http.post(`${BASE_URL}${OIDC}/token`, {
    grant_type: 'authorization_code',
    client_id: 'vectra-console',
    code: decodeURIComponent(code[1]),
    redirect_uri: REDIRECT_URI,
    code_verifier: verifier,
  }, { tags: { flow: 'token', name: 'POST token authorization_code' } });
  if (!check(exchanged, { 'token: canje del codigo 200': (r) => r.status === 200 })) return null;
  return tokenSession(exchanged.json());
}

function refresh(session) {
  const renewed = http.post(`${BASE_URL}${OIDC}/token`, {
    grant_type: 'refresh_token',
    client_id: 'vectra-console',
    refresh_token: session.refreshToken,
  }, { tags: { flow: 'token', name: 'POST token refresh_token' } });
  if (!check(renewed, { 'token: renovacion 200': (r) => r.status === 200 })) return null;
  return tokenSession(renewed.json());
}

const sessions = {}; // por VU: el contexto de un VU persiste entre iteraciones
const retryNotBefore = {}; // por VU y usuario: hasta cuando no se vuelve a intentar un login que acaba de fallar
const LOGIN_BACKOFF_S = 30; // un login son 3 peticiones y /auth/** admite 10/s por IP: sin espera, un 5xx pasajero agota el limite

// El token vigente de `username`: lo renueva con el refresh token y, si eso falla, vuelve a hacer login. Si el login tambien falla,
// no vuelve a intentarlo hasta pasados LOGIN_BACKOFF_S (mientras tanto devuelve null sin tocar la red).
async function accessToken(username) {
  const current = sessions[username];
  if (current && Date.now() < current.renewAt) return current.accessToken;
  if (Date.now() < (retryNotBefore[username] || 0)) return null;
  const next = (current ? refresh(current) : null) || (await login(username));
  sessions[username] = next;
  if (!next) retryNotBefore[username] = Date.now() + LOGIN_BACKOFF_S * 1000;
  return next ? next.accessToken : null;
}

// --- escenarios -------------------------------------------------------------------------------------------------------------
// Cada VU del escenario hace una sola iteracion larga: la que ocupa el lugar N en `iterationInInstance` es el usuario USER_FIRST+N.
// (`exec.vu.idInInstance` cuenta los VU de todos los escenarios, asi que no sirve para numerar usuarios.) Hace un solo login y despues
// solo renueva el token cada USER_RENEW_S; tras un fallo espera otra renovacion entera antes de reintentar.
export async function usersFlow() {
  const prefix = __ENV.USER_PREFIX;
  const first = Number(__ENV.USER_FIRST);
  const count = Number(__ENV.USER_LAST) - first + 1;
  const index = exec.scenario.iterationInInstance;
  const endsAt = exec.scenario.startTime + (RAMP_S + SUSTAIN_S) * 1000;
  if (index >= count) {
    sleep(Math.max(0, (endsAt - Date.now()) / 1000)); // un VU que reinicia no es un usuario nuevo
    return;
  }
  const username = userName(first + index, prefix);
  let session = await login(username);
  while (Date.now() < endsAt) {
    sleep(Math.min(USER_RENEW_S, Math.max(0, (endsAt - Date.now()) / 1000)));
    if (Date.now() >= endsAt) break;
    session = session ? refresh(session) : await login(username);
  }
}

function pemToDer(pem) {
  if (!/-----BEGIN PRIVATE KEY-----/.test(pem)) {
    throw new Error('la llave debe ser PKCS#8 ("BEGIN PRIVATE KEY"); convertirla con: openssl pkcs8 -topk8 -nocrypt');
  }
  return encoding.b64decode(pem.replace(/-----[A-Z ]+-----/g, '').replace(/\s+/g, ''), 'std');
}

const signingKeys = {}; // por VU

async function clientAssertion(client) {
  if (!signingKeys[client]) {
    signingKeys[client] = await crypto.subtle.importKey(
      'pkcs8', pemToDer(KEYS[client]), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign'],
    );
  }
  const b64 = (value) => encoding.b64encode(JSON.stringify(value), 'rawurl');
  const now = Math.floor(Date.now() / 1000);
  // El `aud` es el issuer publico del realm (el mismo origen que el redirect URI), no el `K6_BASE_URL` del port-forward, que lleva puerto.
  const url = `${PUBLIC_ORIGIN}${OIDC}/token`;
  const signingInput = `${b64({ alg: 'ES256', typ: 'JWT' })}.${b64({
    iss: client, sub: client, aud: url, jti: randomUrlSafe(16), iat: now, exp: now + 60,
  })}`;
  // WebCrypto entrega ECDSA como r||s de 64 bytes, que es la firma de JWS para ES256.
  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' }, signingKeys[client], new TextEncoder().encode(signingInput),
  );
  return `${signingInput}.${encoding.b64encode(signature, 'rawurl')}`;
}

export async function servicesFlow() {
  const clients = __ENV.CLIENTS.split(',');
  const client = clients[exec.scenario.iterationInInstance % clients.length];
  const response = http.post(`${BASE_URL}${OIDC}/token`, {
    grant_type: 'client_credentials',
    client_id: client,
    client_assertion_type: 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
    client_assertion: await clientAssertion(client),
  }, { tags: { flow: 'token', name: 'POST token client_credentials', client } });
  check(response, {
    'servicio: token 200': (r) => r.status === 200,
    'servicio: trae access_token': (r) => r.status === 200 && Boolean(r.json('access_token')),
  });
}

export function jwksFlow() {
  const response = http.get(`${BASE_URL}${OIDC}/certs`, { tags: { flow: 'jwks', name: 'GET certs' } });
  check(response, {
    'jwks: 200': (r) => r.status === 200,
    'jwks: trae llaves': (r) => r.status === 200 && r.json('keys.#') !== 0,
  });
}

export async function burstFlow() {
  const token = await accessToken(userName(USER_FIRST));
  if (!check(token, { 'consola: hay token': (t) => t !== null })) return;
  const response = http.get(`${BASE_URL}${CONSOLE_PATH}`, {
    headers: { Authorization: `Bearer ${token}` },
    tags: { flow: 'console', name: 'GET /api/console' },
    // Por encima del limite el 429 es lo esperado: no cuenta como fallo de http_req_failed.
    responseCallback: http.expectedStatuses(200, 429),
  });
  if (response.status === 429) consoleRateLimited.add(1);
  else if (response.status === 200) consoleOk.add(1);
  check(response, {
    'consola: 200 o 429': (r) => r.status === 200 || r.status === 429,
    'consola: el 429 trae Retry-After': (r) => r.status !== 429 || r.headers['Retry-After'] === __ENV.RETRY_AFTER,
    'consola: el 429 es rate_limited': (r) => r.status !== 429 || r.json('code') === 'rate_limited',
  });
}

export async function overheadFlow() {
  const token = await accessToken(userName(USER_FIRST + 1));
  if (!check(token, { 'overhead: hay token': (t) => t !== null })) return;
  const headers = { Authorization: `Bearer ${token}` };
  const legs = [
    ['gateway', `${BASE_URL}${OVERHEAD_PATH}`],
    ['direct', `${ECHO_DIRECT_URL}${OVERHEAD_PATH}`],
  ];
  // El orden alterna para que ninguno de los dos extremos herede siempre la conexion recien abierta.
  if (exec.scenario.iterationInInstance % 2 === 1) legs.reverse();
  for (const [leg, url] of legs) {
    const response = http.get(url, { headers, tags: { flow: 'overhead', leg, name: `GET overhead ${leg}` } });
    check(response, { [`overhead ${leg}: 200`]: (r) => r.status === 200 });
  }
}

// --- setup y resumen --------------------------------------------------------------------------------------------------------
export function setup() {
  const missing = REQUIRED_ENV.filter((name) => !__ENV[name]);
  if (missing.length > 0) {
    throw new Error(`faltan variables de entorno: ${missing.join(', ')} (ver identity-edge/tests/load/README.md)`);
  }
  const noKey = SERVICE_CLIENTS.filter((client) => !KEYS[client]);
  if (noKey.length > 0) {
    throw new Error(`faltan llaves en K6_CLIENT_KEYS_DIR para: ${noKey.join(', ')}`);
  }
}

// NFR-U2-11 (J3): el umbral se aplica a la diferencia de los p95 con y sin gateway. k6 no puede expresar ese umbral como `thresholds`.
// En k6 v2.3.0 un error en `handleSummary` no cambia el codigo de salida (queda en 0): el veredicto va a `overhead-verdict.json`
// y `make -C identity-edge load` sale con error si no se cumple.
export function handleSummary(data) {
  const p95 = (name) => (data.metrics[name] && data.metrics[name].values ? data.metrics[name].values['p(95)'] : NaN);
  const gateway = p95('http_req_duration{leg:gateway}');
  const direct = p95('http_req_duration{leg:direct}');
  const diff = gateway - direct;
  // El presupuesto es el que lleva el escenario `overhead` (el que valida `load_checks`); si falta, NaN y el veredicto falla.
  const budget = Number(exec.test.options.scenarios.overhead.env.MAX_DIFF_P95_MS);
  const limited = data.metrics.console_rate_limited ? data.metrics.console_rate_limited.values.count : 0;
  const verdict = {
    overhead: {
      gateway_p95_ms: gateway,
      direct_p95_ms: direct,
      diff_p95_ms: diff,
      budget_ms: budget,
      ok: Number.isFinite(diff) && diff <= budget,
    },
    console: { rate_limited: limited, ok: limited > 0 },
  };
  const lines = ['', 'identity.js: resumen'];
  for (const name of Object.keys(data.metrics)) {
    for (const expression of Object.keys(data.metrics[name].thresholds || {})) {
      lines.push(`  umbral ${name} ${expression}: ${data.metrics[name].thresholds[expression].ok ? 'OK' : 'FALLA'}`);
    }
  }
  lines.push(
    `  NFR-U2-11 sobrecosto p95 gateway ${gateway} ms - directo ${direct} ms = ${diff} ms (maximo ${budget} ms): ${verdict.overhead.ok ? 'OK' : 'FALLA'}`,
    `  consola: ${limited} respuestas 429 en las rafagas: ${verdict.console.ok ? 'OK' : 'FALLA'}`,
    '',
  );
  if (!verdict.overhead.ok || !verdict.console.ok) console.error('identity.js: el veredicto de handleSummary FALLA');
  return {
    stdout: lines.join('\n'),
    'summary.json': JSON.stringify(data, null, 2),
    'overhead-verdict.json': JSON.stringify(verdict, null, 2),
  };
}

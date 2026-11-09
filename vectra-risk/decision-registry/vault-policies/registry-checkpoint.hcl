# registry-checkpoint: firma los checkpoints cada hora (BR-U3-08) y lee la llave publica.
# Sin comodines (P-U3-08, NFR-U3-40): solo la llave de checkpoints, y solo lo que esta identidad necesita.
path "transit/sign/registry-checkpoints" {
  capabilities = ["update"]
}

path "transit/keys/registry-checkpoints" {
  capabilities = ["read"]
}

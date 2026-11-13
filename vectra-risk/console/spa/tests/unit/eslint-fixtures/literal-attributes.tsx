export const Attributes = ({ text }: { text: string }) => (
  <div id="panel" role="region" aria-labelledby="panel-title">
    <h2 id="panel-title">{text}</h2>
    <label htmlFor="campo">
      {text}
      <input id="campo" type="text" />
    </label>
    <a href="/ruta">{text}</a>
  </div>
);

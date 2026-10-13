/* Receptor del contrato, ejercitado desde tests/test_motor.py.

   Lee por stdin una lista de casos, cada uno con los mensajes que mandaria la
   pagina, y escribe por stdout lo que el motor entendio. Cada caso usa una
   copia fresca del motor, porque su estado de entrada es de modulo. */

'use strict';

const path = require('path');
const ENGINE = path.resolve(__dirname, '..', '..', 'assets', 'games', 'engine.js');

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  const casos = JSON.parse(raw);
  const salida = casos.map((caso) => {
    delete require.cache[ENGINE];
    const E = require(ENGINE);
    // Antes del umbral del modo autonomo: se esta dentro de la aplicacion.
    const ahora = 100;
    const aceptados = caso.mensajes.map((m) => E.receive(m, ahora));
    return {
      aceptados,
      signal: Number.isNaN(E.input.signal) ? null : E.input.signal,
      ready: E.isReady(ahora),
      simulated: E.input.simulated,
      theme: E.input.theme,
    };
  });
  process.stdout.write(JSON.stringify(salida));
});

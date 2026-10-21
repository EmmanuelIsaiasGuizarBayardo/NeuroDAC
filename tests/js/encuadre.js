/* Encuadre de los juegos, ejercitado desde tests/test_motor.py.

   Para muchas combinaciones de espacio y densidad de pantalla verifica que el
   area quepa, que el factor sea el maximo, que la proporcion sea exacta y que
   el presentador del motor, al medir ese tamano, elija el mismo factor sin
   dejar franjas. Escribe las fallas por stdout y sale con 1 si hay alguna. */

'use strict';

const path = require('path');
const { encuadre, encuadreAncho } = require(path.resolve(__dirname, '..', '..', 'assets', 'encuadre.js'));
const E = require(path.resolve(__dirname, '..', '..', 'assets', 'games', 'engine.js'));

const fallas = [];
let casos = 0;
const RESOLUCIONES = [[240, 180], [144, 192]]; // Jardin 4:3 y Carrera 3:4
const DENSIDADES = [1, 1.25, 1.5, 1.75, 2, 2.5, 3];

for (const [lw, lh] of RESOLUCIONES) {
  for (const dpr of DENSIDADES) {
    for (let availW = 200; availW <= 1600; availW += 37) {
      for (let availH = 150; availH <= 1100; availH += 41) {
        casos++;
        const r = encuadre(availW, availH, dpr, lw, lh);
        const s = r.scale;
        const etiqueta = `${lw}x${lh} dpr ${dpr} espacio ${availW}x${availH}`;
        const cabe = availW * dpr >= lw * s && availH * dpr >= lh * s;
        const otroCabe = availW * dpr >= lw * (s + 1) && availH * dpr >= lh * (s + 1);
        if (s > 1 && !cabe) fallas.push(`${etiqueta}: no cabe con factor ${s}`);
        if (otroCabe) fallas.push(`${etiqueta}: el factor ${s} no es el maximo`);
        if (Math.abs(r.width / r.height - lw / lh) > 1e-9) fallas.push(`${etiqueta}: proporcion`);

        // El lienzo mide floor(css * dpr); el navegador puede quedarse un
        // pixel de dispositivo corto. En ambos casos, mismo factor y sin resto.
        for (const corto of [0, 1]) {
          const cw = Math.floor(r.width * dpr) - corto;
          const ch = Math.floor(r.height * dpr) - corto;
          const sm = E.integerScale(cw, ch, lw, lh);
          if (sm !== s) fallas.push(`${etiqueta} (corto ${corto}): el motor elige ${sm}, no ${s}`);
          const restoW = cw - lw * sm;
          const restoH = ch - lh * sm;
          if (restoW > 1 || restoH > 1) {
            fallas.push(`${etiqueta} (corto ${corto}): queda franja de ${restoW}x${restoH}`);
          }
        }
      }
    }
  }
}

/* Modo que llena el ancho: Jardin, de 240 a 360 columnas con alto 180. */
const MIN_W = 240;
const MAX_W = 360;
const LH = 180;
for (const dpr of DENSIDADES) {
  for (let availW = 200; availW <= 1900; availW += 23) {
    for (let availH = 120; availH <= 1200; availH += 53) {
      casos++;
      const r = encuadreAncho(availW, availH, dpr, MIN_W, MAX_W, LH);
      const s = r.scale;
      const et = `ancho dpr ${dpr} espacio ${availW}x${availH}`;
      // Con menos de MIN_W pixeles de dispositivo no hay escalado entero que
      // quepa: ese dominio es imposible y no se exige.
      const posible = availW * dpr >= MIN_W;
      if (posible && r.width > availW + 1e-9) fallas.push(`${et}: se sale a lo ancho`);
      if (s > 1 && LH * s > availH * dpr) fallas.push(`${et}: no cabe en la pantalla con factor ${s}`);
      // Llena el ancho salvo cuando topa con el maximo de columnas.
      if (r.lw < MAX_W && availW * dpr - r.lw * s >= s) {
        fallas.push(`${et}: sobran ${(availW * dpr - r.lw * s).toFixed(0)} px de dispositivo a lo ancho`);
      }
      // El factor solo baja si de verdad no cabe a lo alto.
      const porAncho = Math.max(1, Math.floor((availW * dpr) / MIN_W));
      if (s < porAncho && LH * (s + 1) <= availH * dpr) fallas.push(`${et}: bajo el factor sin necesidad`);
      for (const corto of [0, 1]) {
        const cw = Math.floor(r.width * dpr) - corto;
        const ch = Math.floor(r.height * dpr) - corto;
        const m = E.fitWidth(cw, ch, MIN_W, MAX_W, LH);
        // Mismo factor siempre. Las columnas pueden diferir en una: a factor
        // bajo, un pixel corto es literalmente una columna menos, y el juego
        // la llena exacta. Lo que no se admite es una franja visible.
        if (m.scale !== s || Math.abs(m.w - r.lw) > 1) {
          fallas.push(`${et} (corto ${corto}): el motor elige ${m.w}x${m.scale}, no ${r.lw}x${s}`);
        }
        if (posible && (Math.abs(cw - m.w * m.scale) > 2 || Math.abs(ch - LH * m.scale) > 2)) {
          fallas.push(`${et} (corto ${corto}): franja de ${cw - m.w * m.scale}x${ch - LH * m.scale}`);
        }
      }
    }
  }
}

console.log(`${casos} combinaciones`);
if (fallas.length) {
  console.log('FALLA');
  for (const f of fallas.slice(0, 15)) console.log('  - ' + f);
  if (fallas.length > 15) console.log(`  ... y ${fallas.length - 15} mas`);
  process.exitCode = 1;
} else {
  console.log('OK');
}

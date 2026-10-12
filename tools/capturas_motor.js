/* Renderiza una escena de prueba del motor sin navegador y la vuelca a PNG.

   Uso:
       node tools/capturas_motor.js [carpeta_salida]

   La salida por defecto es results/capturas, que el .gitignore ya excluye.

   Valida, ademas de producir las capturas, que ningun pixel del cuadro final
   salga de la paleta. Las entradas sin usar de la paleta PNG se pintan de
   magenta: si aparece magenta en una captura, algo se salio. */

'use strict';

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const E = require('../assets/games/engine.js');
const { SPEC, PETAL_RAMPS } = require('../assets/games/palette.js');

const OUT = process.argv[2] || path.join('results', 'capturas');
const W = 240;
const H = 180;
const SCALE = 4;

/* ------------------------------------------------------------------ PNG */

const CRC_TABLE = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 255] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

/** PNG de color indexado; las entradas fuera de la paleta van en magenta. */
function writePNG(file, w, h, idx, rgb, count) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 3;

  const plte = Buffer.alloc(256 * 3);
  for (let i = 0; i < 256; i++) {
    if (i < count) {
      plte[i * 3] = rgb[i * 3];
      plte[i * 3 + 1] = rgb[i * 3 + 1];
      plte[i * 3 + 2] = rgb[i * 3 + 2];
    } else {
      plte[i * 3] = 255;
      plte[i * 3 + 1] = 0;
      plte[i * 3 + 2] = 255;
    }
  }

  const raw = Buffer.alloc((w + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w + 1)] = 0;
    for (let x = 0; x < w; x++) raw[y * (w + 1) + 1 + x] = idx[y * w + x];
  }

  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('PLTE', plte),
    chunk('IDAT', zlib.deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
  fs.writeFileSync(file, png);
}

function upscale(src, w, h, s) {
  const out = new Uint8Array(w * s * h * s);
  for (let y = 0; y < h * s; y++) {
    const sy = (y / s) | 0;
    for (let x = 0; x < w * s; x++) out[y * w * s + x] = src[sy * w + ((x / s) | 0)];
  }
  return out;
}

/* ---------------------------------------------------------------- escena */

const pal = E.createPalette(SPEC);
const R = pal.ramps;
const INK = R.ink[0];
const WHITE = R.white[0];

// Materiales: se crean una sola vez, nunca dentro de un bucle de pixeles.
const MAT = {
  stem: E.material(R.foliage, { baseTone: 1 }),
  leaf: E.material(R.foliage),
  center: E.material(R.orange, { spec: 0.08, specIndex: R.petalGold[2] }),
  bubble: E.material(R.celeste, { spec: 0.1, specIndex: WHITE }),
  ridgeFar: E.material(R.sky, { baseTone: 1 }),
  ridgeNear: E.material(R.sky, { baseTone: 2 }),
  petals: PETAL_RAMPS.map((name) => E.material(R[name], { spec: 0.025, specIndex: WHITE })),
};

const frame = E.createFrame(W, H, INK);
const SPR_W = 44;
const SPR_H = 84;
const sprite = E.createFrame(SPR_W, SPR_H);
const scratch = new Uint8Array(SPR_W * SPR_H);

function drawSky(f) {
  const horizon = 118;
  for (let y = 0; y < horizon; y++) {
    // Oscuro arriba, calido hacia el horizonte: un crepusculo.
    const value = (y / horizon) * (R.sky.length - 1);
    for (let x = 0; x < f.w; x++) f.px[y * f.w + x] = E.ditherTone(R.sky, value, x, y);
  }
}

function drawRidges(f) {
  // Siluetas lejanas en tonos de cielo: profundidad sin salir de la rampa.
  E.triangle(f, MAT.ridgeFar, 50, -20, 126, 70, 64, 140, 126);
  // Mismo identificador que la anterior: el contorno interior separa piezas
  // de primer plano, pero en el fondo marcaria una grieta entre montanas.
  E.triangle(f, MAT.ridgeNear, 50, 90, 126, 150, 80, 220, 126);
}

function drawGround(f) {
  for (let y = 118; y < f.h - 6; y++) {
    const value = 2 - ((y - 118) / (f.h - 124)) * 2;
    for (let x = 0; x < f.w; x++) {
      // Borde ondulado del terreno, hecho con la misma funcion que el tramado.
      const edge = 118 + Math.round(Math.sin(x * 0.07) * 2);
      if (y < edge) continue;
      // Dos filas de pasto en el borde: el suelo se lee como jardin.
      f.px[y * f.w + x] =
        y - edge < 2 ? R.foliage[y - edge] : E.ditherTone(R.soil, value, x, y);
    }
  }
}

function drawFlower(spr, species, sway, stage) {
  E.clearFrame(spr, E.TRANSPARENT);
  const baseX = SPR_W / 2;
  const baseY = SPR_H - 4;
  const topX = baseX + sway;
  const topY = baseY - 24 - stage * 8;

  E.capsule(spr, MAT.stem, 1, baseX, baseY, 2.0, topX, topY, 1.4);
  const midY = (baseY + topY) / 2;
  E.ellipse(spr, MAT.leaf, 2, baseX - 6, midY + 4, 6, 2.6, -0.5);
  E.ellipse(spr, MAT.leaf, 3, baseX + 6 + sway * 0.4, midY - 4, 6, 2.6, 0.55);

  const petals = 7;
  for (let i = 0; i < petals; i++) {
    const a = (i / petals) * Math.PI * 2;
    E.ellipse(
      spr, MAT.petals[species], 4 + i,
      topX + Math.cos(a) * 7, topY + Math.sin(a) * 7, 6, 3.4, a
    );
  }
  E.ellipse(spr, MAT.center, 20, topX, topY, 4.2, 4.2, 0);
  E.selOut(spr, pal, INK, scratch);
}

function drawPollen(f) {
  // Anillo hueco con brillo: una bolita rellena se leeria como solida.
  E.ring(f, MAT.bubble, 30, 200, 40, 6, 6, 2);
  E.pixel(f, 197, 37, WHITE);
  E.ring(f, MAT.bubble, 31, 214, 58, 3.5, 3.5, 1.6);
  for (let i = 0; i < 18; i++) {
    const x = 150 + ((i * 37) % 80);
    const y = 20 + ((i * 53) % 60);
    if (E.bayer(x, y) < 0.6) E.pixel(f, x, y, R.petalGold[2]);
  }
}

function drawLabels(f) {
  E.text(f, 'MEDITACI\u00D3N', 7, 9, INK);
  E.text(f, 'MEDITACI\u00D3N', 6, 8, R.paint[1]);
  E.number(f, 72, 6 + E.textWidth('MEDITACI\u00D3N ') + 1, 8, R.orange[2]);
  E.text(f, '\u00A1LISTA! \u00BFA\u00DAN? \u00D1AND\u00DA 4/10 %', 6, 18, R.paint[1]);
  E.text(f, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789', 6, 26, R.petalWhite[2]);
}

function drawSwatches(f) {
  const w = (f.w / pal.count) | 0;
  for (let i = 0; i < pal.count; i++) E.rect(f, i * w, f.h - 5, w, 5, i);
}

function render(theme) {
  E.clearFrame(frame, INK);
  drawSky(frame);
  drawRidges(frame);
  drawGround(frame);

  for (let s = 0; s < PETAL_RAMPS.length; s++) {
    drawFlower(sprite, s, (s - 2) * 2, Math.min(4, s + 1));
    E.blit(frame, sprite, 2 + s * 46, 118 - SPR_H + 10);
  }

  drawPollen(frame);
  drawLabels(frame);
  drawSwatches(frame);
  return pal.rgb[theme];
}

/* ------------------------------------------------------------- validacion */

module.exports = { render, frame, pal };

// Solo valida y escribe capturas cuando se ejecuta directo, no al importarse.
if (require.main === module) {

  fs.mkdirSync(OUT, { recursive: true });
  const seen = new Uint8Array(256);
  const report = [];

  for (const theme of ['dark', 'light']) {
    const rgb = render(theme);
    const distinct = E.countColors(frame, seen);
    let outside = 0;
    for (let i = 0; i < frame.px.length; i++) if (frame.px[i] >= pal.count) outside++;

    writePNG(
      path.join(OUT, `motor_${theme}.png`),
      W * SCALE, H * SCALE, upscale(frame.px, W, H, SCALE), rgb, pal.count
    );
    report.push({ theme, distinct, outside });
  }

  // Acercamiento 1:1 a un sprite, sin recortarlo: el sprite completo cabe.
  drawFlower(sprite, 0, 2, 4);
  const zoomPx = new Uint8Array(sprite.px);
  for (let i = 0; i < zoomPx.length; i++) if (zoomPx[i] === E.TRANSPARENT) zoomPx[i] = R.sky[3];
  writePNG(
    path.join(OUT, 'flor_zoom.png'),
    SPR_W * 10, SPR_H * 10, upscale(zoomPx, SPR_W, SPR_H, 10), pal.rgb.dark, pal.count
  );

  console.log(`paleta: ${pal.count} colores`);
  for (const r of report) {
    console.log(
      `  ${r.theme.padEnd(5)}  colores distintos en el cuadro: ${r.distinct}` +
        `  |  pixeles fuera de paleta: ${r.outside}`
    );
  }
  const fail = report.some((r) => r.outside > 0 || r.distinct > pal.count);
  process.exitCode = fail ? 1 : 0;
  console.log(fail ? 'FALLA' : 'OK');
}

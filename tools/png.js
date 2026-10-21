/* Escritor de PNG indexado para los arneses de captura.

   Las entradas de la paleta PNG que no usa la paleta del juego se pintan de
   magenta: si aparece magenta en una captura, algun pixel se salio. */

'use strict';

const fs = require('fs');
const zlib = require('zlib');

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

module.exports = { writePNG, upscale };

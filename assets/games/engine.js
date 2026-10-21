/* ============================================================================
   NeuroDAC · motor de pixel art

   Framebuffer de color indexado, rasterizador propio y presentacion por LUT.
   Ningun pixel del contenido sale de la paleta y el Canvas solo recibe el
   resultado final, ya escalado por un factor entero.

   Corre tambien en Node (sin DOM) para poder volcar cuadros a PNG en pruebas;
   todo lo que toca el navegador esta en createPresenter y en el contrato.
   ========================================================================== */

(function (root) {
  'use strict';

  /** Indice reservado en buffers de sprite: pixel vacio. */
  const TRANSPARENT = 255;
  /** Marca en sprites: al componer se aplica la LUT de vidrio sobre el fondo. */
  const GLASS = 254;

  // Luz fija desde arriba a la izquierda. El eje y crece hacia abajo, asi que
  // "arriba" es y negativo; z apunta hacia quien mira.
  const LIGHT_X = -0.48;
  const LIGHT_Y = -0.62;
  const LIGHT_Z = 0.62;

  /* ------------------------------------------------------------------ paleta */

  function hexToRgb(hex, out, offset) {
    const v = parseInt(hex.slice(1), 16);
    out[offset] = (v >> 16) & 255;
    out[offset + 1] = (v >> 8) & 255;
    out[offset + 2] = v & 255;
  }

  /**
   * Construye la paleta a partir de rampas ordenadas de oscuro a claro.
   *
   * spec.ramps : [{ name, colors: [hex...] }]
   * spec.themes: { nombreTema: { nombreRampa: [hex...] } }  reemplazos por tema
   *
   * Los indices son los mismos en todos los temas; cambiar de tema es cambiar
   * la tabla RGB de presentacion, no volver a pintar.
   */
  function createPalette(spec) {
    let count = 0;
    for (const r of spec.ramps) count += r.colors.length;
    if (count > 253) throw new Error('paleta demasiado grande: ' + count);

    const ramps = {};
    const family = new Uint8Array(256);
    const tone = new Uint8Array(256);
    const rampStart = new Uint8Array(256);
    const rampLength = new Uint8Array(256);
    const base = new Uint8Array(count * 3);

    let index = 0;
    spec.ramps.forEach(function (r, familyId) {
      const indices = new Uint8Array(r.colors.length);
      for (let t = 0; t < r.colors.length; t++) {
        indices[t] = index;
        family[index] = familyId;
        tone[index] = t;
        rampStart[index] = indices[0];
        rampLength[index] = r.colors.length;
        hexToRgb(r.colors[t], base, index * 3);
        index++;
      }
      // rampStart se fija despues de asignar el primer indice de la rampa.
      for (let t = 0; t < indices.length; t++) rampStart[indices[t]] = indices[0];
      ramps[r.name] = indices;
    });

    const rgb = { base: base };
    const themeNames = Object.keys(spec.themes || {});
    for (const name of themeNames) {
      const table = base.slice();
      const overrides = spec.themes[name];
      for (const rampName of Object.keys(overrides)) {
        const indices = ramps[rampName];
        const colors = overrides[rampName];
        if (!indices || colors.length !== indices.length) {
          throw new Error('el tema ' + name + ' no respeta la rampa ' + rampName);
        }
        for (let t = 0; t < colors.length; t++) hexToRgb(colors[t], table, indices[t] * 3);
      }
      rgb[name] = table;
    }

    return {
      count: count,
      ramps: ramps,
      family: family,
      tone: tone,
      rampStart: rampStart,
      rampLength: rampLength,
      rgb: rgb,
    };
  }

  /** Tono mas oscuro de la rampa a la que pertenece un indice. */
  function darkestOf(pal, i) {
    return pal.rampStart[i];
  }

  /** LUT de desplazamiento dentro de la propia rampa: nunca cambia de matiz. */
  function rampShiftLUT(pal, delta) {
    const lut = new Uint8Array(256);
    for (let i = 0; i < 256; i++) lut[i] = i;
    for (let i = 0; i < pal.count; i++) {
      const t = Math.max(0, Math.min(pal.rampLength[i] - 1, pal.tone[i] + delta));
      lut[i] = pal.rampStart[i] + t;
    }
    return lut;
  }

  /** Distancia redmean: aproxima la percepcion mejor que la euclidiana. */
  function redmean(r1, g1, b1, r2, g2, b2) {
    const rm = (r1 + r2) * 0.5;
    const dr = r1 - r2;
    const dg = g1 - g2;
    const db = b1 - b2;
    return (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db;
  }

  /**
   * LUT de mezcla: LUT[i] = color de paleta mas cercano a mezclar i con un
   * color objetivo. allowedFamilies restringe los candidatos; sin restriccion
   * aparecen saltos de matiz (el cielo visto por un vidrio sale morado).
   * Si allowedFamilies es null, solo se aceptan tonos de la misma rampa.
   */
  function buildMixLUT(pal, r, g, b, amount, allowedFamilies, theme) {
    const table = pal.rgb[theme || 'base'];
    const allowed = new Uint8Array(256);
    if (allowedFamilies) for (const f of allowedFamilies) allowed[f] = 1;

    const lut = new Uint8Array(256);
    for (let i = 0; i < 256; i++) lut[i] = i;

    for (let i = 0; i < pal.count; i++) {
      const tr = table[i * 3] + (r - table[i * 3]) * amount;
      const tg = table[i * 3 + 1] + (g - table[i * 3 + 1]) * amount;
      const tb = table[i * 3 + 2] + (b - table[i * 3 + 2]) * amount;
      let best = i;
      let bestD = Infinity;
      for (let j = 0; j < pal.count; j++) {
        const ok = allowedFamilies ? allowed[pal.family[j]] : pal.family[j] === pal.family[i];
        if (!ok) continue;
        const d = redmean(tr, tg, tb, table[j * 3], table[j * 3 + 1], table[j * 3 + 2]);
        if (d < bestD) {
          bestD = d;
          best = j;
        }
      }
      lut[i] = best;
    }
    return lut;
  }

  /** Tabla de presentacion RGBA empaquetada (little-endian: 0xAABBGGRR). */
  function presentLUT(pal, theme) {
    const table = pal.rgb[theme] || pal.rgb.base;
    const lut = new Uint32Array(256);
    for (let i = 0; i < pal.count; i++) {
      lut[i] =
        (255 << 24) | (table[i * 3 + 2] << 16) | (table[i * 3 + 1] << 8) | table[i * 3];
    }
    lut[TRANSPARENT] = 0;
    return lut;
  }

  /* ------------------------------------------------------------- framebuffer */

  /**
   * Un buffer indexado con un buffer paralelo de identificadores de pieza,
   * que es lo que permite el contorno interior solo donde dos piezas se
   * superponen.
   */
  function createFrame(w, h, fill) {
    const f = {
      w: w,
      h: h,
      px: new Uint8Array(w * h),
      id: new Uint8Array(w * h),
    };
    f.px.fill(fill === undefined ? TRANSPARENT : fill);
    return f;
  }

  function clearFrame(f, value) {
    f.px.fill(value);
    f.id.fill(0);
  }

  /* --------------------------------------------------------------- tramado */

  const BAYER4 = new Float32Array([
    0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5,
  ]);
  for (let i = 0; i < 16; i++) BAYER4[i] = (BAYER4[i] + 0.5) / 16;

  /** Umbral de Bayer 4x4 en (0, 1). */
  function bayer(x, y) {
    return BAYER4[((y & 3) << 2) | (x & 3)];
  }

  /**
   * Elige un tono entero de una rampa a partir de un valor continuo, tramando
   * la parte fraccionaria. Es como se hacen degradados sin salir de la paleta.
   */
  function ditherTone(ramp, value, x, y) {
    const last = ramp.length - 1;
    if (value <= 0) return ramp[0];
    if (value >= last) return ramp[last];
    const lo = value | 0;
    return bayer(x, y) < value - lo ? ramp[lo + 1] : ramp[lo];
  }

  /** Aplica una LUT sobre un rectangulo, opcionalmente tramada por intensidad. */
  function applyLUT(f, lut, x0, y0, w, h, intensity) {
    const xa = Math.max(0, x0 | 0);
    const ya = Math.max(0, y0 | 0);
    const xb = Math.min(f.w, (x0 + w) | 0);
    const yb = Math.min(f.h, (y0 + h) | 0);
    const full = intensity === undefined || intensity >= 1;
    for (let y = ya; y < yb; y++) {
      let j = y * f.w + xa;
      for (let x = xa; x < xb; x++, j++) {
        if (full || bayer(x, y) < intensity) f.px[j] = lut[f.px[j]];
      }
    }
  }

  /* -------------------------------------------------------------- material */

  /**
   * Un material es una rampa con un tono de partida y un umbral especular.
   * Se crea una vez al cargar; nunca dentro de un bucle de pixeles.
   */
  function material(ramp, options) {
    const o = options || {};
    return {
      ramp: ramp,
      baseTone: o.baseTone === undefined ? 0 : o.baseTone,
      spec: o.spec || 0,
      specIndex: o.specIndex === undefined ? -1 : o.specIndex,
    };
  }

  /* ----------------------------------------------------------- rasterizador */

  // Parametros y salidas del rasterizador en variables de modulo: ninguna
  // primitiva crea closures ni objetos por pixel.
  const P = new Float32Array(12);
  // Salidas en un arreglo tipado y no en variables `let`: V8 empaqueta en el
  // heap cada flotante que se escribe en una variable de cierre, y eso era
  // alocacion por primitiva dibujada.
  const OUT = new Float64Array(4);
  const SD = 0;
  const NX = 1;
  const NY = 2;
  const NZ = 3;

  const K_ELLIPSE = 1;
  const K_CAPSULE = 2;
  const K_RING = 3;
  const K_TRIANGLE = 4;

  /**
   * Evalua la primitiva activa en el centro del pixel (x, y); deja distancia y
   * normal en OUT.
   *
   * Recibe enteros y suma el medio pixel adentro. Si recibiera los flotantes
   * x + 0.5, cada uno cruzaria la llamada empaquetado en el heap: 32 bytes por
   * pixel, decenas de KB por cuadro.
   */
  function evaluate(kind, x, y) {
    const px = x + 0.5;
    const py = y + 0.5;
    switch (kind) {
      case K_ELLIPSE: {
        // P: cx, cy, rx, ry, cos, sin
        const dx = px - P[0];
        const dy = py - P[1];
        const u = (dx * P[4] + dy * P[5]) / P[2];
        const v = (-dx * P[5] + dy * P[4]) / P[3];
        const r = Math.sqrt(u * u + v * v);
        OUT[SD] = (r - 1) * Math.min(P[2], P[3]);
        // Normal de esfera, devuelta al marco de la pantalla.
        const z2 = 1 - u * u - v * v;
        const lx = u;
        const ly = v;
        OUT[NX] = lx * P[4] - ly * P[5];
        OUT[NY] = lx * P[5] + ly * P[4];
        OUT[NZ] = z2 > 0 ? Math.sqrt(z2) : 0;
        return;
      }
      case K_CAPSULE: {
        // P: ax, ay, ra, bx, by, rb
        const abx = P[3] - P[0];
        const aby = P[4] - P[1];
        const apx = px - P[0];
        const apy = py - P[1];
        const len2 = abx * abx + aby * aby;
        let t = len2 > 0 ? (apx * abx + apy * aby) / len2 : 0;
        if (t < 0) t = 0;
        else if (t > 1) t = 1;
        const r = P[2] + (P[5] - P[2]) * t;
        const ox = apx - abx * t;
        const oy = apy - aby * t;
        const dist = Math.sqrt(ox * ox + oy * oy);
        OUT[SD] = dist - r;
        // Normal de cilindro alrededor del eje.
        const k = r > 0 ? 1 / r : 0;
        OUT[NX] = ox * k;
        OUT[NY] = oy * k;
        const z2 = 1 - OUT[NX] * OUT[NX] - OUT[NY] * OUT[NY];
        OUT[NZ] = z2 > 0 ? Math.sqrt(z2) : 0;
        return;
      }
      case K_RING: {
        // P: cx, cy, rx, ry, grosor
        const u = (px - P[0]) / P[2];
        const v = (py - P[1]) / P[3];
        const r = Math.sqrt(u * u + v * v);
        const scale = Math.min(P[2], P[3]);
        const half = P[4] * 0.5;
        const radial = (r - 1) * scale;
        OUT[SD] = Math.abs(radial) - half;
        // Normal de toro: el corte transversal del anillo es un circulo.
        const k = half > 0 ? radial / half : 0;
        const inv = r > 0 ? 1 / r : 0;
        OUT[NX] = k * u * inv;
        OUT[NY] = k * v * inv;
        const z2 = 1 - k * k;
        OUT[NZ] = z2 > 0 ? Math.sqrt(z2) : 0;
        return;
      }
      case K_TRIANGLE: {
        // P: x0, y0, x1, y1, x2, y2 en sentido horario en pantalla.
        const e0 = edge(P[0], P[1], P[2], P[3], px, py);
        const e1 = edge(P[2], P[3], P[4], P[5], px, py);
        const e2 = edge(P[4], P[5], P[0], P[1], px, py);
        OUT[SD] = Math.max(e0, e1, e2);
        OUT[NX] = 0;
        OUT[NY] = 0;
        OUT[NZ] = 1;
        return;
      }
    }
  }

  /** Distancia con signo a una arista; negativa del lado interior. */
  function edge(ax, ay, bx, by, px, py) {
    const ex = bx - ax;
    const ey = by - ay;
    const len = Math.sqrt(ex * ex + ey * ey) || 1;
    return ((px - ax) * ey - (py - ay) * ex) / len;
  }

  /** True si el ultimo `shade` cayo en el brillo especular. */
  let specHit = false;

  /** Cuantiza la iluminacion de la normal actual a un tono de la rampa. */
  function shade(mat) {
    let lit = OUT[NX] * LIGHT_X + OUT[NY] * LIGHT_Y + OUT[NZ] * LIGHT_Z;
    if (lit < 0) lit = 0;
    specHit = mat.spec > 0 && mat.specIndex >= 0 && lit > 1 - mat.spec;
    const ramp = mat.ramp;
    const usable = ramp.length - mat.baseTone;
    let t = mat.baseTone + Math.floor(lit * usable);
    if (t > ramp.length - 1) t = ramp.length - 1;
    return t;
  }

  /**
   * Recorre la caja delimitadora y pinta los pixeles interiores.
   * Si el borde de esta pieza cae sobre otra pieza ya pintada, ese borde baja
   * un tono: asi el brazo se separa del torso sin lineas dentro del brazo.
   */
  function raster(f, kind, mat, piece, x0, y0, x1, y1) {
    const xa = Math.max(0, Math.floor(x0));
    const ya = Math.max(0, Math.floor(y0));
    const xb = Math.min(f.w - 1, Math.ceil(x1));
    const yb = Math.min(f.h - 1, Math.ceil(y1));
    const ramp = mat.ramp;
    for (let y = ya; y <= yb; y++) {
      let j = y * f.w + xa;
      for (let x = xa; x <= xb; x++, j++) {
        evaluate(kind, x, y);
        if (OUT[SD] > 0) continue;
        let t = shade(mat);
        if (specHit) {
          f.px[j] = mat.specIndex;
        } else {
          const occupied = f.id[j];
          if (OUT[SD] > -1 && occupied !== 0 && occupied !== piece && t > 0) t--;
          f.px[j] = ramp[t];
        }
        f.id[j] = piece;
      }
    }
  }

  function ellipse(f, mat, piece, cx, cy, rx, ry, angle) {
    const a = angle || 0;
    P[0] = cx;
    P[1] = cy;
    P[2] = rx;
    P[3] = ry;
    P[4] = Math.cos(a);
    P[5] = Math.sin(a);
    const m = Math.max(rx, ry) + 1;
    raster(f, K_ELLIPSE, mat, piece, cx - m, cy - m, cx + m, cy + m);
  }

  function capsule(f, mat, piece, ax, ay, ra, bx, by, rb) {
    P[0] = ax;
    P[1] = ay;
    P[2] = ra;
    P[3] = bx;
    P[4] = by;
    P[5] = rb;
    const m = Math.max(ra, rb) + 1;
    raster(
      f, K_CAPSULE, mat, piece,
      Math.min(ax, bx) - m, Math.min(ay, by) - m,
      Math.max(ax, bx) + m, Math.max(ay, by) + m
    );
  }

  function ring(f, mat, piece, cx, cy, rx, ry, thickness) {
    P[0] = cx;
    P[1] = cy;
    P[2] = rx;
    P[3] = ry;
    P[4] = thickness;
    const m = Math.max(rx, ry) + thickness;
    raster(f, K_RING, mat, piece, cx - m, cy - m, cx + m, cy + m);
  }

  function triangle(f, mat, piece, x0, y0, x1, y1, x2, y2) {
    // El rasterizador espera orden horario en pantalla; se corrige si no.
    const cross = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0);
    if (cross > 0) {
      P[0] = x0; P[1] = y0; P[2] = x1; P[3] = y1; P[4] = x2; P[5] = y2;
    } else {
      P[0] = x0; P[1] = y0; P[2] = x2; P[3] = y2; P[4] = x1; P[5] = y1;
    }
    raster(
      f, K_TRIANGLE, mat, piece,
      Math.min(x0, x1, x2) - 1, Math.min(y0, y1, y2) - 1,
      Math.max(x0, x1, x2) + 1, Math.max(y0, y1, y2) + 1
    );
  }

  function pixel(f, x, y, index) {
    x |= 0;
    y |= 0;
    if (x < 0 || y < 0 || x >= f.w || y >= f.h) return;
    f.px[y * f.w + x] = index;
  }

  /** Linea de Bresenham, para detalles de un pixel de grosor. */
  function line(f, x0, y0, x1, y1, index) {
    x0 |= 0; y0 |= 0; x1 |= 0; y1 |= 0;
    const dx = Math.abs(x1 - x0);
    const dy = -Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1;
    const sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (;;) {
      pixel(f, x0, y0, index);
      if (x0 === x1 && y0 === y1) return;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }

  function rect(f, x, y, w, h, index) {
    const xa = Math.max(0, x | 0);
    const ya = Math.max(0, y | 0);
    const xb = Math.min(f.w, (x + w) | 0);
    const yb = Math.min(f.h, (y + h) | 0);
    for (let yy = ya; yy < yb; yy++) f.px.fill(index, yy * f.w + xa, yy * f.w + xb);
  }

  /* ---------------------------------------------------------------- sprites */

  /**
   * Contorno selectivo. Un pixel vacio con vecino lleno recibe contorno; si el
   * vecino esta arriba o a la izquierda el contorno cae del lado en sombra y
   * va en tinta, si esta abajo o a la derecha cae del lado iluminado y toma el
   * tono mas oscuro de la rampa del vecino. Se escribe en un buffer aparte
   * para que el contorno recien puesto no engorde el siguiente.
   */
  function selOut(spr, pal, ink, scratch) {
    const w = spr.w;
    const h = spr.h;
    const px = spr.px;
    scratch.fill(TRANSPARENT);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const j = y * w + x;
        if (px[j] !== TRANSPARENT) continue;
        const up = y > 0 ? px[j - w] : TRANSPARENT;
        const left = x > 0 ? px[j - 1] : TRANSPARENT;
        if (up !== TRANSPARENT || left !== TRANSPARENT) {
          scratch[j] = ink;
          continue;
        }
        const down = y < h - 1 ? px[j + w] : TRANSPARENT;
        const right = x < w - 1 ? px[j + 1] : TRANSPARENT;
        const n = down !== TRANSPARENT ? down : right;
        if (n !== TRANSPARENT && n < pal.count) scratch[j] = darkestOf(pal, n);
      }
    }
    for (let j = 0; j < px.length; j++) if (scratch[j] !== TRANSPARENT) px[j] = scratch[j];
  }

  /**
   * Compone un sprite sobre un cuadro. alpha < 1 lo vuelve translucido por
   * tramado; glassLUT, si existe, se aplica sobre el fondo donde el sprite
   * tenga la marca GLASS.
   */
  function blit(dst, spr, x, y, alpha, glassLUT) {
    const a = alpha === undefined ? 1 : alpha;
    const ox = x | 0;
    const oy = y | 0;
    for (let sy = 0; sy < spr.h; sy++) {
      const dy = oy + sy;
      if (dy < 0 || dy >= dst.h) continue;
      for (let sx = 0; sx < spr.w; sx++) {
        const dx = ox + sx;
        if (dx < 0 || dx >= dst.w) continue;
        const v = spr.px[sy * spr.w + sx];
        if (v === TRANSPARENT) continue;
        const j = dy * dst.w + dx;
        if (v === GLASS) {
          if (glassLUT) dst.px[j] = glassLUT[dst.px[j]];
          continue;
        }
        if (a < 1 && bayer(dx, dy) >= a) continue;
        dst.px[j] = v;
      }
    }
  }

  /* ------------------------------------------------------- fuente bitmap 3x5 */

  // Cada glifo son 15 bits: cinco filas de tres, la fila superior en los bits
  // altos. Mayusculas solamente; las minusculas se dibujan como mayusculas.
  const GLYPH = new Uint16Array(256);
  const ACCENT = new Uint8Array(256); // 1 agudo, 2 tilde, 3 dieresis

  function g(rows) {
    let v = 0;
    for (let i = 0; i < 5; i++) v = (v << 3) | parseInt(rows[i], 2);
    return v;
  }

  const GLYPHS = {
    A: ['010', '101', '111', '101', '101'], B: ['110', '101', '110', '101', '110'],
    C: ['011', '100', '100', '100', '011'], D: ['110', '101', '101', '101', '110'],
    E: ['111', '100', '110', '100', '111'], F: ['111', '100', '110', '100', '100'],
    G: ['011', '100', '101', '101', '011'], H: ['101', '101', '111', '101', '101'],
    I: ['111', '010', '010', '010', '111'], J: ['001', '001', '001', '101', '010'],
    K: ['101', '101', '110', '101', '101'], L: ['100', '100', '100', '100', '111'],
    M: ['101', '111', '111', '101', '101'], N: ['110', '101', '101', '101', '101'],
    O: ['010', '101', '101', '101', '010'], P: ['110', '101', '110', '100', '100'],
    Q: ['010', '101', '101', '110', '011'], R: ['110', '101', '110', '101', '101'],
    S: ['011', '100', '010', '001', '110'], T: ['111', '010', '010', '010', '010'],
    U: ['101', '101', '101', '101', '111'], V: ['101', '101', '101', '101', '010'],
    W: ['101', '101', '111', '111', '101'], X: ['101', '101', '010', '101', '101'],
    Y: ['101', '101', '010', '010', '010'], Z: ['111', '001', '010', '100', '111'],
    0: ['111', '101', '101', '101', '111'], 1: ['010', '110', '010', '010', '111'],
    2: ['110', '001', '010', '100', '111'], 3: ['110', '001', '010', '001', '110'],
    4: ['101', '101', '111', '001', '001'], 5: ['111', '100', '110', '001', '110'],
    6: ['011', '100', '110', '101', '010'], 7: ['111', '001', '010', '010', '010'],
    8: ['010', '101', '010', '101', '010'], 9: ['010', '101', '011', '001', '110'],
    '.': ['000', '000', '000', '000', '010'], ',': ['000', '000', '000', '010', '100'],
    ':': ['000', '010', '000', '010', '000'], '!': ['010', '010', '010', '000', '010'],
    '?': ['110', '001', '010', '000', '010'], '-': ['000', '000', '111', '000', '000'],
    '/': ['001', '001', '010', '100', '100'], '%': ['101', '001', '010', '100', '101'],
    '+': ['000', '010', '111', '010', '000'], '(': ['001', '010', '010', '010', '001'],
    ')': ['100', '010', '010', '010', '100'], '\u00A1': ['010', '000', '010', '010', '010'],
    '\u00BF': ['010', '000', '010', '100', '011'],
  };

  for (const ch of Object.keys(GLYPHS)) {
    const code = ch.charCodeAt(0);
    GLYPH[code] = g(GLYPHS[ch]);
    if (code >= 65 && code <= 90) GLYPH[code + 32] = GLYPH[code];
  }

  // Letras acentuadas: glifo base mas una marca dibujada aparte.
  const ACCENTED = [
    ['\u00C1\u00E1', 'A', 1], ['\u00C9\u00E9', 'E', 1], ['\u00CD\u00ED', 'I', 1],
    ['\u00D3\u00F3', 'O', 1], ['\u00DA\u00FA', 'U', 1], ['\u00D1\u00F1', 'N', 2],
    ['\u00DC\u00FC', 'U', 3],
  ];
  for (const [chars, baseChar, mark] of ACCENTED) {
    for (const c of chars) {
      GLYPH[c.charCodeAt(0)] = GLYPH[baseChar.charCodeAt(0)];
      ACCENT[c.charCodeAt(0)] = mark;
    }
  }

  const GLYPH_W = 3;
  const GLYPH_ADVANCE = 4;
  /** Alto de linea: una fila para acentos, cinco de glifo y una de aire. */
  const LINE_HEIGHT = 7;

  function drawGlyph(f, code, x, y, index) {
    const bits = GLYPH[code];
    for (let row = 0; row < 5; row++) {
      const r = (bits >> ((4 - row) * 3)) & 7;
      if (r & 4) pixel(f, x, y + row, index);
      if (r & 2) pixel(f, x + 1, y + row, index);
      if (r & 1) pixel(f, x + 2, y + row, index);
    }
    switch (ACCENT[code]) {
      case 1: pixel(f, x + 2, y - 1, index); break;
      case 2: // virgulilla: a 3x5 no cabe la onda; la convencion es una barra
        pixel(f, x, y - 1, index); pixel(f, x + 1, y - 1, index); pixel(f, x + 2, y - 1, index);
        break;
      case 3: pixel(f, x, y - 1, index); pixel(f, x + 2, y - 1, index); break;
    }
  }

  /** Dibuja texto constante; recorrer con charCodeAt no aloca. */
  function text(f, str, x, y, index) {
    let cx = x;
    for (let i = 0; i < str.length; i++) {
      const code = str.charCodeAt(i);
      if (code < 256) drawGlyph(f, code, cx, y, index);
      cx += GLYPH_ADVANCE;
    }
    return cx;
  }

  /** Primer caracter que la fuente no puede dibujar, o null si todos se pueden. */
  function unsupportedChar(str) {
    for (let i = 0; i < str.length; i++) {
      const code = str.charCodeAt(i);
      if (code === 32) continue;
      if (code >= 256 || GLYPH[code] === 0) return str[i];
    }
    return null;
  }

  function textWidth(str) {
    return str.length > 0 ? str.length * GLYPH_ADVANCE - 1 : 0;
  }

  /** Dibuja un entero digito por digito, sin construir strings. */
  function number(f, value, x, y, index, minDigits) {
    let v = Math.max(0, Math.round(value));
    let digits = 1;
    for (let p = 10; p <= v; p *= 10) digits++;
    if (minDigits && digits < minDigits) digits = minDigits;
    let cx = x + (digits - 1) * GLYPH_ADVANCE;
    for (let i = 0; i < digits; i++) {
      drawGlyph(f, 48 + (v % 10), cx, y, index);
      v = (v / 10) | 0;
      cx -= GLYPH_ADVANCE;
    }
    return x + digits * GLYPH_ADVANCE;
  }

  /* ------------------------------------------------------------- particulas */

  /** Particulas en struct-of-arrays; se eliminan por swap-remove. */
  function createParticles(capacity) {
    return {
      capacity: capacity,
      count: 0,
      x: new Float32Array(capacity),
      y: new Float32Array(capacity),
      vx: new Float32Array(capacity),
      vy: new Float32Array(capacity),
      life: new Float32Array(capacity),
      maxLife: new Float32Array(capacity),
      color: new Uint8Array(capacity),
    };
  }

  function spawnParticle(p, x, y, vx, vy, life, color) {
    if (p.count >= p.capacity) return;
    const i = p.count++;
    p.x[i] = x; p.y[i] = y; p.vx[i] = vx; p.vy[i] = vy;
    p.life[i] = life; p.maxLife[i] = life; p.color[i] = color;
  }

  function updateParticles(p, gravity) {
    let i = 0;
    while (i < p.count) {
      p.life[i] -= 1;
      if (p.life[i] <= 0) {
        const last = --p.count;
        p.x[i] = p.x[last]; p.y[i] = p.y[last];
        p.vx[i] = p.vx[last]; p.vy[i] = p.vy[last];
        p.life[i] = p.life[last]; p.maxLife[i] = p.maxLife[last];
        p.color[i] = p.color[last];
        continue;
      }
      p.vy[i] += gravity;
      p.x[i] += p.vx[i];
      p.y[i] += p.vy[i];
      i++;
    }
  }

  /* ---------------------------------------------------------------- resortes */

  /**
   * Resortes subamortiguados en un solo Float32Array: [pos, vel] por resorte.
   * Dan movimiento secundario (tallos, hojas) excitado por cambios de entrada.
   */
  function createSprings(n) {
    return new Float32Array(n * 2);
  }

  function stepSpring(s, i, target, stiffness, damping) {
    const k = i * 2;
    const accel = (target - s[k]) * stiffness - s[k + 1] * damping;
    s[k + 1] += accel;
    s[k] += s[k + 1];
    return s[k];
  }

  /* ------------------------------------------------------------------- bucle */

  const STEP_MS = 1000 / 60;
  const MAX_STEPS = 5;
  /** La pose se muestrea cada 5 ticks de logica: animacion a 12 fps. */
  const ANIM_TICKS = 5;

  /**
   * Logica a 60 Hz fijos con acumulador. Si se acumula mas deuda que el tope,
   * se descarta en lugar de intentar alcanzarla, que es lo que congela un
   * juego tras perder el foco de la pestana.
   */
  function runLoop(update, render) {
    let last = -1;
    let acc = 0;
    function frame(t) {
      if (last < 0) last = t;
      acc += t - last;
      last = t;
      let steps = 0;
      while (acc >= STEP_MS && steps < MAX_STEPS) {
        update();
        acc -= STEP_MS;
        steps++;
      }
      if (steps === MAX_STEPS) acc = 0;
      render();
      root.requestAnimationFrame(frame);
    }
    root.requestAnimationFrame(frame);
  }

  /* ------------------------------------------------------------ presentacion */

  /**
   * Factor entero con el que un area de cw x ch pixeles de dispositivo muestra
   * una region logica de vw x vh. La tolerancia absorbe el redondeo: con
   * densidades fraccionarias, como 1.75, el lienzo puede medir uno o dos
   * pixeles de dispositivo menos que el multiplo exacto (el navegador redondea
   * y el punto flotante da 1979.999 por 1980), y sin ella el factor caeria un
   * paso entero. Va en pixeles y no como fraccion del factor: una fraccion
   * fija cubre menos pixeles cuanto mayor es la resolucion logica.
   */
  const SLACK_PX = 2;

  function integerScale(cw, ch, vw, vh) {
    return Math.max(1, Math.floor(Math.min((cw + SLACK_PX) / vw, (ch + SLACK_PX) / vh)));
  }

  /**
   * Factor y ancho logico para llenar un lienzo de cw x ch pixeles de
   * dispositivo con altura logica fija h y ancho logico entre minW y maxW.
   *
   * El factor sale del alto, que la pagina ajusta a un multiplo exacto; el
   * ancho logico, de cuantas columnas caben a ese factor. Asi el juego llena
   * el ancho completo con escalado entero en lugar de dejar franjas.
   */
  function fitWidth(cw, ch, minW, maxW, h) {
    const scale = Math.max(1, Math.floor((ch + SLACK_PX) / h));
    // Redondeo al mas cercano y no floor: si el navegador deja el lienzo un
    // pixel de dispositivo corto, floor perderia una columna logica entera y
    // dejaria una franja. Lo peor del redondeo es recortar medio pixel logico
    // en el borde.
    const w = Math.max(minW, Math.min(maxW, Math.floor(cw / scale + 0.5)));
    return { scale: scale, w: w };
  }

  /**
   * Convierte el framebuffer a RGBA con una LUT Uint32 y lo escala al canvas
   * visible por un factor entero en pixeles de dispositivo.
   */
  function createPresenter(canvas, w, h, pal) {
    const doc = root.document;
    const small = doc.createElement('canvas');
    const sctx = small.getContext('2d');
    let image = null;
    let out = null;
    const ctx = canvas.getContext('2d');

    /** Asigna el buffer de presentacion; solo al crear y al cambiar de tamano. */
    function allocate(nw, nh) {
      w = nw;
      h = nh;
      small.width = w;
      small.height = h;
      image = sctx.createImageData(w, h);
      out = new Uint32Array(image.data.buffer);
    }
    allocate(w, h);

    const luts = {};
    for (const name of Object.keys(pal.rgb)) luts[name] = presentLUT(pal, name);

    let lut = luts.base;
    let backdrop = '#000';
    let scale = 1;
    let ox = 0;
    let oy = 0;
    // Region del framebuffer que se presenta: todo, o un acercamiento.
    let vx = 0;
    let vy = 0;
    let vw = w;
    let vh = h;
    let grid = false;
    const GRID_STYLE = 'rgba(0,0,0,0.28)';

    function resize() {
      const dpr = root.devicePixelRatio || 1;
      const cw = Math.max(1, Math.floor(canvas.clientWidth * dpr));
      const ch = Math.max(1, Math.floor(canvas.clientHeight * dpr));
      canvas.width = cw;
      canvas.height = ch;
      scale = integerScale(cw, ch, vw, vh);
      ox = (cw - vw * scale) >> 1;
      oy = (ch - vh * scale) >> 1;
      ctx.imageSmoothingEnabled = false;
    }

    /** Acercamiento entero a una region; sin argumentos vuelve al cuadro completo. */
    function setView(x, y, rw, rh) {
      if (x === undefined) {
        vx = 0; vy = 0; vw = w; vh = h;
      } else {
        vx = Math.max(0, x | 0);
        vy = Math.max(0, y | 0);
        vw = Math.min(w - vx, rw | 0);
        vh = Math.min(h - vy, rh | 0);
      }
      resize();
    }

    function setGrid(on) {
      grid = !!on;
    }

    /** Cambia la resolucion logica; vuelve al cuadro completo. */
    function setLogicalSize(nw, nh) {
      allocate(nw, nh);
      vx = 0;
      vy = 0;
      vw = w;
      vh = h;
      resize();
    }

    function setTheme(name, backdropIndex) {
      lut = luts[name] || luts.base;
      const table = pal.rgb[name] || pal.rgb.base;
      const i = (backdropIndex || 0) * 3;
      backdrop = 'rgb(' + table[i] + ',' + table[i + 1] + ',' + table[i + 2] + ')';
    }

    function present(fb) {
      const px = fb.px;
      for (let i = 0; i < px.length; i++) out[i] = lut[px[i]];
      sctx.putImageData(image, 0, 0);
      ctx.fillStyle = backdrop;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(small, vx, vy, vw, vh, ox, oy, vw * scale, vh * scale);
      // Rejilla de depuracion: rectangulos de 1 px, sin antialiasing.
      if (grid && scale >= 3) {
        ctx.fillStyle = GRID_STYLE;
        for (let i = 0; i <= vw; i++) ctx.fillRect(ox + i * scale, oy, 1, vh * scale);
        for (let j = 0; j <= vh; j++) ctx.fillRect(ox, oy + j * scale, vw * scale, 1);
      }
    }

    canvas.style.imageRendering = 'pixelated';
    root.addEventListener('resize', resize);
    resize();
    return {
      present: present,
      setTheme: setTheme,
      resize: resize,
      setView: setView,
      setGrid: setGrid,
      setLogicalSize: setLogicalSize,
    };
  }

  /* ---------------------------------------------------------------- contrato */

  /**
   * Estado recibido de la aplicacion por postMessage; el protocolo esta en
   * docs/contrato-juegos.md y lo emite src/neurodac/game_page.py.
   *
   * La ausencia de senal es NaN, nunca un numero que podria ser una lectura.
   *
   * Un juego abierto directo en el navegador es autonomo: la compuerta se
   * considera abierta y la senal se controla con teclado. Dentro del iframe de
   * la aplicacion nunca lo es. No se decide por tiempo sin mensajes: el primer
   * mensaje de la pagina puede llegar antes de que el juego cargue y perderse,
   * y el juego se declararia autonomo dentro de la aplicacion.
   */
  const SOURCE = 'neurodac';
  let embedded =
    typeof root.top !== 'undefined' && typeof root.self !== 'undefined' && root.self !== root.top;
  const KEY_COUNT = 10;
  const KEY = {
    left: 0, right: 1, up: 2, down: 3, w: 4, s: 5, grid: 6, zoom: 7, sheet: 8, scene: 9,
  };
  const KEY_BY_NAME = {
    ArrowLeft: 0, ArrowRight: 1, ArrowUp: 2, ArrowDown: 3,
    w: 4, W: 4, s: 5, S: 5, g: 6, G: 6, z: 7, Z: 7, h: 8, H: 8, b: 9, B: 9,
  };

  const input = {
    signal: NaN,
    ready: false,
    simulated: false,
    theme: 'dark',
    lastMessageAt: -1,
    held: new Uint8Array(KEY_COUNT),
    pressed: new Uint8Array(KEY_COUNT),
  };

  function keyDown(name) {
    const k = KEY_BY_NAME[name];
    if (k === undefined) return;
    if (!input.held[k]) input.pressed[k] = 1;
    input.held[k] = 1;
  }

  function keyUp(name) {
    const k = KEY_BY_NAME[name];
    if (k !== undefined) input.held[k] = 0;
  }

  /** Limpia los flancos de tecla; se llama al final de cada tick de logica. */
  function endTick() {
    input.pressed.fill(0);
  }

  /** Fija si el juego corre dentro de la aplicacion; lo usan las pruebas. */
  function setEmbedded(value) {
    embedded = !!value;
  }

  function isStandalone() {
    return !embedded && input.lastMessageAt < 0;
  }

  /**
   * Si la simulacion puede avanzar. Dentro de la aplicacion exige `ready` y
   * un valor; abierto solo, la compuerta no aplica.
   */
  function isReady() {
    if (isStandalone()) return true;
    return input.ready && input.signal === input.signal; // NaN no es igual a si mismo
  }

  /** Aplica un mensaje del puente. Separado de listen para poder probarlo. */
  function receive(d, now) {
    if (!d || d.source !== SOURCE) return false;
    input.lastMessageAt = now;
    if ('signalValue' in d) {
      const v = d.signalValue;
      input.signal = typeof v === 'number' && isFinite(v) ? v : NaN;
    }
    if (typeof d.ready === 'boolean') input.ready = d.ready;
    if (typeof d.simulated === 'boolean') input.simulated = d.simulated;
    if (typeof d.theme === 'string') input.theme = d.theme;
    if (typeof d.keydown === 'string') keyDown(d.keydown);
    if (typeof d.keyup === 'string') keyUp(d.keyup);
    return true;
  }

  function listen(onTheme) {
    root.addEventListener('message', function (e) {
      // Solo mensajes de la misma pagina que sirve el juego.
      if (e.origin !== root.location.origin) return;
      const before = input.theme;
      if (receive(e.data, root.performance.now()) && onTheme && input.theme !== before) {
        onTheme(input.theme);
      }
    });
    root.addEventListener('keydown', function (e) { keyDown(e.key); });
    root.addEventListener('keyup', function (e) { keyUp(e.key); });
  }

  /* ---------------------------------------------------------------- herramientas */

  /** Cuenta los indices distintos presentes en un cuadro. */
  function countColors(f, seen) {
    seen.fill(0);
    let n = 0;
    for (let i = 0; i < f.px.length; i++) {
      const v = f.px[i];
      if (!seen[v]) { seen[v] = 1; n++; }
    }
    return n;
  }

  const api = {
    TRANSPARENT: TRANSPARENT,
    GLASS: GLASS,
    LINE_HEIGHT: LINE_HEIGHT,
    GLYPH_W: GLYPH_W,
    ANIM_TICKS: ANIM_TICKS,
    KEY: KEY,
    createPalette: createPalette,
    rampShiftLUT: rampShiftLUT,
    buildMixLUT: buildMixLUT,
    presentLUT: presentLUT,
    darkestOf: darkestOf,
    createFrame: createFrame,
    clearFrame: clearFrame,
    bayer: bayer,
    ditherTone: ditherTone,
    applyLUT: applyLUT,
    material: material,
    ellipse: ellipse,
    capsule: capsule,
    ring: ring,
    triangle: triangle,
    pixel: pixel,
    line: line,
    rect: rect,
    selOut: selOut,
    blit: blit,
    text: text,
    textWidth: textWidth,
    unsupportedChar: unsupportedChar,
    number: number,
    createParticles: createParticles,
    spawnParticle: spawnParticle,
    updateParticles: updateParticles,
    createSprings: createSprings,
    stepSpring: stepSpring,
    runLoop: runLoop,
    createPresenter: createPresenter,
    integerScale: integerScale,
    fitWidth: fitWidth,
    input: input,
    listen: listen,
    endTick: endTick,
    isStandalone: isStandalone,
    setEmbedded: setEmbedded,
    // Las mismas que usa el oyente de teclado; expuestas para las pruebas.
    pressKey: keyDown,
    releaseKey: keyUp,
    isReady: isReady,
    receive: receive,
    countColors: countColors,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.NDEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

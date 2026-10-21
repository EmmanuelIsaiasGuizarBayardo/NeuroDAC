/* ============================================================================
   NeuroDAC · Jardin Mental

   Neurofeedback de meditacion: la senal hace crecer cinco flores. La mecanica
   es la del juego anterior, sin cambios de umbrales ni de ritmo. Lo nuevo es
   que la senal tambien se ve continuamente en la escena: el tallo se mece mas
   lento y con menos amplitud cuanto mas calma hay, el cielo se entibia, y por
   encima del umbral aparece polen.

   Corre en el navegador y en Node: la logica no toca el DOM, para que las
   pruebas puedan ejercitarla sin navegador. El protocolo con la aplicacion
   esta en docs/contrato-juegos.md.
   ========================================================================== */

(function (root) {
  'use strict';

  const inNode = typeof module !== 'undefined' && module.exports;
  const E = inNode ? require('./engine.js') : root.NDEngine;
  const PAL = inNode ? require('./palette.js') : root.NDPalette;
  const ESC = inNode ? require('./escenarios.js') : root.NDEscenarios;
  const TEXTOS = inNode ? require('./textos.js') : root.NDTextos;

  /** Teclas que el juego atiende dentro de la aplicacion: ninguna. Las flechas
   *  solo simulan la senal con el juego abierto fuera de ella. Debe coincidir
   *  con GameSpec.keys en pages/jardin.py. */
  const KEYS_USED = [];

  /** Ancho logico: el juego llena el ancho de su recuadro con escalado
   *  entero, asi que dibuja tantas columnas como quepan entre estos limites.
   *  La altura es fija. Debe coincidir con GameSpec en pages/jardin.py. */
  const MIN_W = 240;
  const MAX_W = 360;
  const H = 180;
  const HORIZON = 116;
  const BED_TOP = 146;
  /** Linea donde nacen los tallos, dentro de la cama de tierra. */
  const BASE_Y = 160;

  // Mecanica del juego anterior. Antes corria por cuadro de pantalla, asi que
  // en un monitor de 144 Hz iba 2.4 veces mas rapido; aqui corre a 60 Hz fijos.
  const STAGES = 6;
  const FLOWERS = 5;
  const UPPER = 55;
  const LOWER = 45;
  const STEP = 1;
  const THRESHOLD = 60;
  const TICKS_PER_BEAT = 60;

  /** Umbrales que la barra de calma marca para el visitante. */
  const THRESHOLDS = [LOWER, UPPER];

  const BANNER_NONE = 0;
  const BANNER_DONE = 1;
  const BANNER_WILT = 2;
  const DONE_TICKS = 210;
  const WILT_TICKS = 150;

  /** Matas de pasto en la cama de tierra; reaccionan a la vida. */
  const TUFTS = 64;
  /** Matas que se reparten cerca de cada flor; el resto, por toda la cama,
   *  incluida la franja del frente. */
  const TUFTS_NEAR = 30;
  /** Matorrales bajos entre las flores, al fondo de la cama. */
  const BUSHES = 12;
  const BUSH_W = 18;
  const BUSH_H = 11;

  const SPR_W = 44;
  const SPR_H = 100;
  const SPR_BASE_X = 22;
  const SPR_BASE_Y = 96;

  /** Generador sembrado: con la misma semilla, la misma partida. */
  function mulberry32(seed) {
    let a = seed | 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function clamp(v, lo, hi) {
    return v < lo ? lo : v > hi ? hi : v;
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function createGame(options) {
    const o = options || {};
    const rand = mulberry32(o.seed === undefined ? Date.now() >>> 0 : o.seed);
    let W = clamp(o.width === undefined ? MIN_W : o.width | 0, MIN_W, MAX_W);

    const pal = E.createPalette(PAL.SPEC);
    const R = pal.ramps;
    const INK = R.ink[0];
    const WHITE = R.white[0];
    const TXT = TEXTOS.jardin;
    const LABEL = R.petalWhite[2];

    // Materiales: se crean una vez, nunca dentro de un bucle de pixeles.
    const MAT = {
      stem: E.material(R.foliage, { baseTone: 1 }),
      leaf: E.material(R.foliage),
      seed: E.material(R.wood),
      mound: E.material(R.soil, { baseTone: 1 }),
      center: E.material(R.orange, { spec: 0.08, specIndex: R.petalGold[2] }),
      petals: PAL.PETAL_RAMPS.map(function (name) {
        return E.material(R[name], { spec: 0.025, specIndex: WHITE });
      }),
      buds: PAL.PETAL_RAMPS.map(function (name) {
        return E.material(R[name], { baseTone: 0 });
      }),
    };
    const PETAL_LIGHT = new Uint8Array(PAL.PETAL_RAMPS.length);
    PAL.PETAL_RAMPS.forEach(function (name, i) {
      PETAL_LIGHT[i] = R[name][R[name].length - 1];
    });
    const DARKEN = E.rampShiftLUT(pal, -2);

    const scenes = ESC.createAll(E, pal);
    let backdrop = E.createFrame(W, H);
    let backdropScene = -1;
    let ground = E.createFrame(W, H);
    const sprites = [];
    for (let i = 0; i < FLOWERS; i++) sprites.push(E.createFrame(SPR_W, SPR_H));
    const scratch = new Uint8Array(SPR_W * SPR_H);
    const sheetSprite = E.createFrame(SPR_W, SPR_H);
    const springs = E.createSprings(FLOWERS);

    // Matorrales prepintados: 3 etapas x 2 variantes. En cada cuadro solo se
    // copian; rasterizarlos por cuadro alocaria por cada primitiva.
    const BUSH_STAGES = [
      // Un solo material: el apagado se deriva bajando un tono y el seco son
      // ramitas, no relleno.
      E.material(R.foliage, { baseTone: 1 }),
    ];
    const BUSH_SHAPES = [
      [5, 7, 4.5, 3.2, 10, 5, 5.5, 4, 14, 7, 3.8, 2.8],
      [6, 6, 5, 3.6, 12, 7, 4.5, 3, 9, 8, 6, 2.6],
    ];
    const bushSprites = [];
    const bushScratch = new Uint8Array(BUSH_W * BUSH_H);
    const DIM = E.rampShiftLUT(pal, -1);
    for (let st = 0; st < 3; st++) {
      for (let v = 0; v < 2; v++) {
        const spr = E.createFrame(BUSH_W, BUSH_H);
        const sh = BUSH_SHAPES[v];
        if (st < 2) {
          for (let k = 0; k < 3; k++) {
            E.ellipse(spr, BUSH_STAGES[0], 1 + k, sh[k * 4], sh[k * 4 + 1], sh[k * 4 + 2], sh[k * 4 + 3], 0);
          }
          // Apagado: el mismo matorral un tono abajo en su propia rampa. Otro
          // material seguia llegando al tono mas claro en el lado iluminado.
          if (st === 1) E.applyLUT(spr, DIM, 0, 0, BUSH_W, BUSH_H);
        } else {
          // Seco: un esqueleto de ramitas en abanico. Relleno parecia piedra,
          // y ralo por tramado, un tablero: lo regular no se lee organico.
          const bx = 9 - v;
          const by = BUSH_H - 1;
          const TIPS = [2, 4, 5, 2, 9 - v, 1, 13, 2, 16, 5];
          for (let k = 0; k < TIPS.length; k += 2) {
            E.line(spr, bx, by, TIPS[k], TIPS[k + 1], R.wood[2]);
            E.pixel(spr, TIPS[k], TIPS[k + 1], R.petalGold[0]);
          }
          E.pixel(spr, 4 + v, 4, R.grass[0]);
          E.pixel(spr, 13 - v, 3, R.grass[0]);
        }
        E.selOut(spr, pal, INK, bushScratch);
        if (st === 0) {
          // Con vida alta, dos florecitas en la copa.
          E.pixel(spr, 7 + v, 3, R.petalWhite[2]);
          E.pixel(spr, 12 - v, 4, R.petalRose[2]);
        }
        bushSprites.push(spr);
      }
    }
    const pollen = E.createParticles(160);
    const seen = new Uint8Array(256);

    const XS = new Float32Array(FLOWERS);
    /** Flores centradas con su separacion de siempre; a 240 quedan donde
     *  estaban. Lo que sobra a los lados es paisaje. */
    function placeFlowers() {
      for (let i = 0; i < FLOWERS; i++) XS[i] = Math.round(W / 2) + (i - 2) * 47;
    }
    placeFlowers();

    // Suelo vivo. Cada mata tiene sus propios umbrales: asi, cuando la vida
    // cambia, el suelo cambia de mata en mata y no todo a la vez.
    const tuftX = new Int16Array(TUFTS);
    const tuftY = new Uint8Array(TUFTS);
    const tuftShow = new Float32Array(TUFTS); // vida minima para aparecer
    const tuftBloom = new Float32Array(TUFTS); // vida minima para florecer
    const tuftJitter = new Float32Array(TUFTS); // corrimiento de su color
    const tuftColor = new Uint8Array(TUFTS);
    const bushX = new Int16Array(BUSHES);
    const bushY = new Uint8Array(BUSHES);
    const bushShow = new Float32Array(BUSHES);
    const bushJitter = new Float32Array(BUSHES);
    const bushVariant = new Uint8Array(BUSHES);
    const WILD = new Uint8Array([
      R.petalGold[2], R.petalWhite[2], R.petalRose[2], R.petalBlue[2], R.petalViolet[2],
    ]);

    // Estado en un solo objeto con arreglos tipados: nada se aloca por tick.
    const g = {
      ticks: 0,
      scene: Math.floor(rand() * scenes.length),
      current: 0,
      done: 0,
      level: new Float32Array(FLOWERS),
      health: new Float32Array(FLOWERS),
      stage: new Uint8Array(FLOWERS),
      beat: new Uint16Array(FLOWERS),
      species: new Uint8Array(FLOWERS),
      calm: 0.5,
      // Vida suavizada de la flor actual: la escena la sigue en ~medio segundo.
      vital: 0.5,
      // Intensidad del polen; nace en cero al cruzar el umbral y crece.
      pollenRate: 0,
      phase: 0,
      banner: BANNER_NONE,
      bannerTicks: 0,
      devSignal: 50,
      animDirty: true,
      // Flor actual para la que se pintaron los monticulos; -1 obliga a pintarlos.
      moundsFor: -1,
      grid: false,
      zoom: false,
      sheet: false,
      lastSignal: NaN,
    };

    drawGround(ground);
    resetGarden(false);

    /* -------------------------------------------------------------- jardin */

    function resetGarden(newScene) {
      for (let i = 0; i < FLOWERS; i++) {
        g.level[i] = 50;
        g.health[i] = 50;
        g.stage[i] = 0;
        g.beat[i] = 0;
        g.species[i] = i % PAL.PETAL_RAMPS.length;
      }
      // Fisher-Yates sobre el arreglo tipado: cada jardin cambia el orden de
      // colores sin crear arreglos.
      for (let i = FLOWERS - 1; i > 0; i--) {
        const j = Math.floor(rand() * (i + 1));
        const t = g.species[i];
        g.species[i] = g.species[j];
        g.species[j] = t;
      }
      placeTufts();
      g.current = 0;
      g.done = 0;
      g.banner = BANNER_NONE;
      g.bannerTicks = 0;
      pollen.count = 0;
      if (newScene) g.scene = ESC.pickNext(scenes.length, g.scene, rand);
      g.moundsFor = -1;
      g.animDirty = true;
    }

    function placeTufts() {
      // Matorrales repartidos a lo ancho, corridos si caerian sobre un tallo.
      for (let k = 0; k < BUSHES; k++) {
        let x = 10 + (k * (W - 20)) / (BUSHES - 1) + (rand() - 0.5) * 8;
        for (let i = 0; i < FLOWERS; i++) {
          if (Math.abs(x - XS[i]) < 10) x += x < XS[i] ? -10 : 10;
        }
        bushX[k] = Math.round(clamp(x, 4, W - 5));
        bushY[k] = BED_TOP + 9 + Math.floor(rand() * 3);
        bushShow[k] = 0.02 + rand() * 0.2;
        bushJitter[k] = (rand() - 0.5) * 0.16;
        bushVariant[k] = k & 1;
      }
      for (let k = 0; k < TUFTS; k++) {
        let x;
        if (k < TUFTS_NEAR) {
          // Alrededor de cada lugar, sin tapar el tallo ni el monticulo.
          const side = rand() < 0.5 ? -1 : 1;
          x = XS[k % FLOWERS] + side * (8 + rand() * 13);
        } else {
          x = 4 + rand() * (W - 8);
        }
        tuftX[k] = Math.round(clamp(x, 3, W - 4));
        // Las cercanas, al pie de las flores; las demas llegan hasta el frente.
        tuftY[k] = k < TUFTS_NEAR
          ? BASE_Y - 1 + Math.floor(rand() * 7)
          : BASE_Y - 1 + Math.floor(rand() * 17);
        // Casi todas sobreviven hasta la vida baja: el pasto se apaga, no se va.
        tuftShow[k] = 0.02 + rand() * 0.28;
        // Una de cada tres puede florecer, y solo con vida alta.
        tuftBloom[k] = k % 3 === 0 ? 0.58 + rand() * 0.3 : 9;
        tuftJitter[k] = (rand() - 0.5) * 0.16;
        tuftColor[k] = WILD[Math.floor(rand() * WILD.length)];
      }
    }

    /**
     * Cambia el ancho logico conservando la partida. Reasigna los buffers que
     * dependen del ancho: ocurre al redimensionar, nunca en el bucle.
     */
    function setWidth(width) {
      const nw = clamp(width | 0, MIN_W, MAX_W);
      if (nw === W) return;
      W = nw;
      backdrop = E.createFrame(W, H);
      backdropScene = -1;
      ground = E.createFrame(W, H);
      drawGround(ground);
      placeFlowers();
      placeTufts();
      g.moundsFor = -1;
      g.animDirty = true;
    }

    function nextScene() {
      g.scene = (g.scene + 1) % scenes.length;
    }

    /** Mecanica del juego anterior, sin cambios: un pulso por segundo. */
    function grow(sig) {
      const i = g.current;
      if (sig > UPPER) g.level[i] = Math.min(100, g.level[i] + STEP);
      else if (sig < LOWER) g.level[i] = Math.max(0, g.level[i] - STEP);

      g.beat[i]++;
      if (g.beat[i] >= TICKS_PER_BEAT) {
        g.beat[i] = 0;
        const above = g.level[i] >= THRESHOLD;
        if (above && g.stage[i] < STAGES) {
          g.stage[i]++;
          g.health[i] = Math.min(100, g.health[i] + 3);
        } else if (!above && g.stage[i] > 0) {
          g.health[i] = Math.max(0, g.health[i] - 3);
          g.stage[i]--;
        } else {
          g.health[i] = clamp(g.health[i] + (above ? 7 : -3), 0, 100);
        }
        g.animDirty = true;
      }

      if (g.health[i] <= 0) {
        g.banner = BANNER_WILT;
        g.bannerTicks = WILT_TICKS;
        return;
      }
      if (g.stage[i] >= STAGES) {
        g.done++;
        const next = i + 1;
        if (next < FLOWERS) {
          g.health[next] = g.health[i];
          g.current = next;
        } else {
          g.banner = BANNER_DONE;
          g.bannerTicks = DONE_TICKS;
        }
        g.animDirty = true;
      }
    }

    /* ---------------------------------------------------------------- tick */

    function tick() {
      g.ticks++;
      const standalone = E.isStandalone();
      const input = E.input;
      const K = E.KEY;

      let sig;
      if (standalone) {
        // Abierto fuera de la aplicacion: la senal es de teclado, y lo dice
        // la pantalla.
        if (input.pressed[K.up]) g.devSignal = Math.min(100, g.devSignal + 10);
        if (input.pressed[K.down]) g.devSignal = Math.max(0, g.devSignal - 10);
        if (input.pressed[K.grid]) g.grid = !g.grid;
        if (input.pressed[K.zoom]) g.zoom = !g.zoom;
        if (input.pressed[K.sheet]) g.sheet = !g.sheet;
        if (input.pressed[K.scene]) nextScene();
        sig = g.devSignal;
      } else {
        // Las herramientas del personal no existen en modo publico.
        g.grid = false;
        g.zoom = false;
        g.sheet = false;
        sig = input.signal;
      }
      g.lastSignal = sig;
      const valid = sig === sig;
      const ready = E.isReady();

      // Calma suavizada: la escena responde en cerca de un segundo, sin
      // temblar con cada paquete.
      if (valid) g.calm += (clamp((sig - 20) / 70, 0, 1) - g.calm) * 0.02;

      // Vaiven: mas lento y mas corto cuanto mas calma. La fase se acumula
      // para que un cambio de frecuencia no produzca saltos.
      g.phase += lerp(2.6, 0.7, g.calm) / 60;
      const amplitude = lerp(3.4, 0.6, g.calm);
      for (let i = 0; i < FLOWERS; i++) {
        E.stepSpring(springs, i, amplitude * Math.sin(g.phase + i * 1.3), 0.08, 0.25);
      }

      if (g.banner !== BANNER_NONE) {
        if (--g.bannerTicks <= 0) resetGarden(true);
      } else if (ready && valid) {
        grow(sig);
      }

      // La vida se ve en el suelo. Es otro canal que la calma a proposito:
      // si el pasto tambien se meciera, no se sabria cual de las dos se ve.
      g.vital += (g.health[Math.min(g.current, FLOWERS - 1)] / 100 - g.vital) * 0.03;

      // El polen nace en cero al cruzar el umbral y crece en cerca de un
      // segundo; al bajar del umbral se detiene en el acto.
      if (g.banner === BANNER_NONE && ready && valid && sig > UPPER) {
        g.pollenRate += ((sig - UPPER) / (100 - UPPER) - g.pollenRate) * 0.02;
        spawnPollen(g.pollenRate);
      } else {
        g.pollenRate = 0;
      }

      E.updateParticles(pollen, 0.0012);
      if (g.ticks % E.ANIM_TICKS === 0) g.animDirty = true;
      E.endTick();
    }

    function spawnPollen(rate) {
      if (rand() > 0.45 * rate) return;
      const i = g.current;
      const headY = BASE_Y - (10 + g.stage[i] * 11);
      const color = rand() < 0.5 ? R.petalGold[2] : PETAL_LIGHT[g.species[i]];
      E.spawnParticle(
        pollen,
        XS[i] + springs[i * 2] + (rand() - 0.5) * 12,
        headY + (rand() - 0.5) * 6,
        (rand() - 0.5) * 0.18,
        // Sube despacio: unos 4 a 11 pixeles logicos por segundo.
        -0.06 - rand() * 0.12,
        150 + rand() * 90,
        color
      );
    }

    /* ---------------------------------------------------------------- dibujo */

    function drawGround(f) {
      E.clearFrame(f, E.TRANSPARENT);
      // Pradera al fondo y cama de tierra al frente: el pasto da la vida y la
      // tierra conserva el contraste de los tallos, que tambien son verdes.
      for (let y = HORIZON; y < BED_TOP; y++) {
        const value = 0.4 + ((y - HORIZON) / (BED_TOP - HORIZON)) * 1.8;
        for (let x = 0; x < W; x++) {
          let v = E.ditherTone(R.grass, value, x, y);
          if (E.bayer(x * 3, y * 5) > 0.93 && y > HORIZON + 3) v = R.grass[2];
          f.px[y * W + x] = v;
        }
      }
      for (let y = BED_TOP; y < H; y++) {
        const value = 2 - ((y - BED_TOP) / (H - BED_TOP)) * 2;
        for (let x = 0; x < W; x++) {
          const edge = BED_TOP + Math.round(Math.sin(x * 0.07) * 1.5);
          if (y < edge) {
            f.px[y * W + x] = R.grass[1];
            continue;
          }
          f.px[y * W + x] = y - edge < 1 ? R.grass[0] : E.ditherTone(R.soil, value, x, y);
        }
      }
    }

    function drawSky(f) {
      // Mas calma, cielo mas tibio: el degradado sube hacia los tonos del sol.
      const warm = lerp(-0.9, 0.6, g.calm);
      const top = R.sky.length - 1;
      for (let y = 0; y < HORIZON; y++) {
        const value = (y / HORIZON) * top + warm;
        for (let x = 0; x < W; x++) f.px[y * W + x] = E.ditherTone(R.sky, value, x, y);
      }
    }

    /** Dibuja una flor en su sprite: tallo en dos tramos, hojas y cabeza. */
    function drawFlower(spr, species, stage, sway, sparkle) {
      E.clearFrame(spr, E.TRANSPARENT);
      const bx = SPR_BASE_X;
      const by = SPR_BASE_Y;

      if (stage === 0) {
        E.ellipse(spr, MAT.seed, 1, bx, by - 2, 3.2, 2.4, 0);
        E.selOut(spr, pal, INK, scratch);
        return;
      }

      const h = 10 + stage * 11;
      const topX = bx + sway;
      const topY = by - h;
      const midX = bx + sway * 0.45;
      const midY = by - h * 0.5;

      // Los dos tramos del tallo comparten pieza: sin grieta entre ellos.
      E.capsule(spr, MAT.stem, 1, bx, by, 1.9, midX, midY, 1.6);
      E.capsule(spr, MAT.stem, 1, midX, midY, 1.6, topX, topY, 1.2);

      if (stage >= 2) {
        E.ellipse(spr, MAT.leaf, 2, bx - 5 + sway * 0.2, by - h * 0.35, 5.5, 2.4, -0.5);
        E.ellipse(spr, MAT.leaf, 3, bx + 5 + sway * 0.35, by - h * 0.55, 5, 2.2, 0.55);
      }

      if (stage === 1) {
        E.ellipse(spr, MAT.leaf, 4, topX - 2, topY, 2.6, 1.3, -0.6);
        E.ellipse(spr, MAT.leaf, 5, topX + 2, topY, 2.6, 1.3, 0.6);
      } else if (stage === 2) {
        E.ellipse(spr, MAT.buds[species], 6, topX, topY, 2.4, 3.4, 0);
      } else {
        const full = stage >= STAGES;
        const n = full ? 9 : 2 + (stage - 2) * 2;
        const radius = full ? 8 : 3 + stage;
        const rx = full ? 5.5 : 2.6 + stage * 0.5;
        const ry = full ? 3.2 : 1.6 + stage * 0.25;
        for (let k = 0; k < n; k++) {
          const a = (k / n) * Math.PI * 2 + g.phase * 0.15;
          E.ellipse(
            spr, MAT.petals[species], 10 + k,
            topX + Math.cos(a) * radius, topY + Math.sin(a) * radius, rx, ry, a
          );
        }
        const c = full ? 4 : 2 + stage * 0.4;
        E.ellipse(spr, MAT.center, 30, topX, topY, c, c, 0);
      }

      E.selOut(spr, pal, INK, scratch);

      // Brillos de la flor completa, despues del contorno para no engordarlo.
      if (stage >= STAGES && sparkle) {
        for (let k = 0; k < 3; k++) {
          const a = g.phase * 0.8 + k * 2.1;
          E.pixel(spr, topX + Math.cos(a) * 13, topY - 4 + Math.sin(a * 1.3) * 7, WHITE);
        }
      }
    }

    /** Monticulo de un lugar que falta por sembrar. */
    function drawMound(spr) {
      E.clearFrame(spr, E.TRANSPARENT);
      E.ellipse(spr, MAT.mound, 1, SPR_BASE_X, SPR_BASE_Y, 5, 2.4, 0);
      // Tierra sobre tierra no se distingue: el contorno lo separa del suelo.
      E.selOut(spr, pal, INK, scratch);
    }

    function refreshSprites() {
      const sparkle = (g.ticks >> 4) & 1;
      for (let i = 0; i <= g.current && i < FLOWERS; i++) {
        drawFlower(sprites[i], g.species[i], g.stage[i], springs[i * 2], sparkle);
      }
      // Los monticulos no se mueven: se pintan solo cuando cambia la flor
      // actual, no en cada cuadro de animacion.
      if (g.moundsFor !== g.current) {
        for (let i = g.current + 1; i < FLOWERS; i++) drawMound(sprites[i]);
        g.moundsFor = g.current;
      }
      g.animDirty = false;
    }

    function shadowText(f, str, x, y, color) {
      E.text(f, str, x + 1, y + 1, INK);
      return E.text(f, str, x, y, color);
    }

    function bar(f, x, y, w, value, fill) {
      E.rect(f, x - 1, y - 1, w + 2, 5, INK);
      if (value === value) E.rect(f, x, y, Math.round((clamp(value, 0, 100) / 100) * w), 3, fill);
    }

    function drawHud(f) {
      const i = Math.min(g.current, FLOWERS - 1);

      // Flor actual.
      let x = shadowText(f, TXT.flor, 5, 5, LABEL) + 3;
      x = E.number(f, Math.min(g.done + 1, FLOWERS), x, 5, R.orange[2]);
      x = E.text(f, '/', x, 5, LABEL);
      E.number(f, FLOWERS, x, 5, LABEL);

      // Calma: la senal, continua, con los dos umbrales marcados.
      const cx = shadowText(f, TXT.calma, 5, 14, LABEL) + 3;
      const bw = 60;
      bar(f, cx, 15, bw, g.lastSignal, R.orange[1]);
      // Indice y no for...of: el iterador seria una alocacion por cuadro.
      for (let k = 0; k < THRESHOLDS.length; k++) {
        const tx = cx + Math.round((THRESHOLDS[k] / 100) * bw);
        E.pixel(f, tx, 13, LABEL);
        E.pixel(f, tx, 19, LABEL);
      }

      // Vida de la flor actual, a la derecha.
      const vw = 48;
      const vx = W - 5 - vw;
      shadowText(f, TXT.vida, vx - E.textWidth(TXT.vida) - 4, 5, LABEL);
      bar(f, vx, 6, vw, g.health[i], R.grass[2]);
    }

    function drawBanner(f) {
      const msg = g.banner === BANNER_DONE ? TXT.completo : TXT.marchita;
      const bw = E.textWidth(msg) + 14;
      const bx = (W - bw) >> 1;
      const by = 52;
      E.applyLUT(f, DARKEN, bx, by, bw, 15);
      E.rect(f, bx, by, bw, 1, R.orange[1]);
      E.rect(f, bx, by + 14, bw, 1, R.orange[1]);
      shadowText(f, msg, bx + 7, by + 5, LABEL);
    }

    function drawPollen(f) {
      for (let k = 0; k < pollen.count; k++) {
        const x = pollen.x[k] | 0;
        const y = pollen.y[k] | 0;
        const life = pollen.life[k] / pollen.maxLife[k];
        const age = pollen.maxLife[k] - pollen.life[k];
        // Aparece y se desvanece por tramado: no brota de golpe ni se apaga
        // de golpe.
        if (age < 20 && E.bayer(x, y) >= age / 20) continue;
        if (life < 0.33 && E.bayer(x, y) >= life / 0.33) continue;
        E.pixel(f, x, y, pollen.color[k]);
      }
    }

    /** Etapa del follaje segun la vida: 0 vivo, 1 apagado, 2 seco. */
    function foliageStage(life) {
      return life > 0.66 ? 0 : life > 0.36 ? 1 : 2;
    }

    /** Matorrales al fondo de la cama, detras de los tallos. */
    function drawBushes(f) {
      const v = g.vital;
      for (let k = 0; k < BUSHES; k++) {
        if (v < bushShow[k]) continue;
        const st = foliageStage(v + bushJitter[k]);
        E.blit(f, bushSprites[st * 2 + bushVariant[k]], bushX[k] - (BUSH_W >> 1), bushY[k] - BUSH_H);
      }
    }

    /** Matas y florecitas del suelo segun la vida suavizada. */
    function drawGroundLife(f) {
      const v = g.vital;
      for (let k = 0; k < TUFTS; k++) {
        if (v < tuftShow[k]) continue;
        const life = v + tuftJitter[k];
        // Verde y alto con vida; apagado; seco y corto.
        let body;
        let tip;
        let h;
        if (life > 0.66) {
          body = R.grass[1];
          tip = R.grass[2];
          h = 4;
        } else if (life > 0.36) {
          body = R.grass[0];
          tip = R.grass[1];
          h = 3;
        } else {
          // Seco: oliva con puntas de paja. Cafe sobre tierra no se distinguia.
          body = R.grass[0];
          tip = R.wood[2];
          h = 2;
        }
        const x = tuftX[k];
        const y = tuftY[k];
        // Hoja central y dos laterales que se abren.
        for (let j = 0; j < h; j++) E.pixel(f, x, y - j, j === h - 1 ? tip : body);
        E.pixel(f, x - 1, y, body);
        E.pixel(f, x + 1, y, body);
        if (h >= 3) {
          E.pixel(f, x - 2, y - 1, tip);
          E.pixel(f, x + 2, y - 1, tip);
        }
        // Florecita silvestre sobre la hoja central, solo con vida alta.
        if (life > tuftBloom[k]) {
          E.pixel(f, x, y - h, tuftColor[k]);
          if (life > tuftBloom[k] + 0.08) {
            E.pixel(f, x - 1, y - h, tuftColor[k]);
            E.pixel(f, x + 1, y - h, tuftColor[k]);
            E.pixel(f, x, y - h, R.orange[2]);
          }
        }
      }
    }

    function drawSheet(f) {
      // Hoja de sprites 1:1: las siete etapas de la especie actual.
      E.clearFrame(f, R.sky[3]);
      const species = g.species[Math.min(g.current, FLOWERS - 1)];
      for (let s = 0; s <= STAGES; s++) {
        drawFlower(sheetSprite, species, s, 0, 1);
        E.blit(f, sheetSprite, 2 + s * 33, 40);
        E.number(f, s, 2 + s * 33 + SPR_BASE_X - 1, 150, INK);
      }
    }

    function render(f) {
      if (g.sheet) {
        drawSheet(f);
        return;
      }
      E.clearFrame(f, INK);
      drawSky(f);
      if (backdropScene !== g.scene) {
        E.clearFrame(backdrop, E.TRANSPARENT);
        scenes[g.scene].draw(backdrop, HORIZON);
        backdropScene = g.scene;
      }
      E.blit(f, backdrop, 0, 0);
      E.blit(f, ground, 0, 0);

      drawBushes(f);
      if (g.animDirty) refreshSprites();
      // Flores y monticulos: cada uno en su sprite, ya pintado. El visitante
      // ve desde el inicio que son cinco lugares.
      for (let i = 0; i < FLOWERS; i++) {
        E.blit(f, sprites[i], XS[i] - SPR_BASE_X, BASE_Y - SPR_BASE_Y);
      }
      // Delante de los tallos: el pasto crece al pie de las flores.
      drawGroundLife(f);

      drawPollen(f);
      drawHud(f);
      if (g.banner !== BANNER_NONE) drawBanner(f);

      if (E.isStandalone()) {
        const x = shadowText(f, TXT.teclado, 5, H - 9, R.petalWhite[1]) + 3;
        E.number(f, g.devSignal, x, H - 9, R.orange[2]);
        if (g.grid) E.number(f, E.countColors(f, seen), W - 20, H - 9, LABEL);
      }
    }

    /** Region del acercamiento: la flor actual completa, sin recortarla. */
    function focus() {
      const i = Math.min(g.current, FLOWERS - 1);
      return { x: XS[i] - SPR_BASE_X, y: BASE_Y - SPR_BASE_Y, w: SPR_W, h: SPR_H };
    }

    return {
      get W() {
        return W;
      },
      H: H,
      MIN_W: MIN_W,
      MAX_W: MAX_W,
      setWidth: setWidth,
      palette: pal,
      backdropIndex: R.sky[0],
      state: g,
      tick: tick,
      render: render,
      focus: focus,
      resetGarden: resetGarden,
      nextScene: nextScene,
      sceneCount: scenes.length,
      // Observadores para las pruebas; no cambian el estado.
      swayOf: function (i) {
        return springs[i * 2];
      },
      pollenCount: function () {
        return pollen.count;
      },
      /** Matas visibles y florecitas abiertas con la vida actual. */
      groundCounts: function () {
        let tufts = 0;
        let blooms = 0;
        for (let k = 0; k < TUFTS; k++) {
          if (g.vital < tuftShow[k]) continue;
          tufts++;
          if (g.vital + tuftJitter[k] > tuftBloom[k]) blooms++;
        }
        let bushes = 0;
        let lush = 0;
        for (let k = 0; k < BUSHES; k++) {
          if (g.vital < bushShow[k]) continue;
          bushes++;
          if (foliageStage(g.vital + bushJitter[k]) === 0) lush++;
        }
        return { tufts: tufts, blooms: blooms, bushes: bushes, lush: lush };
      },
      get grid() {
        return g.grid;
      },
      get zoom() {
        return g.zoom;
      },
    };
  }

  const api = {
    createGame: createGame,
    KEYS_USED: KEYS_USED,
    MIN_W: MIN_W,
    MAX_W: MAX_W,
    H: H,
    STAGES: STAGES,
    FLOWERS: FLOWERS,
    UPPER: UPPER,
    LOWER: LOWER,
  };

  if (inNode) module.exports = api;
  else root.NDJardin = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

/* ============================================================================
   NeuroDAC · Carrera Neural

   Neurofeedback de atencion: la atencion suavizada fija la velocidad del
   coche, de forma continua. Gana quien cruce primero la meta; el rival avanza
   siempre igual, y para ganarle hay que sostener una atencion un poco por
   encima de la zona neutral de eSense (40 a 60, segun NeuroSky).

   La atencion se ve en tres canales: la velocidad del asfalto, las lineas de
   velocidad y el escape del coche. La barra del marcador marca a partir de
   donde se va mas rapido que el rival.

   Corre en el navegador y en Node: la logica no toca el DOM. El protocolo con
   la aplicacion esta en docs/contrato-juegos.md.
   ========================================================================== */

(function (root) {
  'use strict';

  const inNode = typeof module !== 'undefined' && module.exports;
  const E = inNode ? require('./engine.js') : root.NDEngine;
  const PAL = inNode ? require('./palette.js') : root.NDPalette;
  const TEXTOS = inNode ? require('./textos.js') : root.NDTextos;

  /** Teclas que el juego atiende dentro de la aplicacion: los carriles. W y S
   *  simulan la senal solo con el juego abierto fuera de ella. Debe coincidir
   *  con GameSpec.keys en pages/carrera.py. */
  const KEYS_USED = ['ArrowLeft', 'ArrowRight'];

  /** Resolucion logica: el juego llena su recuadro en ambos ejes. Con la
   *  ventana mas alta se ve mas carretera por delante. Debe coincidir con
   *  GameSpec en pages/carrera.py. */
  const MIN_W = 144;
  const MAX_W = 176;
  const MIN_H = 192;
  const MAX_H = 288;

  /* ----------------------------------------------- mecanica: para afinar */
  /** Velocidades en m/s. */
  const V_MIN = 8;
  const V_MAX = 55;
  const GHOST_V = 28;
  /** Atencion suavizada que da V_MIN y V_MAX; en medio, proporcional. */
  const ATT_LOW = 35;
  const ATT_HIGH = 85;
  /** Suavizado de la atencion por tick: constante de tiempo de ~1.4 s. */
  const ATT_SMOOTH = 0.012;
  const FINISH_M = 1000;
  /** Un choque resta velocidad, que se recupera a RECOVER m/s por segundo. */
  const CRASH = 14;
  const RECOVER = 6;
  /** Separacion entre obstaculos, en metros. */
  const OBST_MIN_M = 22;
  const OBST_MAX_M = 40;
  /** Atencion a partir de la cual se va mas rapido que el rival. */
  const ATT_GHOST = ATT_LOW + ((GHOST_V - V_MIN) / (V_MAX - V_MIN)) * (ATT_HIGH - ATT_LOW);

  /* --------------------------------------------------------------- dibujo */
  const PX_PER_M = 3;
  const LANES = 3;
  const LANE_W = 34;
  const ROAD_W = LANES * LANE_W + 4;
  const CAR_W = 14;
  const CAR_H = 24;
  const RESULT_TICKS = 360;

  const RACING = 0;
  const RESULT_WIN = 1;
  const RESULT_SECOND = 2;

  const OB_CAP = 32;
  const SC_CAP = 64;

  /** Paisajes: bosque de pinos, desierto con magueyes y nopales, pueblo. */
  const SCENERY_COUNT = 3;

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

  /** Siguiente paisaje sin repetir el inmediato anterior. */
  function pickNext(count, previous, rand) {
    let i = Math.floor(rand() * (count - 1));
    if (i >= previous) i++;
    return i;
  }

  /** Velocidad que corresponde a una atencion suavizada, sin choques. */
  function speedFor(att) {
    return V_MIN + (V_MAX - V_MIN) * clamp((att - ATT_LOW) / (ATT_HIGH - ATT_LOW), 0, 1);
  }

  function createGame(options) {
    const o = options || {};
    const rand = mulberry32(o.seed === undefined ? Date.now() >>> 0 : o.seed);
    let W = clamp(o.width === undefined ? MIN_W : o.width | 0, MIN_W, MAX_W);
    let H = clamp(o.height === undefined ? MIN_H : o.height | 0, MIN_H, MAX_H);

    const pal = E.createPalette(PAL.SPEC);
    const R = pal.ramps;
    const INK = R.ink[0];
    const WHITE = R.white[0];
    const LABEL = R.petalWhite[2];
    const TXT = TEXTOS.carrera;
    const DARKEN = E.rampShiftLUT(pal, -2);
    const SAND = new Uint8Array([R.wood[2], R.orange[0], R.orange[2]]);

    /* ------------------------------------------------- sprites, una vez */

    const scratchBig = new Uint8Array(32 * 32);
    function sprite(w, h, paint, outline) {
      const spr = E.createFrame(w, h);
      paint(spr);
      if (outline) E.selOut(spr, pal, INK, scratchBig);
      return spr;
    }

    function car(body, roof) {
      const spr = sprite(CAR_W, CAR_H, function (s) {
        // Llantas por fuera de la carroceria: desde arriba son lo que dice
        // "coche". Con la carroceria mas ancha quedaban tapadas.
        E.rect(s, 0, 4, 2, 5, INK);
        E.rect(s, 12, 4, 2, 5, INK);
        E.rect(s, 0, 15, 2, 5, INK);
        E.rect(s, 12, 15, 2, 5, INK);
        E.capsule(s, body, 1, 7, 5, 4.8, 7, 19, 4.8);
      }, true);
      // Parabrisas, techo, medallon, faros y calaveras, sobre el contorno.
      E.rect(spr, 4, 6, 6, 3, R.petalWhite[1]);
      E.rect(spr, 4, 9, 6, 6, roof);
      E.rect(spr, 4, 15, 6, 2, R.petalWhite[0]);
      E.pixel(spr, 4, 1, R.petalGold[2]);
      E.pixel(spr, 9, 1, R.petalGold[2]);
      E.pixel(spr, 4, 22, R.red[1]);
      E.pixel(spr, 9, 22, R.red[1]);
      return spr;
    }

    const MAT = {
      player: E.material(R.celeste, { spec: 0.06, specIndex: WHITE }),
      ghost: E.material(R.asphalt),
      cone: E.material(R.orange, { spec: 0.05, specIndex: WHITE }),
      barrel: E.material(R.red, { spec: 0.05, specIndex: WHITE }),
      hole: E.material(R.asphalt),
      pine: E.material(R.foliage),
      agave: E.material(R.foliage, { baseTone: 1 }),
      nopal: E.material(R.foliage, { baseTone: 1 }),
      rock: E.material(R.petalWhite),
    };

    const playerSprite = car(MAT.player, R.celeste[0]);
    const ghostSprite = car(MAT.ghost, R.asphalt[0]);

    // Obstaculos vistos desde arriba: cono, barril, bache.
    const obstacleSprites = [
      sprite(11, 11, function (s) {
        E.ellipse(s, MAT.cone, 1, 5.5, 5.5, 4.6, 4.6, 0);
        E.ring(s, MAT.rock, 2, 5.5, 5.5, 2.6, 2.6, 1.1);
      }, true),
      sprite(13, 13, function (s) {
        E.ellipse(s, MAT.barrel, 1, 6.5, 6.5, 5.6, 5.6, 0);
        E.ring(s, E.material(R.red), 2, 6.5, 6.5, 3.4, 3.4, 1);
      }, true),
      sprite(16, 9, function (s) {
        E.ellipse(s, MAT.hole, 1, 8, 4.5, 7, 3.6, 0);
        E.ellipse(s, E.material(R.ink), 2, 8.5, 5, 4.5, 2.2, 0);
      }, false),
    ];
    const OB_HALF = new Uint8Array([5, 6, 4]);

    // Paisaje visto desde arriba.
    const pineSprite = sprite(16, 16, function (s) {
      E.ellipse(s, MAT.pine, 1, 8, 8, 7, 7, 0);
      E.ellipse(s, E.material(R.foliage, { baseTone: 1 }), 2, 6.5, 6.5, 3.6, 3.6, 0);
    }, true);
    const rockSprite = sprite(8, 6, function (s) {
      E.ellipse(s, MAT.rock, 1, 4, 3, 3.4, 2.4, 0);
    }, true);
    const agaveSprite = sprite(17, 17, function (s) {
      // Maguey: roseta de pencas que abren desde el centro.
      for (let k = 0; k < 8; k++) {
        const a = (k / 8) * Math.PI * 2 + 0.2;
        E.capsule(s, MAT.agave, 1, 8.5, 8.5, 1.6, 8.5 + Math.cos(a) * 7, 8.5 + Math.sin(a) * 7, 0.6);
      }
    }, true);
    for (let k = 0; k < 8; k++) {
      const a = (k / 8) * Math.PI * 2 + 0.2;
      E.pixel(agaveSprite, 8.5 + Math.cos(a) * 7, 8.5 + Math.sin(a) * 7, R.petalGold[0]);
    }
    const nopalSprite = sprite(15, 13, function (s) {
      // Nopal: pencas ovaladas con espinas y una tuna.
      E.ellipse(s, MAT.nopal, 1, 7, 8, 4.4, 3.2, 0.3);
      E.ellipse(s, MAT.nopal, 2, 4.5, 4.5, 3.4, 2.4, -0.6);
      E.ellipse(s, MAT.nopal, 3, 10.5, 4, 3.2, 2.3, 0.7);
    }, true);
    E.pixel(nopalSprite, 6, 7, R.petalWhite[2]);
    E.pixel(nopalSprite, 9, 9, R.petalWhite[2]);
    E.pixel(nopalSprite, 4, 4, R.petalWhite[2]);
    E.pixel(nopalSprite, 11, 2, R.red[1]);

    // Casitas de pueblo vistas desde arriba: tejado de teja y fachada de color.
    const WALLS = [R.petalRose[1], R.petalGold[1], R.petalBlue[1], R.petalViolet[1]];
    const houseSprites = WALLS.map(function (wall) {
      return sprite(20, 18, function (s) {
        for (let y = 0; y < 13; y++) {
          for (let x = 0; x < 20; x++) {
            // Teja: hileras alternas con juntas verticales.
            const joint = (x + ((y >> 1) & 1) * 2) % 4 === 0;
            E.pixel(s, x, y, joint ? R.red[0] : (y & 1) === 0 ? R.red[1] : R.red[2]);
          }
        }
        E.rect(s, 0, 6, 20, 1, R.red[0]); // cumbrera
        E.rect(s, 0, 13, 20, 5, wall);
        E.rect(s, 8, 14, 4, 4, R.wood[1]); // puerta
        E.pixel(s, 3, 15, R.celeste[2]);
        E.pixel(s, 16, 15, R.celeste[2]);
      }, true);
    });

    // Lista de la hoja de sprites, armada una vez.
    const SHEET = [playerSprite, ghostSprite].concat(
      obstacleSprites,
      [pineSprite, rockSprite, agaveSprite, nopalSprite],
      houseSprites
    );

    /* ------------------------------------------------------ estado */

    const ob = {
      m: new Float32Array(OB_CAP),
      lane: new Uint8Array(OB_CAP),
      kind: new Uint8Array(OB_CAP),
      count: 0,
    };
    const sc = {
      m: new Float32Array(SC_CAP),
      x: new Int16Array(SC_CAP),
      kind: new Uint8Array(SC_CAP),
      count: 0,
    };
    const exhaust = E.createParticles(80);
    const seen = new Uint8Array(256);

    const g = {
      ticks: 0,
      state: RACING,
      resultTicks: 0,
      scenery: Math.floor(rand() * SCENERY_COUNT),
      dist: 0,
      ghost: 0,
      ghostFinished: false,
      att: 50,
      penalty: 0,
      lane: 1,
      carX: 0,
      crashFlash: 0,
      crashes: 0,
      nextObstacle: 40,
      nextScenery: new Float32Array(2),
      devSignal: 50,
      lastSignal: NaN,
      playTicks: 0,
      lastSeconds: -1,
      bestSeconds: -1,
      grid: false,
      zoom: false,
      sheet: false,
    };

    function roadX0() {
      return (W - ROAD_W) >> 1;
    }

    function laneCenter(i) {
      return roadX0() + 2 + i * LANE_W + (LANE_W >> 1);
    }

    function playerY() {
      return H - CAR_H - 8;
    }

    /** Metros visibles por delante del coche. */
    function aheadM() {
      return (playerY() + 40) / PX_PER_M;
    }

    function resetRace(newScenery) {
      g.state = RACING;
      g.resultTicks = 0;
      g.dist = 0;
      g.ghost = 0;
      g.ghostFinished = false;
      g.penalty = 0;
      g.lane = 1;
      g.carX = laneCenter(1);
      g.crashFlash = 0;
      g.crashes = 0;
      g.nextObstacle = 40;
      g.playTicks = 0;
      ob.count = 0;
      exhaust.count = 0;
      setScenery(newScenery ? pickNext(SCENERY_COUNT, g.scenery, rand) : g.scenery);
    }

    /** Cambia el paisaje y repuebla los acotamientos desde donde va el coche. */
    function setScenery(index) {
      g.scenery = clamp(index | 0, 0, SCENERY_COUNT - 1);
      sc.count = 0;
      g.nextScenery[0] = g.dist - (H - playerY() + 20) / PX_PER_M;
      g.nextScenery[1] = g.nextScenery[0] + 6;
      fillScenery();
    }

    function setSize(width, height) {
      const nw = clamp(width | 0, MIN_W, MAX_W);
      const nh = clamp(height | 0, MIN_H, MAX_H);
      if (nw === W && nh === H) return;
      W = nw;
      H = nh;
      g.carX = laneCenter(g.lane);
      fillScenery();
    }

    /* --------------------------------------------------- paisaje */

    function sceneryStep() {
      if (g.scenery === 2) return 7 + rand() * 2;
      if (g.scenery === 1) return 16 + rand() * 18;
      return 12 + rand() * 14;
    }

    /** Agrega paisaje hasta cubrir lo visible por delante. */
    function fillScenery() {
      const limit = g.dist + aheadM() + 10;
      for (let side = 0; side < 2; side++) {
        while (g.nextScenery[side] < limit && sc.count < SC_CAP) {
          const i = sc.count++;
          sc.m[i] = g.nextScenery[side];
          const shoulder = roadX0();
          const cx = side === 0 ? shoulder >> 1 : W - (shoulder >> 1);
          sc.x[i] = cx + Math.round((rand() - 0.5) * Math.max(0, shoulder - 18));
          let kind;
          if (g.scenery === 0) kind = rand() < 0.8 ? 0 : 1; // pino o roca
          else if (g.scenery === 1) kind = rand() < 0.55 ? 2 : 3; // maguey o nopal
          else kind = 4 + Math.floor(rand() * WALLS.length); // casita
          sc.kind[i] = kind;
          g.nextScenery[side] += sceneryStep();
        }
      }
    }

    function sceneryCull() {
      const behind = g.dist - (H - playerY() + 20) / PX_PER_M;
      let i = 0;
      while (i < sc.count) {
        if (sc.m[i] < behind) {
          const last = --sc.count;
          sc.m[i] = sc.m[last];
          sc.x[i] = sc.x[last];
          sc.kind[i] = sc.kind[last];
          continue;
        }
        i++;
      }
    }

    /* ------------------------------------------------------- tick */

    function currentSpeed() {
      return Math.max(V_MIN * 0.5, speedFor(g.att) - g.penalty);
    }

    function tick() {
      g.ticks++;
      const standalone = E.isStandalone();
      const input = E.input;
      const K = E.KEY;

      let sig;
      if (standalone) {
        if (input.pressed[K.w]) g.devSignal = Math.min(100, g.devSignal + 10);
        if (input.pressed[K.s]) g.devSignal = Math.max(0, g.devSignal - 10);
        if (input.pressed[K.grid]) g.grid = !g.grid;
        if (input.pressed[K.zoom]) g.zoom = !g.zoom;
        if (input.pressed[K.sheet]) g.sheet = !g.sheet;
        if (input.pressed[K.scene]) setScenery((g.scenery + 1) % SCENERY_COUNT);
        sig = g.devSignal;
      } else {
        // Las herramientas del personal no existen en modo publico, y W y S
        // no tocan la senal: lo mostrado aparentaria ser atencion sin serlo.
        g.grid = false;
        g.zoom = false;
        g.sheet = false;
        sig = input.signal;
      }
      g.lastSignal = sig;
      const valid = sig === sig;
      const running = g.state === RACING && E.isReady() && valid;

      // Los carriles son jugabilidad: responden dentro y fuera de la app,
      // pero solo mientras la carrera corre.
      if (running) {
        if (input.pressed[K.left]) g.lane = Math.max(0, g.lane - 1);
        if (input.pressed[K.right]) g.lane = Math.min(LANES - 1, g.lane + 1);
      }
      // El coche se desliza al carril: un cambio se ve, no se teletransporta.
      const target = laneCenter(g.lane);
      g.carX += (target - g.carX) * 0.25;
      if (Math.abs(target - g.carX) < 0.3) g.carX = target;

      if (valid) g.att += (sig - g.att) * ATT_SMOOTH;

      if (g.state !== RACING) {
        if (--g.resultTicks <= 0) resetRace(true);
      } else if (running) {
        race();
      }

      updateExhaust(running);
      if (g.crashFlash > 0) g.crashFlash--;
      E.endTick();
    }

    function race() {
      g.playTicks++;
      g.penalty = Math.max(0, g.penalty - RECOVER / 60);
      g.dist += currentSpeed() / 60;
      if (!g.ghostFinished) {
        g.ghost = Math.min(FINISH_M, g.ghost + GHOST_V / 60);
        g.ghostFinished = g.ghost >= FINISH_M;
      }

      // Obstaculos por delante, uno por fila: nunca se bloquean los tres
      // carriles a la vez.
      while (g.nextObstacle < g.dist + aheadM() && g.nextObstacle < FINISH_M - 20) {
        if (ob.count < OB_CAP) {
          const i = ob.count++;
          ob.m[i] = g.nextObstacle;
          ob.lane[i] = Math.floor(rand() * LANES);
          ob.kind[i] = Math.floor(rand() * obstacleSprites.length);
        }
        g.nextObstacle += OBST_MIN_M + rand() * (OBST_MAX_M - OBST_MIN_M);
      }

      // Choques: mismo carril y a menos de medio coche.
      const lane = nearestLane();
      let i = 0;
      while (i < ob.count) {
        const dy = (ob.m[i] - g.dist) * PX_PER_M;
        const reach = (CAR_H >> 1) + OB_HALF[ob.kind[i]];
        const hit = ob.lane[i] === lane && dy < reach && dy > -reach;
        if (hit || dy < -(H - playerY() + 20)) {
          if (hit) {
            g.penalty += CRASH;
            g.crashFlash = 30;
            g.crashes++;
          }
          const last = --ob.count;
          ob.m[i] = ob.m[last];
          ob.lane[i] = ob.lane[last];
          ob.kind[i] = ob.kind[last];
          continue;
        }
        i++;
      }

      fillScenery();
      sceneryCull();

      if (g.dist >= FINISH_M) {
        g.state = g.ghostFinished ? RESULT_SECOND : RESULT_WIN;
        g.resultTicks = RESULT_TICKS;
        g.lastSeconds = Math.floor(g.playTicks / 60);
        if (g.bestSeconds < 0 || g.lastSeconds < g.bestSeconds) g.bestSeconds = g.lastSeconds;
      }
    }

    function nearestLane() {
      let best = 0;
      let bestD = 1e9;
      for (let i = 0; i < LANES; i++) {
        const d = Math.abs(laneCenter(i) - g.carX);
        if (d < bestD) {
          bestD = d;
          best = i;
        }
      }
      return best;
    }

    function updateExhaust(running) {
      if (running) {
        // El escape tambien dice la atencion: mas chispas y mas calientes.
        const f = clamp((g.att - ATT_LOW) / (ATT_HIGH - ATT_LOW), 0, 1);
        if (rand() < 0.25 + 0.6 * f) {
          const hot = rand() < f;
          E.spawnParticle(
            exhaust,
            g.carX + (rand() - 0.5) * 6,
            playerY() + CAR_H - 1,
            (rand() - 0.5) * 0.3,
            0.5 + rand() * 0.6 + f * 0.8,
            14 + rand() * 18,
            hot ? (rand() < 0.5 ? R.orange[2] : R.petalGold[2]) : R.petalWhite[0]
          );
        }
      }
      E.updateParticles(exhaust, 0);
    }

    /* ----------------------------------------------------- dibujo */

    function worldRow(y) {
      // Fila del mundo bajo la fila de pantalla y: el asfalto y las rayas
      // se anclan al mundo, asi que su tramado se desliza con la velocidad.
      return ((g.dist * PX_PER_M) | 0) + (playerY() - y);
    }

    function drawGround(f) {
      const x0 = roadX0();
      const x1 = x0 + ROAD_W;
      for (let y = 0; y < H; y++) {
        const row = worldRow(y);
        let j = y * W;
        for (let x = 0; x < W; x++, j++) {
          if (x >= x0 && x < x1) {
            f.px[j] = E.ditherTone(R.asphalt, 1.35, x, row);
          } else if (g.scenery === 1) {
            f.px[j] = E.ditherTone(SAND, 1.6, x, row);
          } else if (g.scenery === 2) {
            // Banqueta de losas.
            const joint = (row & 7) === 0 || (x & 7) === 0;
            f.px[j] = joint ? R.petalWhite[0] : R.petalWhite[1];
          } else {
            f.px[j] = E.ditherTone(R.grass, 1.1, x, row);
          }
        }
      }
    }

    function drawRoadMarks(f) {
      const x0 = roadX0();
      // Orillas continuas.
      E.rect(f, x0, 0, 2, H, R.petalWhite[2]);
      E.rect(f, x0 + ROAD_W - 2, 0, 2, H, R.petalWhite[2]);
      // Rayas de carril: 8 pixeles de raya y 8 de hueco, ancladas al mundo.
      for (let k = 1; k < LANES; k++) {
        const x = x0 + 2 + k * LANE_W - 1;
        for (let y = 0; y < H; y++) {
          if ((worldRow(y) & 15) < 8) E.rect(f, x, y, 2, 1, R.petalWhite[1]);
        }
      }
    }

    function drawSpeedLines(f) {
      // Lineas de velocidad: mas largas y mas visibles cuanto mas rapido.
      const v = currentSpeed();
      const len = (2 + v * 0.25) | 0;
      const strength = clamp((v - V_MIN) / (V_MAX - V_MIN), 0, 1);
      const x0 = roadX0();
      for (let k = 0; k < 9; k++) {
        const x = x0 + 5 + ((k * 37) % (ROAD_W - 10));
        const y0 = ((worldRow(0) + k * 53) % H + H) % H;
        for (let t = 0; t < len; t++) {
          const y = (y0 + t) % H;
          // Gris claro: el tono del asfalto sobre asfalto no se leia.
          if (E.bayer(x, y) < strength * 0.7) E.pixel(f, x, y, R.petalWhite[0]);
        }
      }
    }

    function screenY(m) {
      return (playerY() - (m - g.dist) * PX_PER_M) | 0;
    }

    function drawScenery(f) {
      for (let i = 0; i < sc.count; i++) {
        const k = sc.kind[i];
        const spr =
          k === 0 ? pineSprite
            : k === 1 ? rockSprite
              : k === 2 ? agaveSprite
                : k === 3 ? nopalSprite
                  : houseSprites[k - 4];
        E.blit(f, spr, sc.x[i] - (spr.w >> 1), screenY(sc.m[i]) - (spr.h >> 1));
      }
    }

    function drawFinish(f) {
      const y = screenY(FINISH_M);
      if (y < -8 || y > H) return;
      const x0 = roadX0();
      // Bandera a cuadros de lado a lado del camino.
      for (let r = 0; r < 2; r++) {
        for (let c = 0; c < ROAD_W; c += 4) {
          const light = ((c >> 2) + r) & 1;
          E.rect(f, x0 + c, y + r * 4, 4, 4, light ? R.petalWhite[2] : INK);
        }
      }
    }

    function drawObstacles(f) {
      for (let i = 0; i < ob.count; i++) {
        const spr = obstacleSprites[ob.kind[i]];
        E.blit(f, spr, laneCenter(ob.lane[i]) - (spr.w >> 1), screenY(ob.m[i]) - (spr.h >> 1));
      }
    }

    function drawCars(f) {
      // El rival, translucido: no choca y no se confunde con el jugador.
      const gy = screenY(g.ghost) - (CAR_H >> 1);
      if (gy > -CAR_H && gy < H) E.blit(f, ghostSprite, laneCenter(2) - (CAR_W >> 1), gy, 0.5);
      for (let k = 0; k < exhaust.count; k++) {
        const life = exhaust.life[k] / exhaust.maxLife[k];
        const x = exhaust.x[k] | 0;
        const y = exhaust.y[k] | 0;
        if (life < 0.4 && E.bayer(x, y) >= life / 0.4) continue;
        E.pixel(f, x, y, exhaust.color[k]);
      }
      // Tras un choque el coche parpadea.
      if (!(g.crashFlash > 0 && (g.crashFlash >> 2) & 1)) {
        E.blit(f, playerSprite, (g.carX | 0) - (CAR_W >> 1), playerY());
      }
    }

    function shadowText(f, str, x, y, color) {
      E.text(f, str, x + 1, y + 1, INK);
      return E.text(f, str, x, y, color);
    }

    function drawHud(f) {
      // Franja oscura para que el marcador se lea sobre cualquier paisaje.
      E.applyLUT(f, DARKEN, 0, 0, W, 24);

      // Atencion: continua, con la raya del rival.
      const ax = shadowText(f, TXT.atencion, 4, 3, LABEL) + 3;
      const aw = W - ax - 4;
      E.rect(f, ax - 1, 3, aw + 2, 5, INK);
      E.rect(f, ax, 4, Math.round((clamp(g.att, 0, 100) / 100) * aw), 3, R.orange[1]);
      const gx = ax + Math.round((ATT_GHOST / 100) * aw);
      E.rect(f, gx, 2, 1, 7, LABEL);

      // Reloj del reto en la franja, a la derecha. El mejor de la sesion va en
      // el aviso final: a 144 columnas no cabe otra fila sin tapar camino.
      const t = Math.floor(g.playTicks / 60);
      const cw = E.clockWidth(t);
      const tx = W - 4 - cw;
      E.clock(f, t, tx + 1, 13, INK);
      E.clock(f, t, tx, 12, R.orange[2]);

      // Avance hacia la meta: el jugador y el rival sobre la misma pista.
      const mx = shadowText(f, TXT.meta, 4, 12, LABEL) + 3;
      const mw = tx - mx - 5;
      E.rect(f, mx - 1, 12, mw + 2, 5, INK);
      const px = mx + Math.round((clamp(g.dist, 0, FINISH_M) / FINISH_M) * (mw - 1));
      const hx = mx + Math.round((g.ghost / FINISH_M) * (mw - 1));
      E.rect(f, hx, 13, 1, 3, R.asphalt[2]);
      E.rect(f, px - 1, 13, 3, 3, R.celeste[2]);
      E.rect(f, mx + mw - 1, 12, 1, 5, R.petalWhite[2]);

    }

    function drawResult(f) {
      const msg = g.state === RESULT_WIN ? TXT.gano : TXT.segundo;
      const showBest = g.bestSeconds >= 0 && g.bestSeconds < g.lastSeconds;
      const lines = showBest ? 3 : 2;
      const timeW = E.textWidth(TXT.tiempo) + 4 + E.clockWidth(g.lastSeconds);
      const bestW = E.textWidth(TXT.mejor) + 4 + E.clockWidth(g.bestSeconds);
      const bw = Math.min(W - 6, Math.max(E.textWidth(msg), timeW, showBest ? bestW : 0) + 14);
      const bh = 6 + lines * 9;
      const bx = (W - bw) >> 1;
      const by = (H >> 1) - 24;
      E.applyLUT(f, DARKEN, bx, by, bw, bh);
      E.applyLUT(f, DARKEN, bx, by, bw, bh);
      const accent = g.state === RESULT_WIN ? R.orange[1] : R.asphalt[2];
      E.rect(f, bx, by, bw, 1, accent);
      E.rect(f, bx, by + bh - 1, bw, 1, accent);
      shadowText(f, msg, (W - E.textWidth(msg)) >> 1, by + 5, LABEL);
      let x = shadowText(f, TXT.tiempo, (W - timeW) >> 1, by + 14, LABEL) + 3;
      E.clock(f, g.lastSeconds, x + 1, by + 15, INK);
      E.clock(f, g.lastSeconds, x, by + 14, R.orange[2]);
      if (showBest) {
        x = shadowText(f, TXT.mejor, (W - bestW) >> 1, by + 23, R.petalWhite[1]) + 3;
        E.clock(f, g.bestSeconds, x, by + 23, R.petalWhite[1]);
      }
    }

    function drawSheet(f) {
      // Hoja de sprites 1:1, para revisar cada pieza a tamano real.
      E.clearFrame(f, R.sky[3]);
      const all = SHEET;
      let x = 3;
      let y = 30;
      for (let k = 0; k < all.length; k++) {
        if (x + all[k].w > W - 3) {
          x = 3;
          y += 30;
        }
        E.blit(f, all[k], x, y);
        x += all[k].w + 4;
      }
    }

    function render(f) {
      if (g.sheet) {
        drawSheet(f);
        return;
      }
      drawGround(f);
      drawScenery(f);
      drawRoadMarks(f);
      drawSpeedLines(f);
      drawFinish(f);
      drawObstacles(f);
      drawCars(f);
      drawHud(f);
      if (g.state !== RACING) drawResult(f);

      if (E.isStandalone()) {
        const x = shadowText(f, TXT.teclado, 4, H - 9, R.petalWhite[2]) + 3;
        E.number(f, g.devSignal, x, H - 9, R.orange[2]);
        if (g.grid) E.number(f, E.countColors(f, seen), W - 14, H - 18, LABEL);
      }
    }

    function focus() {
      return { x: Math.max(0, (g.carX | 0) - 20), y: Math.max(0, playerY() - 40), w: 40, h: 72 };
    }

    resetRace(false);
    g.carX = laneCenter(1);

    return {
      get W() {
        return W;
      },
      get H() {
        return H;
      },
      MIN_W: MIN_W,
      MAX_W: MAX_W,
      MIN_H: MIN_H,
      MAX_H: MAX_H,
      palette: pal,
      backdropIndex: INK,
      state: g,
      tick: tick,
      render: render,
      focus: focus,
      setSize: setSize,
      setScenery: setScenery,
      resetRace: resetRace,
      // Observadores para las pruebas; no cambian el estado.
      speed: currentSpeed,
      nearestLane: nearestLane,
      obstacleCount: function () {
        return ob.count;
      },
      /** Vista de solo lectura de los obstaculos, para el bot de pruebas. */
      obstacleView: function () {
        return ob;
      },
      sceneryCount: function () {
        return sc.count;
      },
      exhaustCount: function () {
        return exhaust.count;
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
    speedFor: speedFor,
    KEYS_USED: KEYS_USED,
    MIN_W: MIN_W,
    MAX_W: MAX_W,
    MIN_H: MIN_H,
    MAX_H: MAX_H,
    V_MIN: V_MIN,
    V_MAX: V_MAX,
    GHOST_V: GHOST_V,
    FINISH_M: FINISH_M,
    ATT_GHOST: ATT_GHOST,
    SCENERY_COUNT: SCENERY_COUNT,
  };

  if (inNode) module.exports = api;
  else root.NDCarrera = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

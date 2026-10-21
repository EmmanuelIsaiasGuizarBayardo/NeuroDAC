/* Verifica Carrera Neural sin navegador y vuelca capturas.

   Uso:
       node tools/capturas_carrera.js [carpeta_salida]

   La salida por defecto es results/capturas, que el .gitignore ya excluye.
   Para medir tambien la alocacion por cuadro:

       node --expose-gc --min-semi-space-size=256 --max-semi-space-size=256 \
            tools/capturas_carrera.js

   Un bot juega carreras completas mandando los cambios de carril por el
   puente, como la pagina. El arnes falla si la compuerta no detiene la
   carrera, si mas atencion no lleva mas rapido a la meta, si el reloj cuenta
   pausas, si W y S alteran la senal dentro de la aplicacion o si algun pixel
   sale de la paleta. */

'use strict';

const fs = require('fs');
const path = require('path');
const { writePNG, upscale } = require('./png.js');

const OUT = process.argv[2] || path.join('results', 'capturas');
const ENGINE = path.resolve(__dirname, '..', 'assets', 'games', 'engine.js');
const CARRERA = path.resolve(__dirname, '..', 'assets', 'games', 'carrera.js');
const SCALE = 3;

const fallas = [];
function check(cond, mensaje) {
  if (!cond) fallas.push(mensaje);
  return cond;
}

function fresh(embedded, seed, width, height) {
  delete require.cache[ENGINE];
  delete require.cache[CARRERA];
  const E = require(ENGINE);
  const C = require(CARRERA);
  E.setEmbedded(embedded);
  const game = C.createGame({ seed: seed === undefined ? 7 : seed, width: width || 160, height: height || 240 });
  return { E, C, game, frame: E.createFrame(game.W, game.H, 0) };
}

function bridge(E, signalValue, ready, theme) {
  E.receive({ source: 'neurodac', signalValue, ready, theme: theme || 'dark' }, 0);
}

/** Bot: si hay un obstaculo cerca en su carril, cambia a uno libre. Mira
 *  por delante en proporcion a su velocidad, como una persona atenta: con
 *  una ventana fija, a 70 m/s ya no alcanza a cruzar el carril. */
function drive(ctx) {
  const g = ctx.game.state;
  const ob = ctx.game.obstacleView();
  const threat = [false, false, false];
  const window = Math.max(26, ctx.game.speed() * 0.65);
  for (let i = 0; i < ob.count; i++) {
    const ahead = ob.m[i] - g.dist;
    if (ahead > -3 && ahead < window) threat[ob.lane[i]] = true;
  }
  const lane = g.lane;
  if (!threat[lane]) return;
  let key = null;
  if (lane > 0 && !threat[lane - 1]) key = 'ArrowLeft';
  else if (lane < 2 && !threat[lane + 1]) key = 'ArrowRight';
  else if (lane === 1) key = threat[0] ? 'ArrowRight' : 'ArrowLeft';
  if (key) {
    ctx.E.receive({ source: 'neurodac', keydown: key }, 0);
    ctx.E.receive({ source: 'neurodac', keyup: key }, 0);
  }
}

function run(ctx, ticks, signalValue, ready, opts) {
  const o = opts || {};
  for (let i = 0; i < ticks; i++) {
    bridge(ctx.E, signalValue, ready, o.theme);
    if (o.bot) drive(ctx);
    ctx.game.tick();
    if (o.until && o.until()) return i + 1;
  }
  return ticks;
}

const capturas = [];
function capture(ctx, nombre, theme) {
  ctx.game.render(ctx.frame);
  const pal = ctx.game.palette;
  let fuera = 0;
  for (let i = 0; i < ctx.frame.px.length; i++) if (ctx.frame.px[i] >= pal.count) fuera++;
  const distintos = ctx.E.countColors(ctx.frame, new Uint8Array(256));
  check(fuera === 0, `${nombre}: ${fuera} pixeles fuera de la paleta`);
  check(distintos <= pal.count, `${nombre}: ${distintos} colores`);
  writePNG(
    path.join(OUT, `${nombre}.png`),
    ctx.game.W * SCALE, ctx.game.H * SCALE,
    upscale(ctx.frame.px, ctx.game.W, ctx.game.H, SCALE),
    pal.rgb[theme || 'dark'], pal.count
  );
  capturas.push({ nombre, distintos, fuera });
}

/** Carrera completa con bot; devuelve el resultado y el tiempo. */
function race(ctx, signalValue, theme) {
  const g = ctx.game.state;
  run(ctx, 60 * 300, signalValue, true, { bot: true, theme, until: () => g.state !== 0 });
  return { result: g.state, seconds: g.lastSeconds, ticks: g.playTicks, crashes: g.crashes };
}

fs.mkdirSync(OUT, { recursive: true });

/* ---------------------------------------------------------- compuerta */
{
  const ctx = fresh(true);
  const g = ctx.game.state;
  run(ctx, 1200, null, false);
  run(ctx, 1200, 90, false);
  run(ctx, 600, null, true);
  check(g.dist === 0 && g.ghost === 0, `compuerta: avanzo sin senal valida (${g.dist}, ${g.ghost})`);
  check(g.playTicks === 0, 'compuerta: el reloj corrio con la compuerta cerrada');
  capture(ctx, 'carrera_compuerta');
}

/* ------------------------------------- velocidad proporcional a la atencion */
{
  const { C } = fresh(true);
  check(C.speedFor(20) === C.V_MIN && C.speedFor(95) === C.V_MAX, 'velocidad: extremos');
  let previa = -1;
  let monotona = true;
  for (let a = 30; a <= 90; a += 5) {
    const v = C.speedFor(a);
    if (v < previa) monotona = false;
    previa = v;
  }
  check(monotona, 'velocidad: no crece con la atencion');
  check(C.speedFor(60) > C.speedFor(50) && C.speedFor(70) > C.speedFor(60),
    'velocidad: no es continua en la zona neutral');
  check(Math.abs(C.speedFor(C.ATT_GHOST) - C.GHOST_V) < 1e-9, 'velocidad: la raya del rival no coincide');
  check(C.ATT_GHOST > 50 && C.ATT_GHOST < 65,
    `velocidad: ganarle al rival pide ${C.ATT_GHOST.toFixed(1)}, fuera de lo previsto`);

  // En juego: con el bot, mas atencion recorre mas en el mismo tiempo.
  const recorridos = [40, 60, 85].map((sig) => {
    const ctx = fresh(true, 9);
    run(ctx, 20 * 60, sig, true, { bot: true });
    return ctx.game.state.dist;
  });
  check(recorridos[0] < recorridos[1] && recorridos[1] < recorridos[2],
    `velocidad: recorridos en 20 s no crecen con la atencion (${recorridos.map((d) => d.toFixed(0)).join(', ')})`);
}

/* --------------------------------------------------- carreras completas */
{
  const ctx = fresh(true, 11);
  ctx.game.setScenery(0);
  const ganada = race(ctx, 88);
  check(ganada.result === 1, `meta: con atencion alta no gano (resultado ${ganada.result})`);
  check(ganada.seconds === Math.floor(ganada.ticks / 60), 'reloj: el tiempo guardado no es el jugado');
  // Entre lo que se tarda a velocidad maxima y lo que tarda el rival.
  const minimo = Math.floor(ctx.C.FINISH_M / ctx.C.V_MAX);
  const rival = ctx.C.FINISH_M / ctx.C.GHOST_V;
  check(ganada.seconds >= minimo && ganada.seconds < rival,
    `reloj: ${ganada.seconds} s con atencion alta, fuera de [${minimo}, ${rival.toFixed(1)})`);
  check(ctx.game.state.bestSeconds === ganada.seconds, 'reloj: el primer tiempo no quedo como mejor');
  run(ctx, 20, 88, true);
  capture(ctx, 'carrera_gano');

  // Siguiente carrera, con atencion neutral: el rival llega primero.
  run(ctx, 400, 50, true);
  check(ctx.game.state.state === 0 && ctx.game.state.dist < 50, 'meta: no arranco una carrera nueva');
  const perdida = race(ctx, 50);
  check(perdida.result === 2, `meta: con atencion neutral no perdio (resultado ${perdida.result})`);
  check(perdida.seconds > ctx.C.FINISH_M / ctx.C.GHOST_V, `meta: perdio en ${perdida.seconds} s, antes que el rival`);
  check(ctx.game.state.bestSeconds === ganada.seconds, 'reloj: el mejor no se conservo');
  run(ctx, 20, 50, true);
  capture(ctx, 'carrera_segundo');
}

/* ------------------------------------------------ reloj y pausas */
{
  const ctx = fresh(true, 13);
  const g = ctx.game.state;
  run(ctx, 600, 80, true, { bot: true });
  const antes = [g.playTicks, g.dist, g.ghost].join(',');
  run(ctx, 900, 80, false);
  check([g.playTicks, g.dist, g.ghost].join(',') === antes, 'reloj: una pausa avanzo la carrera o el reloj');
}

/* ------------------------------------------ choques y canales visuales */
{
  const ctx = fresh(true, 17);
  const g = ctx.game.state;
  let vistoChoque = false;
  for (let i = 0; i < 60 * 40 && !vistoChoque; i++) {
    const antes = g.crashes;
    run(ctx, 1, 75, true);
    if (g.crashes > antes) {
      vistoChoque = true;
      check(ctx.game.speed() < ctx.C.speedFor(g.att) - 5, 'choque: no resto velocidad');
    }
  }
  check(vistoChoque, 'choque: sin bot no choco en 40 s');

  // Lineas de velocidad: mas pixeles con mas velocidad. Se miden aisladas,
  // sin obstaculos ni castigo: lo que se verifica es el canal, no el manejo,
  // y varios obstaculos nuevos usan el mismo gris.
  function lineas(sig) {
    const c = fresh(true, 19);
    run(c, 900, sig, true, { bot: true });
    c.game.obstacleView().count = 0;
    c.game.state.penalty = 0;
    c.game.render(c.frame);
    const pal = c.game.palette;
    const gris = pal.ramps.petalWhite[0];
    let n = 0;
    const x0 = (c.game.W - 106) >> 1;
    for (let y = 26; y < c.game.H; y++) {
      for (let x = x0 + 3; x < x0 + 103; x++) if (c.frame.px[y * c.game.W + x] === gris) n++;
    }
    return n;
  }
  const lento = lineas(35);
  const rapido = lineas(90);
  check(rapido > lento * 2, `lineas de velocidad: ${lento} pixeles lento y ${rapido} rapido`);

  // Escape: mas particulas con mas atencion.
  function escape(sig) {
    const c = fresh(true, 23);
    run(c, 900, sig, true, { bot: true });
    let suma = 0;
    for (let i = 0; i < 120; i++) {
      run(c, 1, sig, true, { bot: true });
      suma += c.game.exhaustCount();
    }
    return suma / 120;
  }
  check(escape(90) > escape(35) * 1.5, 'escape: no crece con la atencion');
}

/* ------------------------------------------ obstaculos y equidad */
{
  // Una carrera larga por paisaje, registrando cada obstaculo al aparecer.
  const vistos = [new Set(), new Set(), new Set()];
  let bloqueos = 0;
  let autosQueAvanzan = 0;
  for (let esc = 0; esc < 3; esc++) {
    const ctx = fresh(true, 50 + esc);
    ctx.game.setScenery(esc);
    const g = ctx.game.state;
    const ob = ctx.game.obstacleView();
    const conocidos = new Map();
    run(ctx, 60 * 60, 90, true, {
      bot: true,
      until: () => {
        for (let i = 0; i < ob.count; i++) {
          vistos[esc].add(ob.kind[i]);
          if (ob.kind[i] >= 3 && ob.kind[i] <= 6) {
            const clave = ob.lane[i] + ':' + ob.kind[i] + ':' + Math.round(ob.v[i] * 100);
            // Contra su primera posicion: entre ticks avanza menos de medio metro.
            const primera = conocidos.get(clave);
            if (primera === undefined) conocidos.set(clave, ob.m[i]);
            else if (ob.m[i] > primera + 5) autosQueAvanzan++;
          }
        }
        // Ninguna franja de 10 m con los tres carriles ocupados por obstaculos
        // fijos: no habria por donde pasar.
        for (let i = 0; i < ob.count; i++) {
          let carriles = 0;
          for (let l = 0; l < 3; l++) {
            for (let j = 0; j < ob.count; j++) {
              if (ob.lane[j] === l && Math.abs(ob.m[j] - ob.m[i]) < 10 && ob.v[j] === 0 && ob.v[i] === 0) {
                carriles++;
                break;
              }
            }
          }
          if (carriles === 3) bloqueos++;
        }
        return g.state !== 0;
      },
    });
  }
  check(bloqueos === 0, `equidad: ${bloqueos} cuadros con los tres carriles bloqueados`);
  check(autosQueAvanzan > 20, `autos lentos: no avanzan (${autosQueAvanzan} observaciones)`);
  const tema = [7, 8, 9];
  for (let esc = 0; esc < 3; esc++) {
    check(vistos[esc].has(tema[esc]), `obstaculos: el tematico del paisaje ${esc} no aparecio`);
    check(!vistos[esc].has(tema[(esc + 1) % 3]), `obstaculos: un tematico ajeno aparecio en el paisaje ${esc}`);
    check([3, 4, 5, 6].some((k) => vistos[esc].has(k)), `obstaculos: sin autos lentos en el paisaje ${esc}`);
  }
}

/* ------------------------------------------ paisajes con variedad */
{
  // Recorre cada paisaje y registra que elementos aparecen.
  const vistos = [new Set(), new Set(), new Set()];
  for (let esc = 0; esc < 3; esc++) {
    for (const seed of [61, 62, 63]) {
      const ctx = fresh(true, seed + esc * 10, 176, 288);
      ctx.game.setScenery(esc);
      run(ctx, 60 * 60, 90, true, { bot: true, until: () => ctx.game.state.state !== 0 });
      // El catalogo de paisaje no es observable desde fuera; se infiere del
      // tipo registrado en cada elemento a traves de la hoja del juego.
      const sc = ctx.game.sceneryView();
      for (let i = 0; i < sc.count; i++) vistos[esc].add(sc.kind[i]);
      for (const k of ctx.game.sceneryHistory()) vistos[esc].add(k);
    }
  }
  const hitosBosque = [12, 13, 14, 15, 16, 17].filter((k) => vistos[0].has(k));
  check(hitosBosque.length >= 2, `paisaje: casi no hay hitos en el bosque (${hitosBosque})`);
  check(vistos[1].has(18) || vistos[1].has(19), 'paisaje: sin piramides ni ruinas en el desierto');
  check([4, 5, 6, 7].some((k) => vistos[2].has(k)) && [8, 9, 10, 11].some((k) => vistos[2].has(k)),
    'paisaje: el pueblo no alterna teja y losa');
}

/* ------------------------------------------ meta a la vista */
{
  const ctx = fresh(true, 29, 176, 288);
  ctx.game.setScenery(2);
  run(ctx, 60 * 300, 80, true, { bot: true, until: () => ctx.game.state.dist > 960 });
  capture(ctx, 'carrera_meta_pueblo');
}

{
  const ctx = fresh(true, 31, 144, 192);
  ctx.game.setScenery(1);
  run(ctx, 12 * 60, 45, true, { bot: true, theme: 'light' });
  capture(ctx, 'carrera_desierto_claro', 'light');
}

/* ------------------------------------------ teclado y herramientas */
{
  const ctx = fresh(true);
  const g = ctx.game.state;
  ctx.E.pressKey('w');
  ctx.E.pressKey('g');
  run(ctx, 3, 40, true);
  ctx.E.releaseKey('w');
  ctx.E.releaseKey('g');
  check(g.devSignal === 50 && g.lastSignal === 40, 'teclado: W altero la senal en la aplicacion');
  check(!g.grid, 'teclado: la rejilla del personal se activo en la aplicacion');
  ctx.E.receive({ source: 'neurodac', keydown: 'ArrowLeft' }, 0);
  ctx.E.receive({ source: 'neurodac', keyup: 'ArrowLeft' }, 0);
  run(ctx, 1, 40, true);
  check(g.lane === 0, 'teclado: la flecha reenviada no cambio de carril');
}
{
  const ctx = fresh(false);
  const g = ctx.game.state;
  check(ctx.E.isStandalone(), 'autonomo: no se detecto');
  for (let k = 0; k < 2; k++) {
    ctx.E.pressKey('w');
    ctx.game.tick();
    ctx.E.releaseKey('w');
  }
  check(g.devSignal === 70, `autonomo: dos pulsaciones de W deben dar 70 (${g.devSignal})`);
  for (let i = 0; i < 300; i++) ctx.game.tick();
  capture(ctx, 'carrera_autonomo');
  ctx.E.pressKey('h');
  ctx.game.tick();
  ctx.E.releaseKey('h');
  check(g.sheet, 'autonomo: la hoja de sprites no se activo');
  capture(ctx, 'carrera_hoja');
}

/* ------------------------------------------ paisajes y tamano */
{
  const ctx = fresh(true, 37);
  const vistos = new Set();
  let previo = ctx.game.state.scenery;
  let repetidos = 0;
  for (let i = 0; i < 30; i++) {
    ctx.game.resetRace(true);
    const s = ctx.game.state.scenery;
    if (s === previo) repetidos++;
    vistos.add(s);
    previo = s;
  }
  check(repetidos === 0, `paisajes: ${repetidos} repeticiones inmediatas`);
  check(vistos.size === ctx.C.SCENERY_COUNT, 'paisajes: no aparecieron todos');

  const c2 = fresh(true, 41, 144, 192);
  run(c2, 600, 70, true, { bot: true });
  const antes = [c2.game.state.dist, c2.game.state.playTicks].join(',');
  c2.game.setSize(176, 288);
  check(c2.game.W === 176 && c2.game.H === 288, 'tamano: no cambio');
  check([c2.game.state.dist, c2.game.state.playTicks].join(',') === antes, 'tamano: la carrera cambio');
  c2.game.setSize(9999, 9999);
  check(c2.game.W === 176 && c2.game.H === 288, 'tamano: no respeta el maximo');
  c2.frame = c2.E.createFrame(c2.game.W, c2.game.H, 0);
  c2.game.setScenery(0);
  run(c2, 120, 70, true, { bot: true });
  capture(c2, 'carrera_bosque_alto');
}

/* -------------------------------------------- textos y teclas */
{
  const { E, C } = fresh(true);
  const TEXTOS = require(path.resolve(__dirname, '..', 'assets', 'games', 'textos.js'));
  for (const [clave, texto] of Object.entries(TEXTOS.carrera)) {
    const c = E.unsupportedChar(texto);
    check(c === null, `textos: '${clave}' tiene '${c}', que la fuente no puede dibujar`);
  }
  check(C.KEYS_USED.join() === 'ArrowLeft,ArrowRight', 'teclas: Carrera solo atiende los carriles');
}

/* ------------------------------------------------------- rendimiento */
const rendimiento = (() => {
  const ctx = fresh(true, 43, 176, 288);
  run(ctx, 600, 75, true, { bot: true });
  const N = 3000;
  const t = new Float64Array(N);
  for (let i = 0; i < N; i++) {
    const a = performance.now();
    bridge(ctx.E, 60 + 25 * Math.sin(i / 120), true);
    ctx.game.tick();
    ctx.game.render(ctx.frame);
    t[i] = performance.now() - a;
    if (ctx.game.state.state !== 0) ctx.game.resetRace(true);
  }
  t.sort();
  const q = (p) => t[Math.floor(p * (N - 1))];
  const fiable =
    global.gc && process.execArgv.some((a) => a.startsWith('--min-semi-space-size='));
  let heap = null;
  if (fiable) {
    bridge(ctx.E, 70, true);
    global.gc();
    const h0 = process.memoryUsage().heapUsed;
    for (let i = 0; i < N; i++) {
      ctx.game.tick();
      ctx.game.render(ctx.frame);
    }
    heap = (process.memoryUsage().heapUsed - h0) / 1024 / (N / 60);
  }
  check(q(0.99) < 16.7, `rendimiento: p99 ${q(0.99).toFixed(2)} ms excede el cuadro de 60 Hz`);
  return { p50: q(0.5), p95: q(0.95), p99: q(0.99), heap };
})();

for (const c of capturas) {
  console.log(`  ${c.nombre.padEnd(24)} colores ${String(c.distintos).padStart(2)}  fuera de paleta ${c.fuera}`);
}
console.log(
  `  rendimiento por cuadro (tick + render, 176x288): p50 ${rendimiento.p50.toFixed(3)} ms  ` +
    `p95 ${rendimiento.p95.toFixed(3)} ms  p99 ${rendimiento.p99.toFixed(3)} ms`
);
if (rendimiento.heap !== null) {
  console.log(`  alocacion: ${rendimiento.heap.toFixed(1)} KB/s a 60 Hz`);
} else {
  console.log(
    '  alocacion: no medida. Para medirla: node --expose-gc ' +
      '--min-semi-space-size=256 --max-semi-space-size=256 tools/capturas_carrera.js'
  );
}
if (fallas.length) {
  console.log('FALLA');
  for (const f of fallas) console.log('  - ' + f);
  process.exitCode = 1;
} else {
  console.log('OK');
}

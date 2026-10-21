/* Verifica Jardin Mental sin navegador y vuelca capturas.

   Uso:
       node tools/capturas_jardin.js [carpeta_salida]

   La salida por defecto es results/capturas, que el .gitignore ya excluye.
   Para medir tambien la alocacion por cuadro:

       node --expose-gc --min-semi-space-size=256 --max-semi-space-size=256 \
            tools/capturas_jardin.js

   No solo dibuja: ejercita el juego con los mismos mensajes que manda la
   pagina y falla si el comportamiento no es el del contrato. La compuerta,
   que el teclado no altere la senal dentro de la aplicacion, que la escena
   responda a la calma y que ningun pixel salga de la paleta. */

'use strict';

const fs = require('fs');
const path = require('path');
const { writePNG, upscale } = require('./png.js');

const OUT = process.argv[2] || path.join('results', 'capturas');
const ENGINE = path.resolve(__dirname, '..', 'assets', 'games', 'engine.js');
const JARDIN = path.resolve(__dirname, '..', 'assets', 'games', 'jardin.js');
const SCALE = 4;

const fallas = [];
function check(cond, mensaje) {
  if (!cond) fallas.push(mensaje);
  return cond;
}

/** Copia fresca del motor y del juego: el estado de entrada es de modulo. */
function fresh(embedded, seed) {
  delete require.cache[ENGINE];
  delete require.cache[JARDIN];
  const E = require(ENGINE);
  const J = require(JARDIN);
  E.setEmbedded(embedded);
  const game = J.createGame({ seed: seed === undefined ? 7 : seed });
  const frame = E.createFrame(game.W, game.H, 0);
  return { E, J, game, frame };
}

/** Lo que manda la pagina en cada refresco, segun docs/contrato-juegos.md. */
function bridge(E, signalValue, ready, theme) {
  E.receive({ source: 'neurodac', signalValue, ready, theme: theme || 'dark' }, 0);
}

function run(ctx, ticks, signalValue, ready, theme) {
  for (let i = 0; i < ticks; i++) {
    bridge(ctx.E, signalValue, ready, theme);
    ctx.game.tick();
  }
}

/** Amplitud del vaiven: maximo desplazamiento del resorte de una flor. */
function measureSway(ctx, ticks, signalValue) {
  let max = 0;
  for (let i = 0; i < ticks; i++) {
    bridge(ctx.E, signalValue, true);
    ctx.game.tick();
    max = Math.max(max, Math.abs(ctx.game.swayOf(0)));
  }
  return max;
}

const capturas = [];
function capture(ctx, nombre, theme) {
  ctx.game.render(ctx.frame);
  const pal = ctx.game.palette;
  let fuera = 0;
  for (let i = 0; i < ctx.frame.px.length; i++) if (ctx.frame.px[i] >= pal.count) fuera++;
  const distintos = ctx.E.countColors(ctx.frame, new Uint8Array(256));
  check(fuera === 0, `${nombre}: ${fuera} pixeles fuera de la paleta`);
  check(distintos <= pal.count, `${nombre}: ${distintos} colores, mas que la paleta`);
  writePNG(
    path.join(OUT, `${nombre}.png`),
    ctx.game.W * SCALE, ctx.game.H * SCALE,
    upscale(ctx.frame.px, ctx.game.W, ctx.game.H, SCALE),
    pal.rgb[theme || 'dark'], pal.count
  );
  capturas.push({ nombre, distintos, fuera });
}

fs.mkdirSync(OUT, { recursive: true });

/* ---------------------------------------------------------- compuerta */
{
  const ctx = fresh(true);
  const g = ctx.game.state;
  // Sin valor y sin compuerta: lo que llega antes de que la senal sirva.
  run(ctx, 1200, null, false);
  check(g.health[0] === 50 && g.stage[0] === 0 && g.level[0] === 50,
    'compuerta: la flor cambio sin senal valida');
  // Con valor pero compuerta cerrada, como al calibrar.
  run(ctx, 1200, 10, false);
  check(g.health[0] === 50, 'compuerta: la flor perdio salud con la compuerta cerrada');
  // Compuerta abierta pero sin valor: tampoco debe correr.
  run(ctx, 600, null, true);
  check(g.health[0] === 50, 'compuerta: la flor corrio con ready pero sin valor');
  capture(ctx, 'jardin_compuerta');
}

/* --------------------------------------------- la mecanica es la anterior */
{
  const ctx = fresh(true);
  const g = ctx.game.state;
  // Por encima de 55 el nivel sube 1 por tick; con 60 o mas, una etapa por
  // segundo. Seis etapas: la primera flor termina en seis segundos y poco.
  run(ctx, 6 * 60 + 15, 85, true);
  check(g.done >= 1 && g.current === 1, `mecanica: tras ~6 s con calma alta, done=${g.done}`);
  // Por debajo de 45 se pierde 3 de salud por segundo: de 50 a 0 en ~17 s.
  const ctx2 = fresh(true);
  run(ctx2, 5 * 60, 20, true);
  const tras5 = ctx2.game.state.health[0];
  check(tras5 < 50, `mecanica: con calma baja la salud no bajo (${tras5})`);
  // Se registra si el aviso aparecio en algun momento: al terminar, el
  // jardin puede estar ya reiniciado y la salud de vuelta en 50.
  let marchita = false;
  for (let i = 0; i < 16 * 60 && !marchita; i++) {
    run(ctx2, 1, 20, true);
    marchita = ctx2.game.state.banner === 2;
  }
  check(marchita, 'mecanica: la flor no se marchito con calma baja sostenida');
}

/* ---------------------------------------- la senal se ve en la escena */
{
  const ctx = fresh(true);
  run(ctx, 600, 90, true);
  const calmaAlta = ctx.game.state.calm;
  const ampAlta = measureSway(ctx, 180, 90);
  run(ctx, 600, 15, true);
  const calmaBaja = ctx.game.state.calm;
  const ampBaja = measureSway(ctx, 180, 15);
  check(calmaAlta > 0.8, `escena: la calma suavizada no subio (${calmaAlta.toFixed(2)})`);
  check(calmaBaja < 0.2, `escena: la calma suavizada no bajo (${calmaBaja.toFixed(2)})`);
  check(ampAlta < ampBaja * 0.5,
    `escena: el vaiven no se calma (${ampAlta.toFixed(2)} vs ${ampBaja.toFixed(2)} px)`);
}

/* --------------------------------------------------- polen y capturas */
{
  const ctx = fresh(true, 11);
  ctx.game.state.scene = 1; // Chichen Itza
  run(ctx, 6 * 60 + 15, 88, true); // primera flor completa
  run(ctx, 4 * 60, 88, true);
  check(ctx.game.state.current >= 1, 'polen: no avanzo a la segunda flor');
  let maxPolen = 0;
  for (let i = 0; i < 120; i++) {
    run(ctx, 1, 88, true);
    maxPolen = Math.max(maxPolen, ctx.game.pollenCount());
  }
  check(maxPolen > 5, `polen: casi no aparece con calma alta (${maxPolen})`);
  capture(ctx, 'jardin_calma_alta');

  run(ctx, 6 * 60, 18, true);
  // La vida maxima del polen son 200 ticks: tras seis segundos debe haberse ido.
  check(ctx.game.pollenCount() === 0, `polen: quedan ${ctx.game.pollenCount()} con calma baja`);
  capture(ctx, 'jardin_calma_baja');
}

{
  const ctx = fresh(true, 3);
  ctx.game.state.scene = 2; // volcanes
  run(ctx, 3 * (6 * 60 + 15), 80, true, 'light');
  check(ctx.game.state.done >= 3, `avance: tres flores, done=${ctx.game.state.done}`);
  capture(ctx, 'jardin_avance_claro', 'light');
}

{
  const ctx = fresh(true, 5);
  ctx.game.state.scene = 0;
  // Cinco flores completas: aparece el aviso de jardin completo.
  let t = 0;
  while (ctx.game.state.banner !== 1 && t < 5 * 60 * 10) {
    run(ctx, 1, 90, true);
    t++;
  }
  check(ctx.game.state.banner === 1, 'completo: no aparecio el aviso de jardin completo');
  run(ctx, 30, 90, true);
  capture(ctx, 'jardin_completo');
  const antes = ctx.game.state.scene;
  run(ctx, 400, 90, true);
  check(ctx.game.state.done < 5 && ctx.game.state.scene !== antes,
    'completo: el jardin no se renovo con otro escenario');
}

/* --------------------------------------- el polen aparece gradualmente */
{
  // Al cruzar el umbral no debe brotar de golpe: su intensidad parte de cero.
  const ctx = fresh(true, 17);
  run(ctx, 300, 20, true);
  run(ctx, 15, 90, true);
  const alCruzar = ctx.game.pollenCount();
  check(alCruzar <= 2, `polen: brota de golpe al cruzar el umbral (${alCruzar} en 1/4 s)`);
  run(ctx, 180, 90, true);
  check(ctx.game.pollenCount() > alCruzar, 'polen: no crece despues de cruzar el umbral');
}

/* -------------------------------------------- la vida se ve en el suelo */
{
  const ctx = fresh(true, 23);
  ctx.game.state.scene = 1;
  // Calma alta sostenida: la vida sube con cada etapa.
  run(ctx, 2 * (6 * 60 + 15) + 120, 90, true);
  const g = ctx.game.state;
  const vidaAlta = g.health[g.current];
  const alta = ctx.game.groundCounts();
  check(vidaAlta >= 80, `vida: no subio con calma alta (${vidaAlta})`);
  check(alta.blooms >= 3, `vida: con vida alta casi no hay florecitas (${alta.blooms})`);
  capture(ctx, 'jardin_vida_alta');

  // Calma baja hasta justo antes de marchitarse.
  let t = 0;
  while (g.health[g.current] > 12 && g.banner === 0 && t < 30 * 60) {
    run(ctx, 1, 20, true);
    t++;
  }
  run(ctx, 90, 20, true);
  const baja = ctx.game.groundCounts();
  check(g.banner === 0, 'vida: la flor se marchito antes de la captura');
  check(baja.blooms === 0, `vida: quedan ${baja.blooms} florecitas con vida baja`);
  check(baja.tufts < alta.tufts, `vida: el pasto no raleo (${baja.tufts} vs ${alta.tufts})`);
  capture(ctx, 'jardin_vida_baja');
}

/* ------------------------------------------ rotacion de escenarios */
{
  const ctx = fresh(true, 21);
  const vistos = new Set();
  let previo = ctx.game.state.scene;
  let repetidos = 0;
  for (let i = 0; i < 30; i++) {
    ctx.game.resetGarden(true);
    const s = ctx.game.state.scene;
    if (s === previo) repetidos++;
    vistos.add(s);
    previo = s;
  }
  check(repetidos === 0, `escenarios: ${repetidos} repeticiones inmediatas`);
  check(vistos.size === ctx.game.sceneCount, 'escenarios: no aparecieron todos');
}

/* --------------------------------------- teclado y herramientas */
{
  // Dentro de la aplicacion las flechas no alteran la senal y las
  // herramientas del personal no existen.
  const ctx = fresh(true);
  const g = ctx.game.state;
  ctx.E.pressKey('ArrowUp');
  ctx.E.pressKey('g');
  run(ctx, 2, 40, true);
  ctx.E.releaseKey('ArrowUp');
  ctx.E.releaseKey('g');
  check(g.devSignal === 50 && g.lastSignal === 40,
    'teclado: las flechas alteraron la senal en la aplicacion');
  check(!g.grid, 'teclado: la rejilla del personal se activo en la aplicacion');
}
{
  // Abierto fuera de la aplicacion: modo autonomo, controlado por teclado.
  const ctx = fresh(false);
  const g = ctx.game.state;
  check(ctx.E.isStandalone(), 'autonomo: no se detecto el modo autonomo');
  ctx.E.pressKey('ArrowUp');
  ctx.game.tick();
  ctx.E.releaseKey('ArrowUp');
  ctx.E.pressKey('ArrowUp');
  ctx.game.tick();
  ctx.E.releaseKey('ArrowUp');
  check(g.devSignal === 70, `autonomo: dos pulsaciones deben dar 70 (${g.devSignal})`);
  for (let i = 0; i < 400; i++) ctx.game.tick();
  capture(ctx, 'jardin_autonomo');
  ctx.E.pressKey('h');
  ctx.game.tick();
  ctx.E.releaseKey('h');
  check(g.sheet, 'autonomo: la hoja de sprites no se activo');
  capture(ctx, 'jardin_hoja');
}

/* ---------------------------------------------------- acercamiento */
{
  const ctx = fresh(true, 11);
  run(ctx, 4 * 60 + 15, 85, true);
  ctx.game.render(ctx.frame);
  const r = ctx.game.focus();
  const crop = new Uint8Array(r.w * r.h);
  for (let y = 0; y < r.h; y++) {
    for (let x = 0; x < r.w; x++) crop[y * r.w + x] = ctx.frame.px[(r.y + y) * ctx.game.W + r.x + x];
  }
  writePNG(path.join(OUT, 'jardin_zoom.png'), r.w * 10, r.h * 10, upscale(crop, r.w, r.h, 10),
    ctx.game.palette.rgb.dark, ctx.game.palette.count);
}

/* -------------------------------------------- textos y teclas */
{
  const { E, J } = fresh(true);
  const TEXTOS = require(path.resolve(__dirname, '..', 'assets', 'games', 'textos.js'));
  for (const [clave, texto] of Object.entries(TEXTOS.jardin)) {
    const c = E.unsupportedChar(texto);
    check(c === null, `textos: '${clave}' tiene '${c}', que la fuente no puede dibujar`);
  }
  check(J.KEYS_USED.length === 0, 'teclas: Jardin no debe atender teclas dentro de la aplicacion');
}

/* ------------------------------------------------------- rendimiento */
const rendimiento = (() => {
  const ctx = fresh(true, 13);
  run(ctx, 900, 85, true);
  const N = 3000;
  const t = new Float64Array(N);
  for (let i = 0; i < N; i++) {
    const sig = 50 + 40 * Math.sin(i / 90);
    const a = performance.now();
    bridge(ctx.E, sig, true);
    ctx.game.tick();
    ctx.game.render(ctx.frame);
    t[i] = performance.now() - a;
  }
  t.sort();
  const q = (p) => t[Math.floor(p * (N - 1))];
  // La alocacion solo es fiable si el recolector no puede correr durante la
  // ventana: con un espacio joven chico, recolecta a mitad de la medicion y la
  // diferencia de heapUsed sale baja y enganosa. Por eso se mide solo con
  // los indicadores que lo garantizan.
  const fiable =
    global.gc && process.execArgv.some((a) => a.startsWith('--min-semi-space-size='));
  let heap = null;
  if (fiable) {
    global.gc();
    const h0 = process.memoryUsage().heapUsed;
    // El puente se fija una vez: construir el mensaje en cada tick es
    // alocacion del arnes, no del juego.
    bridge(ctx.E, 60, true);
    for (let i = 0; i < N; i++) {
      ctx.game.tick();
      ctx.game.render(ctx.frame);
    }
    heap = (process.memoryUsage().heapUsed - h0) / 1024 / (N / 60);
  }
  check(q(0.99) < 16.7, `rendimiento: p99 ${q(0.99).toFixed(2)} ms excede el cuadro de 60 Hz`);
  return { p50: q(0.5), p95: q(0.95), p99: q(0.99), heap };
})();

/* ------------------------------------------------------------ reporte */
for (const c of capturas) {
  console.log(`  ${c.nombre.padEnd(22)} colores ${String(c.distintos).padStart(2)}  fuera de paleta ${c.fuera}`);
}
console.log(
  `  rendimiento por cuadro (tick + render): p50 ${rendimiento.p50.toFixed(3)} ms  ` +
    `p95 ${rendimiento.p95.toFixed(3)} ms  p99 ${rendimiento.p99.toFixed(3)} ms`
);
if (rendimiento.heap !== null) {
  console.log(`  alocacion: ${rendimiento.heap.toFixed(1)} KB/s a 60 Hz`);
} else {
  console.log(
    '  alocacion: no medida. Para medirla: node --expose-gc ' +
      '--min-semi-space-size=256 --max-semi-space-size=256 tools/capturas_jardin.js'
  );
}

if (fallas.length) {
  console.log('FALLA');
  for (const f of fallas) console.log('  - ' + f);
  process.exitCode = 1;
} else {
  console.log('OK');
}

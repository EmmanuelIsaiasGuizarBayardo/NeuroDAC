/* ============================================================================
   NeuroDAC · encuadre de los juegos

   Corre en la pagina principal (Dash lo inyecta desde assets/). Ajusta cada
   contenedor de juego al mayor multiplo entero de su resolucion logica que
   cabe en el espacio disponible, contando la densidad de pixeles de la
   pantalla. Asi el juego llena su iframe sin resto y con escalado entero: lo
   que sobra queda fuera del recuadro, como margen de la pagina, y no como
   franjas dentro del juego.

   Escalar por CSS a un factor no entero llenaria el marco, pero sobre el
   tramado Bayer del cielo produciria moire: bandas que no existen en el
   dibujo.

   Solo actua sobre contenedores con data-lw y data-lh; los juegos que no las
   declaran conservan su tamano.
   ========================================================================== */

(function (root) {
  'use strict';

  /**
   * Tamano CSS del area de juego para un espacio disponible.
   *
   * availW, availH: espacio en pixeles CSS. dpr: pixeles de dispositivo por
   * pixel CSS. lw, lh: resolucion logica del juego.
   */
  function encuadre(availW, availH, dpr, lw, lh) {
    const scale = Math.max(1, Math.floor(Math.min((availW * dpr) / lw, (availH * dpr) / lh)));
    return { scale: scale, width: (lw * scale) / dpr, height: (lh * scale) / dpr };
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { encuadre: encuadre };
    return;
  }

  /** Alto maximo declarado ("66vh" o "500px") en pixeles CSS. */
  function maxHeight(value) {
    const m = /^([\d.]+)(vh|px)$/.exec(value || '');
    if (!m) return Infinity;
    const n = parseFloat(m[1]);
    return m[2] === 'vh' ? (root.innerHeight * n) / 100 : n;
  }

  function sides(style, a, b) {
    return (parseFloat(style[a]) || 0) + (parseFloat(style[b]) || 0);
  }

  function ajustar() {
    const dpr = root.devicePixelRatio || 1;
    const nodos = root.document.querySelectorAll('.game-canvas-container[data-lw]');
    for (let i = 0; i < nodos.length; i++) {
      const c = nodos[i];
      const padre = c.parentElement;
      if (!padre) continue;
      const cs = root.getComputedStyle(c);
      const ps = root.getComputedStyle(padre);
      // El borde del contenedor no es area de juego.
      const bx = sides(cs, 'borderLeftWidth', 'borderRightWidth');
      const by = sides(cs, 'borderTopWidth', 'borderBottomWidth');
      const availW = padre.clientWidth - sides(ps, 'paddingLeft', 'paddingRight') - bx;
      const availH = maxHeight(c.dataset.maxh) - by;
      if (availW <= 0 || availH <= 0) continue;
      const r = encuadre(availW, availH, dpr, +c.dataset.lw, +c.dataset.lh);
      const w = r.width + bx + 'px';
      const h = r.height + by + 'px';
      // Solo se escribe si cambia: escribir el estilo fuerza otro calculo de
      // maquetacion, y esto corre con cada cambio del DOM.
      if (c.style.width !== w) c.style.width = w;
      if (c.style.height !== h) c.style.height = h;
      c.style.marginLeft = 'auto';
      c.style.marginRight = 'auto';
    }
  }

  let pendiente = false;
  function programar() {
    if (pendiente) return;
    pendiente = true;
    root.requestAnimationFrame(function () {
      pendiente = false;
      ajustar();
    });
  }

  root.addEventListener('resize', programar);
  // Dash monta cada pagina despues de cargar: se observa el arbol, como en
  // neurons.js. Como mucho un ajuste por cuadro.
  new root.MutationObserver(programar).observe(root.document.documentElement, {
    childList: true,
    subtree: true,
  });
  programar();
})(typeof globalThis !== 'undefined' ? globalThis : this);

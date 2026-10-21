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

  /**
   * Encuadre que llena el ancho: el factor sale del ancho disponible y el
   * juego dibuja tantas columnas logicas como quepan, entre minW y maxW, con
   * la altura logica lh fija.
   *
   * Solo se baja el factor si el juego no cupiera en la pantalla y hubiera que
   * desplazarse para verlo; en ventanas normales de escritorio no ocurre.
   */
  function encuadreAncho(availW, availH, dpr, minW, maxW, lh) {
    let scale = Math.max(1, Math.floor((availW * dpr) / minW));
    while (scale > 1 && lh * scale > availH * dpr) scale--;
    const lw = Math.max(minW, Math.min(maxW, Math.floor((availW * dpr) / scale)));
    return { scale: scale, lw: lw, width: (lw * scale) / dpr, height: (lh * scale) / dpr };
  }

  /**
   * Encuadre que llena ancho y alto: el juego admite un rango de columnas y
   * uno de filas. El factor es el mayor que deja ambos lados dentro de su
   * minimo, y el juego dibuja tantas columnas y filas como quepan. Con la
   * ventana mas alta se ve mas juego, no pixeles mas grandes.
   */
  function encuadreLlenar(availW, availH, dpr, minW, maxW, minH, maxH) {
    const scale = Math.max(
      1,
      Math.min(Math.floor((availW * dpr) / minW), Math.floor((availH * dpr) / minH))
    );
    const lw = Math.max(minW, Math.min(maxW, Math.floor((availW * dpr) / scale)));
    const lh = Math.max(minH, Math.min(maxH, Math.floor((availH * dpr) / scale)));
    return { scale: scale, lw: lw, lh: lh, width: (lw * scale) / dpr, height: (lh * scale) / dpr };
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { encuadre: encuadre, encuadreAncho: encuadreAncho, encuadreLlenar: encuadreLlenar };
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
      let r;
      if (c.dataset.lhmax) {
        // Llena ancho y alto: el alto disponible es lo que queda de pantalla
        // debajo de donde empieza el recuadro.
        const top = c.getBoundingClientRect().top + root.scrollY;
        const availH = root.innerHeight - top - 12 - by;
        if (availW <= 0 || availH <= 0) continue;
        r = encuadreLlenar(
          availW, availH, dpr,
          +c.dataset.lw, +c.dataset.lwmax, +c.dataset.lh, +c.dataset.lhmax
        );
      } else if (c.dataset.lwmax) {
        // Llena el ancho. El alto solo limita si el juego no cupiera en la
        // pantalla: lo que queda debajo de donde empieza el recuadro.
        const top = c.getBoundingClientRect().top + root.scrollY;
        const availH = root.innerHeight - top - 12 - by;
        if (availW <= 0 || availH <= 0) continue;
        r = encuadreAncho(availW, availH, dpr, +c.dataset.lw, +c.dataset.lwmax, +c.dataset.lh);
      } else {
        const availH = maxHeight(c.dataset.maxh) - by;
        if (availW <= 0 || availH <= 0) continue;
        r = encuadre(availW, availH, dpr, +c.dataset.lw, +c.dataset.lh);
      }
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

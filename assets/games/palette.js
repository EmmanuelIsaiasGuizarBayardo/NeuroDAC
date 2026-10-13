/* ============================================================================
   NeuroDAC · paleta compartida

   48 colores en rampas de oscuro a claro, una por material. Los dos juegos
   usan esta misma paleta. El tema claro no es otra paleta: es otra tabla RGB
   sobre los mismos indices, asi que cambiar de tema no obliga a repintar.

   Ambientacion: crepusculo en tema oscuro y media tarde en tema claro. Se
   evita la noche cerrada porque el contorno en tinta se pierde sobre fondos
   oscuros.
   ========================================================================== */

(function (root) {
  'use strict';

  const SPEC = {
    ramps: [
      { name: 'ink', colors: ['#1a1423'] },
      {
        name: 'sky',
        colors: ['#2b2142', '#4a2f5e', '#7a3f6e', '#b45a6a', '#e2845e', '#f4b46a'],
      },
      { name: 'foliage', colors: ['#1e3b2e', '#2e5e3c', '#4b8a42', '#88b85a'] },
      { name: 'wood', colors: ['#3a2820', '#5c3f2e', '#866044'] },
      { name: 'soil', colors: ['#2a1d1c', '#4a3228', '#6c4a36'] },
      // Pasto amarillo verdoso, distinto del follaje azul verdoso: asi los
      // tallos no se pierden contra la pradera.
      { name: 'grass', colors: ['#45591f', '#76902e', '#b4c24e'] },

      // Una rampa por especie de flor: las variantes son intercambiar rampa.
      { name: 'petalRose', colors: ['#7a2848', '#c4567c', '#f29ab6'] },
      { name: 'petalBlue', colors: ['#24407a', '#3f7cc4', '#90c6ee'] },
      { name: 'petalGold', colors: ['#8a5a16', '#d8a42c', '#f6e07c'] },
      { name: 'petalViolet', colors: ['#4a2a6e', '#8a54b8', '#c8a2ea'] },
      { name: 'petalWhite', colors: ['#6c6878', '#b8b4c6', '#f2eee6'] },

      // La pintura de carril usa la rampa del petalo blanco, casi identica.
      { name: 'asphalt', colors: ['#2a2a33', '#45454f', '#6e6e7c'] },

      // Celeste y naranja DUNNE como acentos, no como dominantes.
      { name: 'celeste', colors: ['#1f5a7a', '#4da8da', '#a8dcf4'] },
      { name: 'red', colors: ['#6e1f26', '#c43a3c', '#f07a6a'] },
      { name: 'orange', colors: ['#8a4a1c', '#e8843c', '#f6c08a'] },

      { name: 'white', colors: ['#ffffff'] },
    ],
    themes: {
      dark: {},
      light: {
        sky: ['#3d5a8a', '#5878a8', '#7f9cc4', '#b3c4d8', '#e8d2a8', '#f6e4b8'],
        soil: ['#3a2a24', '#5c4232', '#86604a'],
      },
    },
  };

  /** Rampas de petalo disponibles, en el orden en que aparecen las flores. */
  const PETAL_RAMPS = ['petalRose', 'petalBlue', 'petalGold', 'petalViolet', 'petalWhite'];

  const api = { SPEC: SPEC, PETAL_RAMPS: PETAL_RAMPS };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.NDPalette = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

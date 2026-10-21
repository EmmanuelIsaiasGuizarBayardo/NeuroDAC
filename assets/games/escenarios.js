/* ============================================================================
   NeuroDAC · escenarios de fondo

   Cada escenario pinta solo su silueta, sobre un buffer transparente, una vez
   por jardin. El cielo se dibuja aparte en cada cuadro, de modo que puede
   cambiar con la senal sin repintar el fondo.

   Los materiales se crean al construir el escenario, nunca al dibujarlo.
   ========================================================================== */

(function (root) {
  'use strict';

  /** Ancho para el que estan disenados los escenarios. */
  const DESIGN_W = 240;

  /**
   * Desplazamiento del diseno dentro del lienzo actual. El lienzo puede ser
   * mas ancho que el diseno: este queda centrado y sus perfiles, que son
   * funciones continuas, siguen hacia los lados. Cada `draw` lo fija.
   */
  let ox = 0;

  function centerFor(f) {
    ox = Math.round((f.w - DESIGN_W) / 2);
  }

  /** Columnas que cubren todo el lienzo, en coordenadas del diseno. */
  function leftEdge() {
    return -ox;
  }

  function rightEdge(f) {
    return f.w - 1 - ox;
  }

  function px(f, x, y, index) {
    E_.pixel(f, x + ox, y, index);
  }

  function rc(f, x, y, w, h, index) {
    E_.rect(f, x + ox, y, w, h, index);
  }

  /**
   * Rellena columnas desde un perfil superior hasta el horizonte.
   * x0 y x1 van en coordenadas del diseno; top(x) devuelve la altura del borde
   * superior en esa columna, o un valor mayor o igual al horizonte si la
   * columna esta vacia.
   */
  function fillProfile(f, x0, x1, horizon, top, tone) {
    const a = Math.max(-ox, x0);
    const b = Math.min(f.w - 1 - ox, x1);
    for (let x = a; x <= b; x++) {
      const t = Math.round(top(x));
      const col = x + ox;
      for (let y = Math.max(0, t); y < horizon; y++) {
        f.px[y * f.w + col] = tone(x, y, t);
      }
    }
  }

  // El motor llega al construir los escenarios; px y rc lo necesitan.
  let E_ = null;

  /* ------------------------------------------------------------- montanas */

  function montanas(E, pal) {
    const R = pal.ramps;
    // Lejos mas claro y cerca mas oscuro: perspectiva atmosferica.
    function far(x) {
      return 70 + 14 * Math.sin(x * 0.045 + 0.6) + 7 * Math.sin(x * 0.13 + 2.1);
    }
    function near(x) {
      return 94 + 8 * Math.sin(x * 0.06 + 3.3) + 4 * Math.sin(x * 0.19);
    }
    return {
      id: 'montanas',
      nombre: 'Montañas',
      draw(f, horizon) {
        centerFor(f);
        fillProfile(f, leftEdge(), rightEdge(f), horizon, far, function (x, y, t) {
          // Arista iluminada en las laderas que miran a la izquierda.
          if (y - t < 1 && far(x - 1) > far(x)) return R.sky[3];
          // Cuerpo solido para que conserve el borde; bruma tramada solo
          // cerca de la base, donde el aire es mas espeso.
          const haze = (y - (horizon - 14)) / 14;
          return haze > 0 && E.bayer(x, y) < haze * 0.6 ? R.sky[3] : R.sky[2];
        });
        fillProfile(f, leftEdge(), rightEdge(f), horizon, near, function (x, y) {
          return E.ditherTone(R.foliage, 0.6 - (horizon - y) * 0.01, x, y);
        });
      },
    };
  }

  /* --------------------------------------------------------- Chichen Itza */

  /**
   * El Castillo, Templo de Kukulcan. Rasgos que lo hacen reconocible a esta
   * escala: nueve cuerpos escalonados, escalinata central con alfardas,
   * templo con tres vanos y cabezas de serpiente al pie de la escalinata.
   */
  function chichen(E, pal) {
    const R = pal.ramps;
    const STONE_DARK = R.petalWhite[0];
    const STONE = R.petalWhite[1];
    const STONE_LIT = R.petalWhite[2];
    const SUN = R.sky[5];
    const DOOR = R.sky[0];

    const CX = 152;
    const TIERS = 9;
    const TIER_H = 4;
    const BASE_HW = 44;
    const INSET = 3.4;
    const STAIR_HW = 4;

    function jungle(x) {
      return 104 + 3 * Math.sin(x * 0.21) + 2 * Math.sin(x * 0.53 + 1.7);
    }

    function stone(x, hw) {
      // Lado derecho en sombra: la luz viene de arriba a la izquierda.
      return x > CX + hw * 0.4 ? STONE_DARK : STONE;
    }

    return {
      id: 'chichen',
      nombre: 'Chichén Itzá',
      draw(f, horizon) {
        centerFor(f);
        // Selva baja detras de la Gran Nivelacion.
        fillProfile(f, leftEdge(), rightEdge(f), horizon, jungle, function (x, y, t) {
          return y - t < 1 ? R.foliage[1] : R.foliage[0];
        });

        // Nueve cuerpos con talud: cada uno se angosta un poco hacia arriba.
        for (let i = 0; i < TIERS; i++) {
          const bottom = horizon - i * TIER_H;
          const hw = BASE_HW - i * INSET;
          for (let r = 0; r < TIER_H; r++) {
            const y = bottom - 1 - r;
            const w = hw - r * 0.6;
            for (let x = Math.round(CX - w); x <= Math.round(CX + w); x++) {
              // La fila superior de cada cuerpo recibe la luz del atardecer.
              const lip = r === TIER_H - 1;
              const lit = lip && x <= CX + w * 0.4;
              px(f, x, y, lip ? (lit ? SUN : STONE_LIT) : stone(x, w));
            }
          }
        }

        // Escalinata central con escalones alternados y alfardas oscuras.
        const platform = horizon - TIERS * TIER_H;
        for (let y = platform; y < horizon; y++) {
          for (let x = CX - STAIR_HW; x <= CX + STAIR_HW; x++) {
            px(f, x, y, (y & 1) === 0 ? STONE_LIT : STONE);
          }
          px(f, CX - STAIR_HW - 1, y, STONE_DARK);
          px(f, CX + STAIR_HW + 1, y, STONE_DARK);
        }

        // Cabezas de serpiente al pie de las alfardas.
        rc(f, CX - STAIR_HW - 4, horizon - 3, 4, 3, STONE_DARK);
        rc(f, CX + STAIR_HW + 1, horizon - 3, 4, 3, STONE_DARK);
        rc(f, CX - STAIR_HW - 4, horizon - 3, 4, 1, SUN);
        rc(f, CX + STAIR_HW + 1, horizon - 3, 4, 1, STONE_LIT);

        // Templo en la cima, con tres vanos y cresteria.
        const top = platform - 9;
        rc(f, CX - 11, top, 23, 9, STONE);
        rc(f, CX + 5, top, 7, 9, STONE_DARK);
        rc(f, CX - 12, top, 25, 1, SUN);
        rc(f, CX - 8, top + 4, 3, 5, DOOR);
        rc(f, CX - 2, top + 3, 5, 6, DOOR);
        rc(f, CX + 6, top + 4, 3, 5, DOOR);
        for (let x = CX - 10; x <= CX + 10; x += 4) rc(f, x, top - 2, 2, 2, STONE);
      },
    };
  }

  /* -------------------------------------------------------------- volcanes */

  /**
   * Iztaccihuatl y Popocatepetl como se ven desde la Ciudad de Mexico, mirando
   * al oriente: el Izta al norte, a la izquierda, con la cabeza de la mujer
   * dormida en su extremo norte y el pecho como cumbre mas alta; el Popo al
   * sur, a la derecha, mas alto y con fumarola.
   */
  function volcanes(E, pal) {
    const R = pal.ramps;
    const SNOW = R.petalWhite[2];
    const SNOW_SHADE = R.petalWhite[1];
    const ASH = R.petalWhite[0];

    const POPO_X = 184;
    const POPO_TOP = 52;
    const CRATER_HW = 5;

    function popo(x) {
      const d = Math.abs(x - POPO_X);
      if (d <= CRATER_HW) return POPO_TOP;
      // Laderas ligeramente concavas, como las de un estratovolcan.
      return POPO_TOP + Math.pow(d - CRATER_HW, 1.1) * 1.05;
    }

    function bump(x, cx, top, hw) {
      const u = (x - cx) / hw;
      return u * u < 1 ? top + (1 - Math.sqrt(1 - u * u)) * 28 : 999;
    }

    function izta(x) {
      // La cabellera: una pendiente larga que cae desde la cabeza hasta el
      // borde, para que la mujer dormida no empiece cortada.
      const hair = 101 - Math.min(1, x / 26) * 15;
      // El Paso de Cortes: el collado que une los pies con el Popo.
      const saddle = x > 140 ? 92 + (x - 140) * 0.06 : 999;
      return Math.min(
        hair,
        bump(x, 34, 81, 14),  // cabeza
        bump(x, 70, 72, 26),  // pecho, la cumbre mas alta
        bump(x, 108, 79, 20), // rodillas
        bump(x, 138, 86, 16), // pies
        saddle,
        x < 175 ? 94 : 999
      );
    }

    // Faldas boscosas al pie de ambos volcanes, de borde a borde.
    function foothills(x) {
      return 104 + 2.5 * Math.sin(x * 0.17 + 0.4) + 1.5 * Math.sin(x * 0.41);
    }

    function rock(x, y, cx, snowline, gullies) {
      const lit = x < cx;
      // La nieve depende de la altitud, no de la profundidad bajo el borde: asi
      // forma un casquete en la cima y no una franja por toda la ladera.
      // `gullies` marca cuanto baja la nieve por las canadas: mucho en el Popo,
      // poco en los campos de nieve continuos del Izta.
      const ragged = snowline + gullies * (Math.sin(x * 0.9) + 0.6 * Math.sin(x * 2.3));
      if (y < ragged || (y < ragged + 4 && E.bayer(x, y) < (ragged + 4 - y) / 4)) {
        return lit ? SNOW : SNOW_SHADE;
      }
      return lit ? R.sky[2] : R.sky[1];
    }

    return {
      id: 'volcanes',
      nombre: 'Iztaccíhuatl y Popocatépetl',
      draw(f, horizon) {
        centerFor(f);
        fillProfile(f, leftEdge(), 180, horizon, izta, function (x, y) {
          return rock(x, y, 70, 84, 1.2);
        });
        fillProfile(f, 110, rightEdge(f), horizon, popo, function (x, y) {
          return rock(x, y, POPO_X, POPO_TOP + 16, 3);
        });

        // Fumarola: densa en la boca y cada vez mas rala al subir y abrirse.
        for (let i = 0; i < 5; i++) {
          const cx = POPO_X + 2 + i * 5;
          const cy = POPO_TOP - 4 - i * 4;
          const r = 2.5 + i * 1.3;
          const alpha = 0.9 - i * 0.14;
          for (let y = Math.floor(cy - r); y <= cy + r; y++) {
            for (let x = Math.floor(cx - r * 1.4); x <= cx + r * 1.4; x++) {
              const u = (x - cx) / (r * 1.4);
              const v = (y - cy) / r;
              if (u * u + v * v <= 1 && E.bayer(x, y) < alpha) {
                px(f, x, y, v < -0.2 ? SNOW_SHADE : ASH);
              }
            }
          }
        }

        fillProfile(f, leftEdge(), rightEdge(f), horizon, foothills, function (x, y, t) {
          return y - t < 1 ? R.foliage[1] : R.foliage[0];
        });
      },
    };
  }

  const FACTORIES = [montanas, chichen, volcanes];

  /** Construye todos los escenarios con sus materiales, una sola vez. */
  function createAll(E, pal) {
    E_ = E;
    return FACTORIES.map(function (factory) {
      return factory(E, pal);
    });
  }

  /**
   * Elige el escenario del siguiente jardin sin repetir el inmediato anterior.
   * rand() es un generador sembrado; con la misma semilla, la misma secuencia.
   */
  function pickNext(count, previous, rand) {
    if (count < 2) return 0;
    let i = Math.floor(rand() * (count - 1));
    if (i >= previous) i++;
    return i;
  }

  const api = { createAll: createAll, pickNext: pickNext };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.NDEscenarios = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

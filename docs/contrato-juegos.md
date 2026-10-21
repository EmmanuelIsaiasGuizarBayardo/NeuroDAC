# Contrato entre la aplicación y un juego

Un juego de NeuroDAC es una página HTML dentro de un `<iframe>`. No sabe nada
de la diadema, de Dash ni del puerto serial: recibe un valor de señal y un
estado por `postMessage`, y dibuja. Cumpliendo este contrato, un juego se puede
rehacer por completo sin tocar la aplicación.

Del lado de la aplicación, el contrato lo emite `src/neurodac/game_page.py`.
Del lado del juego, lo recibe el motor en `assets/games/engine.js`. Una prueba
cruzada (`tests/test_motor.py`) genera los mensajes con el código de Python y
los entrega al receptor de JavaScript, de modo que los dos lados no pueden
divergir sin que el CI falle.

## Archivos

```
assets/games/
├── engine.js       # motor compartido: framebuffer, rasterizador, bucle, receptor
├── palette.js      # paleta compartida de 48 colores en rampas
├── escenarios.js   # fondos de Jardín
├── textos.js       # generado desde content/; no se edita a mano
├── jardin.js       # lógica de Jardín; corre en el navegador y en Node
├── jardin.html     # cascarón: carga los módulos y conecta el bucle
├── carrera.js      # lógica de Carrera; corre en el navegador y en Node
└── carrera.html    # cascarón de Carrera
```

Dash inyecta en la página principal todo `.js` que encuentre bajo `assets/`,
incluidas subcarpetas. Para que el motor no se ejecute dentro de la aplicación,
`interfaz.py` construye la app con `assets_path_ignore=["games"]`.
`assets_ignore` no sirve para esto: se compara solo contra el nombre del
archivo, nunca contra la ruta. Los archivos siguen servidos en
`/assets/games/...`, que es lo que carga el `<iframe>`.

## Encuadre

Un juego de pixel art declara su resolución lógica en el `GameSpec` de su
página (`logical_size`), y debe ser la misma que dibuja; una prueba compara
ambas. Con ella, `assets/encuadre.js`, que sí corre en la página principal,
ajusta el contenedor al mayor múltiplo entero de esa resolución que cabe en el
espacio disponible, contando la densidad de píxeles de la pantalla. El juego
llena entonces su `<iframe>` sin resto y con escalado entero; lo que sobra
queda fuera del recuadro, como margen de la página.

Si además declara `logical_width_max`, el juego **llena el ancho** de su
recuadro: la página elige el factor por el ancho disponible y el juego dibuja
tantas columnas lógicas como quepan, entre el mínimo y ese máximo, con la
altura lógica fija. Jardín va de 240 a 360 columnas con 180 de alto; los
escenarios centran su diseño de 240 y sus perfiles continúan hacia los lados.
El factor solo baja si el juego no cupiera en la pantalla y hubiera que
desplazarse para verlo. Para que la aparición de la barra de desplazamiento no
angoste la columna y produzca un vaivén, la página reserva su espacio con
`scrollbar-gutter: stable`.

Si declara también `logical_height_max`, el juego **llena los dos ejes**:
el factor es el mayor que deja ambos lados dentro de su mínimo, y el juego
dibuja tantas columnas y filas como quepan. Con la ventana más alta se ve más
juego, no píxeles más grandes. Carrera va de 144×192 a 176×288: en pantalla
completa se ve más carretera por delante. Aquí el motor puede elegir un factor
distinto al de la página; la prueba no exige que coincidan, exige que el
juego llene su lienzo sin franja y con su tamaño dentro de los límites.

La tolerancia del redondeo va en píxeles de dispositivo, no como fracción del
factor: con densidad 1.75 y factor 11, el punto flotante da 1979.999 por 1980,
y una fracción fija dejaba caer el factor un paso entero.

No se escala por CSS a un factor no entero para llenar el marco: sobre el
tramado Bayer del cielo eso produce *moiré*, bandas que no existen en el
dibujo. `tests/js/encuadre.js` verifica, para miles de combinaciones de
espacio y densidad (incluidas 1.25, 1.5 y 1.75), que el presentador del motor
elija el mismo factor que el encuadre y no deje franjas, aun si el navegador
redondea un píxel de dispositivo por debajo.

## Mensajes de la aplicación al juego

Un objeto plano. Los campos son opcionales salvo `source`; el juego conserva el
último valor recibido de cada uno.

```js
{
  source: "neurodac",   // obligatorio; cualquier otro mensaje se ignora
  signalValue: 63,      // número, o null si no hay dato
  ready: true,          // la simulación puede avanzar
  simulated: false,     // la fuente es la diadema simulada
  theme: "dark",        // "dark" | "light"
  keydown: "ArrowUp",   // tecla reenviada desde la página principal
  keyup: "ArrowUp"
}
```

| Campo         | Rango                 | Notas                                             |
|---------------|-----------------------|---------------------------------------------------|
| `signalValue` | 0 a 100, o `null`     | `meditation` en Jardín, `attention` en Carrera    |
| `ready`       | booleano              | ver compuerta                                     |
| `simulated`   | booleano              | el aviso en pantalla lo pone la página, no el juego |
| `theme`       | `"dark"`, `"light"`   | cambia la tabla de presentación, no la paleta     |

**La ausencia es explícita.** Sin dato, `signalValue` es `null` y el motor lo
guarda como `NaN`. Nunca se manda un número de relleno: un 50 de "todavía no
hay datos" entraría al juego como una meditación de 50.

Los mensajes solo se aceptan si vienen del mismo origen que sirve el juego, y
la página los envía con ese origen como destino.

Las teclas se reenvían porque un `<iframe>` no recibe eventos de teclado
mientras el foco está en la página principal. Se reenvía también `keyup`: sin
él, el juego cree que la tecla sigue oprimida y deja de registrar las
siguientes pulsaciones.

## Compuerta

La compuerta se aplica en dos niveles, como pide el estándar:

- **En la interfaz.** Una capa de Dash cubre el juego mientras la señal no
  sirve y muestra el texto `visitante` del estado, desde `content/`. Es lo que
  ve el público. La etiqueta y la pista del estado son solo para el personal y
  viven en el panel de calidad.
- **En la lógica.** El juego no avanza su simulación mientras
  `engine.isReady()` sea falso: ni la flor pierde salud ni el fantasma se
  adelanta.

`ready` es verdadero solo si el estado de la señal es `lista` **y** ya hay un
valor: la sesión puede quedar lista antes de que llegue el primer paquete
eSense. Al presionar Detener la página manda `ready: false` y `signalValue:
null`; antes de esto, el juego conservaba el último `ready: true` y seguía
corriendo con la señal congelada.

## Aviso de señal simulada

Mientras la fuente es la diadema simulada, la página muestra el aviso
`avisos.simulada` de `content/` como franja sobre el juego. Va sobre el lienzo
y no encima de él, para no tapar el marcador. Lo pone la página y no el juego,
para que valga igual con cualquier juego.

## Textos dentro del lienzo

Lo que un juego dibuja en su lienzo también es texto que ve el público, así que
vive en `content/`, en la sección `pantalla` de cada juego. Como el juego corre
en el navegador y no puede leer `content/`, `tools/generar_textos_juegos.py`
genera `assets/games/textos.js`. Se versiona porque Dash lo sirve tal cual;
`tests/test_content.py` falla si está desfasado del contenido, y el arnés del
juego falla si un texto usa un carácter que la fuente bitmap no puede dibujar.

## Modo autónomo

Un juego abierto directo en el navegador es autónomo: la compuerta se
considera abierta y la señal se controla con teclado. Dentro del `<iframe>` de
la aplicación nunca lo es; el motor lo decide comparando `self` con `top`. No
se decide por tiempo sin mensajes: el primer mensaje de la página puede llegar
antes de que el juego cargue y perderse, y el juego se declararía autónomo
dentro de la aplicación, con la flor marchitándose detrás de la compuerta. Sirve para desarrollar un juego sin levantar la
aplicación ni conectar la diadema. Las herramientas de depuración (rejilla,
acercamiento, hoja de sprites) solo existen en este modo: en la aplicación no
se muestran herramientas del personal.

## Teclas

Cada juego declara en su `GameSpec` las teclas que la página le reenvía;
`tests/test_game_page.py` verifica que el juego las atienda y que no atienda
otras.

| Tecla | Uso                                                  |
|-------|------------------------------------------------------|
| ← →   | jugabilidad (carriles en Carrera)                    |
| ↑ ↓   | simular la señal en modo autónomo (Jardín)           |
| W S   | simular la señal en modo autónomo (Carrera)          |
| G Z H | rejilla, acercamiento y hoja de sprites; solo modo autónomo |
| B     | siguiente escenario de Jardín; solo modo autónomo    |

Carrera atiende ← → dentro de la aplicación, porque cambiar de carril es la
jugabilidad. W y S, que simulan la atención, solo existen abierto fuera de
ella. Jardín no atiende ninguna tecla dentro de la aplicación: la señal viene solo de
la diadema o de la fuente simulada, que se declara en pantalla. Si las flechas
la alteraran, lo mostrado aparentaría ser meditación sin serlo. Un juego sobre
el motor declara sus teclas en `KEYS_USED`, y una prueba exige que coincidan
exactamente con las de su `GameSpec`.

## Reloj del reto

Cada juego mide cuánto tarda el visitante en completar su reto: las cinco
flores en Jardín, la meta en Carrera. El reloj corre en el marcador y, al
terminar, el aviso final muestra el tiempo y el mejor de la sesión, para que
los visitantes se comparen.

**El reloj solo cuenta el tiempo en que el juego avanza.** Si la compuerta se
cierra a media partida, por ejemplo porque la diadema perdió contacto, el
reloj se detiene con ella. Contar ese tiempo castigaría un mal contacto, no la
atención ni la meditación. El mejor tiempo es de la sesión: se pierde al
recargar la página. Los arneses verifican que el reloj no corra con la
compuerta cerrada ni durante una pausa, y que el tiempo guardado sea el jugado.

## Carrera: dificultad y equidad

La atención fija la velocidad de forma proporcional. Lo que se afina del rival
no es su velocidad sino **la atención que pide empatarlo** (`ATT_RIVAL`, hoy
56): su velocidad se deriva de ella. Con la mecánica proporcional, subir la
velocidad máxima con el rival fijo bajaría esa atención y lo volvería más
fácil sin que nadie lo notara.

Ninguna fila de obstáculos bloquea los tres carriles. Una fila doble deja uno
libre, no admite autos lentos cerca, y las filas de los siguientes
`DOUBLE_GUARD_M` metros respetan ese carril: dos filas dobles seguidas con
huecos en lados opuestos pedirían cruzar dos carriles en un instante. El arnés
lo verifica cuadro por cuadro en carreras completas de los tres paisajes, y
falla si se viola.

Con un bot que mira por delante en proporción a su velocidad, los valores
actuales dan de 3.5 a 5.5 choques por carrera; con atención alta se gana
siempre, y con atención apenas arriba de la raya del rival se gana la mitad de
las veces, que es donde esquivar debe decidir. Las constantes para afinar
están juntas al inicio de `assets/games/carrera.js`.

## Reglas de render

Las garantiza el motor si se usa como está:

- Todo se pinta en un framebuffer indexado a resolución lógica fija; ningún
  píxel sale de la paleta. El Canvas solo recibe el cuadro final, escalado por
  un factor entero en píxeles de dispositivo.
- Sin trazados del Canvas, `fillText`, gradientes ni `shadowBlur` en el
  contenido del juego.
- Materiales, LUTs y textos se crean al cargar, nunca dentro de un bucle de
  píxeles o de cuadros. El arnés de capturas mide la alocación por cuadro.
- Las piezas de fondo que forman una sola silueta comparten identificador de
  pieza; si no, el contorno interior marca una grieta entre ellas.

## Verificación

```powershell
node tools/capturas_motor.js
node tools/capturas_jardin.js
node tools/capturas_carrera.js
uv run pytest tests/test_motor.py tests/test_game_page.py -q
```

`capturas_jardin.js` no solo dibuja: ejercita el juego con los mismos mensajes
que manda la página y falla si la compuerta no detiene la simulación, si la
mecánica no es la anterior, si la escena no responde a la calma o si el
teclado altera la señal dentro de la aplicación. Para medir también la
alocación por cuadro hay que impedir que el recolector corra durante la
medición, o la cifra sale engañosamente baja:

```powershell
node --expose-gc --min-semi-space-size=256 --max-semi-space-size=256 tools/capturas_jardin.js
```

El arnés vuelca capturas en ambos temas a `results/capturas/` y falla si algún
píxel del cuadro final sale de la paleta; las entradas sin usar de la paleta
PNG van en magenta, de modo que cualquier fuga se ve a simple vista.

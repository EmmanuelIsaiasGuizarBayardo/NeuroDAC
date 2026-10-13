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
├── jardin.html     # un archivo por juego, con su resolución lógica
└── carrera.html
```

Dash inyecta en la página principal todo `.js` que encuentre bajo `assets/`,
incluidas subcarpetas. Para que el motor no se ejecute dentro de la aplicación,
`interfaz.py` construye la app con `assets_path_ignore=["games"]`.
`assets_ignore` no sirve para esto: se compara solo contra el nombre del
archivo, nunca contra la ruta. Los archivos siguen servidos en
`/assets/games/...`, que es lo que carga el `<iframe>`.

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

Mientras la fuente es la diadema simulada, la página muestra encima del juego
el aviso `avisos.simulada` de `content/`. Lo pone la página y no el juego, para
que valga igual con cualquier juego.

## Modo autónomo

Si no llega ningún mensaje con `source: "neurodac"` en 1.5 s, el juego asume
que se abrió directo en el navegador: la compuerta se considera abierta y la
señal se controla con teclado. Sirve para desarrollar un juego sin levantar la
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
uv run pytest tests/test_motor.py tests/test_game_page.py -q
```

El arnés vuelca capturas en ambos temas a `results/capturas/` y falla si algún
píxel del cuadro final sale de la paleta; las entradas sin usar de la paleta
PNG van en magenta, de modo que cualquier fuga se ve a simple vista.

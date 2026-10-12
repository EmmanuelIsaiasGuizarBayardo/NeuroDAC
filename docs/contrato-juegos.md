# Contrato entre la aplicación y un juego

Un juego de NeuroDAC es una página HTML dentro de un `<iframe>`. No sabe nada
de la diadema, de Dash ni del puerto serial: recibe un valor de señal y un
estado por `postMessage`, y dibuja. Cumpliendo este contrato, un juego se puede
rehacer por completo sin tocar la aplicación.

## Archivos

```
assets/games/
├── engine.js     # motor compartido: framebuffer, rasterizador, bucle, contrato
├── palette.js    # paleta compartida de 48 colores en rampas
├── jardin.html   # un archivo por juego, con su resolución lógica
└── carrera.html
```

Dash inyecta en la página principal todo `.js` que encuentre bajo `assets/`,
incluidas subcarpetas. Para que el motor no se ejecute dentro de la aplicación,
`interfaz.py` debe construir la app con:

```python
dash.Dash(__name__, ..., assets_path_ignore=["games"])
```

`assets_ignore` no sirve para esto: se compara solo contra el nombre del
archivo, nunca contra la ruta. Los archivos siguen servidos en
`/assets/games/...`, que es lo que carga el `<iframe>`.

## Mensajes de la aplicación al juego

Un solo tipo de mensaje, un objeto plano. Los campos son opcionales; el juego
conserva el último valor recibido de cada uno.

```js
{
  source: "neurodac",     // obligatorio; cualquier otro mensaje se ignora
  signal: 63,             // número, ver rangos
  gate: "calibrando",     // estado de la señal, ver compuerta
  progress: 0.4,          // avance de calibración, de 0 a 1
  theme: "dark",          // "dark" | "light"
  keydown: "ArrowLeft",   // tecla reenviada desde la página principal
  keyup: "ArrowLeft"
}
```

| Campo      | Rango                         | Notas                                          |
|------------|-------------------------------|------------------------------------------------|
| `signal`   | 0 a 100                       | `meditation` en Jardín, `attention` en Carrera |
| `gate`     | ver tabla de compuerta        | valores de `SignalState` en `acquisition.py`   |
| `progress` | 0 a 1                         | solo tiene sentido con `gate: "calibrando"`    |
| `theme`    | `"dark"`, `"light"`           | cambia la tabla de presentación, no la paleta  |

Las teclas se reenvían porque un `<iframe>` no recibe eventos de teclado
mientras el foco está en la página principal. El juego escucha también sus
propios eventos de teclado, para cuando el foco sí está dentro.

## Compuerta

Mientras `gate` sea distinto de `"lista"`, **la simulación no avanza**: ni la
flor pierde salud ni el fantasma se adelanta. El juego muestra al visitante un
mensaje corto con la fuente bitmap. La instrucción detallada para el operador
no es del juego; vive en el panel de calidad de Dash.

| `gate`            | Mensaje al visitante          |
|-------------------|-------------------------------|
| `desconectada`    | (sin mensaje: el operador aún no conecta) |
| `sin_datos`       | Esperando la diadema          |
| `sin_contacto`    | Acomódate la diadema          |
| `contacto_pobre`  | Acomódate la diadema          |
| `calibrando`      | Quédate quieto, barra con `progress` |
| `lista`           | (se abre la compuerta)        |

## Modo autónomo

Si no llega ningún mensaje con `source: "neurodac"` en 1.5 s, el juego asume
que se abrió directo en el navegador: la compuerta se considera abierta y la
señal se controla con teclado. Sirve para desarrollar un juego sin levantar la
aplicación ni conectar la diadema.

## Teclas reservadas

| Tecla        | Uso                                             |
|--------------|-------------------------------------------------|
| ← →          | jugabilidad (carriles en Carrera)               |
| ↑ ↓          | simular la señal en modo autónomo (Jardín)      |
| W S          | simular la señal en modo autónomo (Carrera)     |
| G            | rejilla de píxeles                              |
| Z            | acercamiento entero al objeto principal         |
| H            | hoja de sprites 1:1                             |

## Reglas de render

Estas son las que el motor ya garantiza si se usa como está:

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
```

Vuelca capturas en ambos temas y falla si algún píxel del cuadro final sale de
la paleta. Las entradas sin usar de la paleta PNG van en magenta, de modo que
cualquier fuga se ve a simple vista. Las capturas van a `results/capturas/`,
que la plantilla del proyecto ya excluye del control de versiones.

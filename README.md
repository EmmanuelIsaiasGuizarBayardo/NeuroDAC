# NeuroDAC

Demostrador Académico de Neuroingeniería de la **División Universitaria de
Neuroingeniería (DUNNE)**, UNAM. Es una aplicación web que visualiza EEG en
vivo desde una diadema NeuroSky MindWave Mobile 2 y lo convierte en dos
ejercicios de neurofeedback para divulgación.

Se opera en museos y eventos: hay un operador de DUNNE frente a la consola y
un visitante con la diadema puesta. Ese contexto explica varias decisiones de
diseño que de otro modo parecerían exageradas.

---

## Requisitos

| | |
|---|---|
| Python | 3.12, fijado en `.python-version` |
| Gestor | [uv](https://docs.astral.sh/uv/) |
| Sistema | Windows 10 para usar la diadema; cualquiera para desarrollar |
| Hardware | NeuroSky MindWave Mobile 2 (opcional: hay diadema simulada) |

En Windows 11 la conexión Bluetooth con la diadema se interrumpe con
frecuencia. Para demostraciones se usa Windows 10.

---

## Puesta en marcha

```powershell
git clone https://github.com/EmmanuelIsaiasGuizarBayardo/NeuroDAC.git
cd NeuroDAC
uv sync
uv run python tools/preparar_datos.py
uv run python interfaz.py
```

`uv sync` descarga Python 3.12 si no lo tienes e instala el paquete en modo
editable. La aplicación queda en <http://127.0.0.1:8050>.

**No hace falta la diadema para desarrollar.** Cada página trae un selector de
fuente con la opción *Simulada*, que genera tramas ThinkGear sintéticas y
recorre los mismos estados que el hardware real.

### Datos

`data/` no se versiona. `tools/preparar_datos.py` regenera el registro de
demostración desde el dataset público; si falta el archivo de origen, el
script dice qué descargar y dónde ponerlo. La aplicación arranca aunque no
haya datos: la página de visualización muestra el comando en lugar de fallar.

### Banderas útiles

```powershell
uv run python interfaz.py --debug          # recarga al editar
uv run python interfaz.py --host 0.0.0.0   # visible desde otra máquina
uv run python interfaz.py --port 8060
```

`--debug` está apagado por omisión: el recargador de Flask importa el módulo
dos veces, lo que duplica la memoria del registro EEG y puede abrir el puerto
serial dos veces.

---

## Arquitectura

### Cadena de adquisición

```
serial.Serial(COM, 115200)          SerialSource
  └─ hilo lector                    Session._read_loop
       └─ ThinkGearParser.feed()    valida checksum, descarta tramas corruptas
            └─ Session._handle()    enruta el evento
                 ├─ deque           muestras de la señal seleccionada
                 └─ estado          poor_signal, tasa, antigüedad
                      └─ dcc.Interval (100–200 ms)
                           └─ callback de Dash
                                └─ gráfica  +  postMessage al iframe
```

No hay Web Serial ni WebSockets: el navegador nunca toca el puerto, todo pasa
por *polling* HTTP contra el servidor Flask local.

El hilo lector **empuja** cada muestra a la cola en cuanto llega. No hay un
segundo hilo encuestando atributos, de modo que el muestreo es exacto.

### Una sesión por fuente

`neurodac.acquisition.registry` es el único dueño de los puertos. Las páginas
nunca abren nada: piden una sesión con `registry.acquire(source, signal)`.
Dos páginas que pidan el mismo COM reciben **la misma sesión**, lo que elimina
por construcción el bloqueo del puerto al navegar.

El registro indexa por nombre de fuente, así que una segunda diadema sería
otra entrada del diccionario y no otra variable global.

### Estado de la señal

`Session.quality` devuelve un `Quality` con el estado agregado, `poor_signal`,
la tasa de tramas por segundo y la antigüedad de la última. Los estados son:

| Estado | Significado |
|---|---|
| `desconectada` | no hay sesión |
| `sin_datos` | no llegan tramas desde hace más de 3 s |
| `sin_contacto` | `poor_signal >= 200`, el electrodo no toca piel |
| `contacto_pobre` | `poor_signal > 50`, señal ruidosa |
| `calibrando` | contacto bueno; eSense establece su línea base (10 s) |
| `lista` | la señal sirve |

Perder el contacto **o** sufrir un corte de datos reinicia la calibración: en
ambos casos el algoritmo eSense pierde su línea base.

### La compuerta

Los juegos no corren hasta que el estado es `lista`. El bloqueo es doble: un
velo sobre el lienzo en Dash, y dentro del juego la simulación no avanza
mientras `ready` sea falso.

Es necesario porque `attention` y `meditation` se inicializan en cero, que es
un valor válido dentro del rango 0–100. Sin la compuerta, un cero de "todavía
no hay datos" entra como si fuera concentración nula.

### Páginas

Las cuatro siguen el mismo patrón: no abren puertos, no lanzan hilos, no usan
variables globales. `neurodac.ui` aporta el panel de conexión y el bloque de
calidad; `neurodac.game_page` arma las páginas de juego completas, de modo que
`pages/jardin.py` y `pages/carrera.py` solo declaran un `GameSpec`.

El HTML de los juegos vive en `assets/games/*.html` y se carga en un `iframe`
del mismo origen. La comunicación es por `postMessage`, con tres campos:
`signalValue`, `theme` y `ready`.

### Datos

`neurodac.eeg_io` garantiza dos invariantes en todo registro: amplitudes en
microvoltios y media cero por canal. La segunda importa: un registro con
*offset* DC se dibuja como una línea plana pegada al borde del eje.

---

## Estructura

```
interfaz.py                 Punto de entrada. Único ejecutable.
pyproject.toml              Dependencias declaradas.
uv.lock                     Resolución exacta. Fuente de verdad del entorno.

src/neurodac/
  thinkgear.py              Parser del protocolo. Puro: sin serial ni hilos.
  acquisition.py            Sesiones, registro, estado de la señal.
  simulator.py              Diadema simulada, sembrable, con escenarios de falla.
  eeg_io.py                 Lectura de EEGLAB y CSV.
  ui.py                     Panel de conexión, bloque de calidad, compuerta.
  game_page.py              Armado de las páginas de juego.

pages/                      Una página de Dash por archivo.
assets/                     CSS, logo, y el HTML de los juegos.
tools/preparar_datos.py     Regenera el registro de demostración.
tests/                      Pruebas. Ninguna necesita hardware.
data/                       No versionado.
```

---

## La diadema

La MindWave Mobile 2 **no usa dongle USB**: se empareja por Bluetooth como
dispositivo genérico, no como audífono.

1. Enciende la diadema; el LED azul parpadea.
2. Configuración → Dispositivos → Agregar Bluetooth → *MindWave Mobile*.
   Código de emparejamiento: `0000`.
3. Windows asigna un puerto COM. Para saber cuál: Administrador de
   Dispositivos → Puertos (COM y LPT) → *Standard Serial over Bluetooth link*.
4. Ese número (`COM3`, `COM4`, …) es lo que se escribe en la interfaz.

La terminal es el instrumento de diagnóstico: muestra el estado del enlace y
los errores del hilo lector. Si la aplicación deja de responder, ahí está la
causa; `CTRL + C` y volver a levantar suele bastar.

La compatibilidad con dos diademas simultáneas está prevista en el diseño del
registro, pero **no está implementada ni probada**.

---

## Pruebas

```powershell
uv run pytest -q                      # todo
uv run pytest tests/test_thinkgear.py -q
```

Ninguna prueba necesita la diadema. Se apoyan en tres dobles: tramas
sintéticas para el parser, una fuente guionizada con reloj controlado para la
máquina de estados, y el simulador completo para la ruta de punta a punta.

Lo que se prueba es lo que importa, no lo fácil: el protocolo ThinkGear
(checksum, códigos extendidos, flujo fragmentado y sucio), las transiciones de
estado de la señal, la propiedad del puerto, y la coherencia entre las teclas
declaradas en `GameSpec` y las que atiende el JavaScript.

---

## Convenciones

**Estilo.** PEP 8 verificado con `ruff`. Type hints en las firmas, docstrings
en estilo NumPy, nombres en inglés, comentarios en español cuando explican
algo que el código no dice por sí solo.

```powershell
uv run ruff check . --fix
uv run ruff format .
```

**Commits.** Verbo en infinitivo, sin punto final, menos de 72 caracteres, con
ámbito al inicio:

```
adquisición: centralizar sesiones por puerto
juegos: mover el HTML a assets y bloquear el arranque sin señal
```

**Activos generados.** Nada que produzca un script se edita a mano ni se
versiona. Si algo hay que cambiar, se edita el script y se vuelve a correr.

**Dependencias.** `uv add <paquete>`, nunca `pip install` suelto, o el cambio
no queda en `uv.lock`.

---

## Cómo contribuir

1. *Fork* y rama desde `main`.
2. `uv sync` y confirma que `uv run pytest -q` pasa antes de tocar nada.
3. Las pruebas van con el cambio, no después.
4. `uv run ruff check . --fix` y `uv run ruff format .` antes del commit.
5. *Pull request* describiendo qué cambia y cómo lo verificaste.

El CI corre `ruff` y `pytest` en cada *push* y cada *pull request*.

Si tu cambio toca la adquisición y no tienes diadema, usa la fuente simulada y
dilo en el *pull request*; alguien con hardware lo verifica antes de fusionar.

---

## Licencia

| Qué | Licencia |
|---|---|
| Código: Python, JavaScript, CSS, HTML | **MIT** (`LICENSE`) |
| Contenido didáctico y manual del operador | **CC BY 4.0** (`LICENSE-CONTENIDO.md`) |
| Logotipo de DUNNE | reservado; ver `LICENSE-CONTENIDO.md` |

Las dos licencias permiten *fork*, modificación, redistribución y uso con
cualquier finalidad, incluso comercial, y las dos exigen mantener el crédito.

Se separan porque las licencias Creative Commons no son adecuadas para
software y las de software no están pensadas para textos didácticos.

---

## Datos y licencias

El registro de demostración proviene de **UC San Diego Resting State EEG Data
from Patients with Parkinson's Disease**, OpenNeuro
[`ds002778`](https://openneuro.org/datasets/ds002778/versions/1.0.2) v1.0.2,
licencia **CC0**. Autores: Rockhill, Jackson, George, Aron y Swann.

Los curadores piden que se les escriba antes de someter a revisión por pares
un manuscrito que use estos datos.

**Señal de personas.** En operación, el EEG de los asistentes es efímero: se
mantiene en memoria mientras dura la sesión y no se escribe a disco. Ningún
componente de la aplicación persiste señal. Este repositorio no contiene datos
personales.

---

## Créditos

Los roles de cada persona, en taxonomía CRediT, están en
[`CREDITS.md`](CREDITS.md). Para citar el proyecto, GitHub genera la
referencia desde `CITATION.cff` con el botón **Cite this repository**.

<!-- Archivo generado por tools/generar_manual.py desde
     content/divulgacion.es.json. No editar a mano: los cambios se
     pierden en la siguiente regeneración. -->

# Manual del operador

*NeuroDAC · Demostrador Académico de Neuroingeniería · DUNNE*

Este manual es para quien opera NeuroDAC frente al público: en un museo, una feria de ciencias o un taller. No hace falta saber programar.

La demostración tiene dos personas: tú frente a la consola y un visitante con la diadema puesta. Tu trabajo es que la señal sea buena y explicar qué está viendo.

---

## Antes del evento

1. Carga la diadema por completo. Dura unas ocho horas y no avisa antes de apagarse.
2. Lleva toallitas con alcohol: limpiar la frente del visitante mejora el contacto más que cualquier ajuste.
3. Verifica en tu computadora que la aplicación levanta y que la fuente simulada funciona. Si algo falla, es mejor descubrirlo en casa.
4. Prueba el emparejamiento Bluetooth en la computadora que vas a usar. Los puertos COM cambian entre máquinas.
5. Si hay proyector, revisa que el texto se lea desde el fondo del salón. El tema claro suele verse mejor con luz ambiental.

## Colocar la diadema

1. Limpia la frente del visitante con una toallita y espera a que seque.
2. Coloca el sensor sobre la frente, encima de la ceja izquierda, apartando el cabello. El sensor debe tocar piel, no pelo.
3. Engancha el clip en el lóbulo de la oreja izquierda. Ese clip es la referencia eléctrica: sin él no hay señal, aunque el sensor esté perfecto.
4. Pide al visitante que se acomode y deje de moverse. Apretar la mandíbula o parpadear fuerte ensucia la señal.

> Si el visitante trae maquillaje en la frente o mucho fijador en el cabello, el contacto será pobre y no hay ajuste que lo arregle. Conviene decirlo con naturalidad y ofrecer la fuente simulada.

## Durante la demostración

1. Levanta la aplicación y abre el navegador. La terminal debe quedar visible: ahí aparecen los errores.
2. Elige la fuente, escribe el puerto COM y presiona Conectar.
3. Observa el indicador de calidad. Hasta que diga Lista, los juegos no arrancan.
4. Mientras calibra, aprovecha para explicar qué es el EEG. Toma unos diez segundos.
5. Al terminar con un visitante, presiona Detener antes de pasar al siguiente.

## Qué significa cada estado

El indicador de calidad es lo primero que hay que mirar. Cada estado
trae qué hacer, no solo qué pasa.

| Estado | Qué hacer |
|---|---|
| **Desconectada** | Elige la fuente y presiona Conectar. |
| **Sin datos** | El puerto está abierto pero no llegan tramas. Revisa que la diadema siga encendida y emparejada. |
| **Sin contacto** | El electrodo frontal no toca la piel. Acomoda la diadema en la frente y verifica el clip de la oreja. |
| **Contacto pobre** | Hay contacto pero con ruido. Aparta el cabello de la frente y revisa que el clip haga contacto con el lóbulo. |
| **Calibrando** | La diadema está estableciendo su línea base. Pide al visitante que se quede quieto unos segundos. |
| **Lista** | Señal estable. |

## Qué explicar de cada banda

Son los textos que la aplicación muestra en el panel lateral. Sirven
de guion cuando el visitante pregunta qué está viendo.

### Señal EEG sin procesar

Lo que ves aquí es la actividad eléctrica de un cerebro tal cual la capta el electrodo. Es como escuchar todas las conversaciones de un salón al mismo tiempo; una mezcla de muchas frecuencias distintas. Los picos grandes suelen ser artefactos, como parpadeos o movimientos musculares, y no actividad cerebral real.

### Ondas Delta, las más lentas

Las ondas delta son como el latido profundo del cerebro dormido. Aparecen durante el sueño profundo, cuando el cuerpo se dedica a repararse. Si las vemos en alguien despierto podría indicar que algo no anda bien; por eso los neurólogos les prestan mucha atención.

### Ondas Theta, soñar despierto

Theta es la frecuencia de la creatividad y la ensoñación. Aparece cuando la mente divaga, durante la meditación profunda, o justo antes de quedarse dormido. El hipocampo, la región encargada de formar memorias, usa este ritmo para consolidar lo aprendido durante el día.

### Ondas Alpha, relajación consciente

Fueron las primeras que se descubrieron en el EEG, en 1929. Aparecen al cerrar los ojos y relajarse; es como si la corteza visual dijera que no hay nada que ver y conviniera descansar. Al abrir los ojos o ponerse a pensar desaparecen de inmediato, y por eso se usan tanto en neurofeedback para enseñar a relajarse.

### Ondas Beta, pensamiento activo

Beta es la frecuencia del cerebro concentrado. Al resolver un problema de matemáticas, leer con atención o sostener una conversación, el cerebro vibra en beta. Hay dos tipos: beta baja, de concentración calmada, y beta alta, ligada al estrés. En las interfaces cerebro-computadora es la banda clave para detectar intenciones de movimiento.

### Ondas Gamma, el pegamento de la conciencia

Gamma es la más rápida y la más misteriosa. Se cree que es responsable de pegar toda la información sensorial en una experiencia unificada. Cuando ves un gato, gamma une su forma, color, sonido y textura en un solo percepto. Es difícil de medir porque los músculos de la cara generan señales parecidas.

## Los dos juegos

### Jardín Mental

El Jardín Mental es un ejercicio de *neurofeedback* basado en meditación. La señal de meditación de la diadema hace crecer las flores: por encima de 55 la flor sube de etapa, por debajo de 45 pierde salud. El objetivo es hacer florecer las cinco manteniendo la calma, no concentrándose con fuerza.

El juego no arranca hasta que la señal sirve. Antes de eso, un cero de "todavía no hay datos" entraba como si fuera meditación nula y la flor se marchitaba sola en unos diecisiete segundos.

### Carrera Neural

La Carrera Neural es un ejercicio de *neurofeedback* basado en atención. La señal de atención de la diadema controla la velocidad del coche: a mayor concentración sostenida, más rápido avanza. Las flechas cambian de carril para esquivar obstáculos, y chocar cuesta velocidad durante unos segundos.

El coche gris es el rival, que avanza a velocidad constante. Como el juego no arranca hasta que la señal sirve, nadie empieza la carrera con medio kilómetro de desventaja; volver de una caída reinicia la carrera en lugar de continuarla perdida.

## Tipos de señal

Lo que ofrece el selector. Para demostrar, `raw` es la más vistosa;
`attention` y `meditation` son las que controlan los juegos.

| Señal | Qué es |
|---|---|
| `raw` | Señal cruda del electrodo; mezcla de todas las frecuencias cerebrales. |
| `attention` | Índice propietario de NeuroSky (0–100) que estima el nivel de concentración. |
| `meditation` | Índice propietario (0–100) que refleja estados de relajación y calma mental. |
| `blink` | Detecta artefactos de parpadeo; útil para interfaces BCI basadas en EOG. |
| `delta` | Potencia en banda delta (0.5–4 Hz); sueño profundo. |
| `theta` | Potencia en banda theta (4–8 Hz); meditación y memoria. |
| `low-alpha` | Alpha baja (8–10 Hz); relajación cortical temprana. |
| `high-alpha` | Alpha alta (10–12 Hz); relajación cortical profunda. |
| `low-beta` | Beta baja (12–18 Hz); ritmo sensoriomotor (SMR). |
| `high-beta` | Beta alta (18–30 Hz); actividad mental intensa. |
| `low-gamma` | Gamma baja (30–40 Hz); procesamiento cognitivo. |
| `mid-gamma` | Gamma media (40–50 Hz); binding perceptual. |

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| No conecta y dice que el puerto está ocupado | Otra ventana de la aplicación tiene el puerto abierto. Ciérrala, o presiona Detener en la otra página. |
| Conecta pero nunca pasa de Sin datos | La diadema está apagada o se desemparejó. Apágala y enciéndela; si sigue, vuelve a emparejarla desde Windows. |
| La señal se corta a media demostración | Es lo más común en Windows 11. Presiona Detener, Conectar de nuevo, y si se repite cambia a la fuente simulada y sigue la demostración. |
| La aplicación deja de responder | Mira la terminal: ahí está la causa. Ciérrala con CTRL + C y vuelve a levantarla; tarda unos segundos. |
| No hay diadema disponible o el visitante no quiere ponérsela | Usa la fuente simulada. Los juegos funcionan igual y la explicación no cambia. |

## Al terminar

1. Presiona Detener y cierra la aplicación con CTRL + C en la terminal.
2. Apaga la diadema. No se apaga sola y se queda sin batería.
3. Guarda el clip de oreja: es la pieza que más se pierde.

> La señal del visitante no se guarda en ningún momento. Vive en la memoria mientras dura la sesión y desaparece al detener. Si alguien pregunta, esa es la respuesta.

---

Contenido bajo CC BY 4.0; ver `LICENSE-CONTENIDO.md`. La documentación
para quien desarrolla está en el `README.md` del repositorio.

# Créditos

NeuroDAC es un proyecto de la **División Universitaria de Neuroingeniería
(DUNNE)**, Facultad de Medicina, Universidad Nacional Autónoma de México.

Los roles siguen la taxonomía [CRediT](https://credit.niso.org/), que es la
que usan las revistas académicas. Se listan explícitos para que la
contribución de cada quien quede documentada y no se diluya en el nombre de la
organización.

---

## Contribuciones

### Emmanuel Isaías Guízar Bayardo

*Conceptualization · Software · Methodology · Validation · Data curation ·
Visualization · Writing – original draft · Project administration*

Arquitectura del proyecto y de la capa de adquisición. Reimplementación del
parser del protocolo ThinkGear. Migración de ambos juegos de Pygame a HTML5
Canvas e integración en la aplicación web. Diadema simulada y suite de
pruebas. Capa de datos EEG. Estructura del repositorio, entorno reproducible y
documentación. Presidencia de DUNNE durante el desarrollo.

### Emilio Hernández Vargas

*Software*

Diseño e implementación originales de los dos videojuegos, Jardín Mental y
Carrera Neural, en Pygame. La mecánica de juego, los umbrales de control y la
progresión de ambos se conservan de esa versión.

### Jesús Hernández Cabañas

*Conceptualization · Project administration*

Concepción y liderazgo inicial del proyecto.

### Luis Santiago Medina Nava

*Writing – review & editing*

Redacción y revisión de la documentación del proyecto.

### Karen Cortés Cárdenas

*Writing – review & editing*

Redacción y revisión de la documentación del proyecto.

### André Emiliano Flores Serralta

*Writing – review & editing*

Redacción y revisión de la documentación del proyecto.

---

## Trabajo de terceros

### Protocolo ThinkGear

`src/neurodac/thinkgear.py` se reimplementó desde cero contra la
especificación *ThinkGear Serial Stream Guide* de NeuroSky, tomando como
referencia inicial
[sr-gus/neurosky_mm2_headset](https://github.com/sr-gus/neurosky_mm2_headset).

No es una adaptación de ese código: la implementación actual valida el
checksum, termina en presencia de códigos extendidos y decodifica las bandas
espectrales en base 256. Se le reconoce como punto de partida.

### Registro EEG de demostración

**UC San Diego Resting State EEG Data from Patients with Parkinson's Disease**,
OpenNeuro [`ds002778`](https://openneuro.org/datasets/ds002778/versions/1.0.2)
v1.0.2, licencia CC0.

Rockhill, A. P., Jackson, N., George, J., Aron, A., & Swann, N. C. (2021).
*UC San Diego Resting State EEG Data from Patients with Parkinson's Disease*
[Conjunto de datos]. OpenNeuro. https://doi.org/10.18112/openneuro.ds002778

Los curadores piden que se les escriba antes de someter a revisión por pares
un manuscrito que use estos datos.

### Bibliotecas

Dash y Plotly (MIT), MNE-Python (BSD-3), NumPy y pandas (BSD-3), pyserial
(BSD-3), Bootstrap a través de dash-bootstrap-components (MIT). Las versiones
exactas están en `uv.lock`.

---

## Cómo citar

El repositorio incluye `CITATION.cff`, así que GitHub genera la cita desde el
botón **Cite this repository**. En APA 7:

> Guízar Bayardo, E. I., Hernández Vargas, E., Hernández Cabañas, J., Medina
> Nava, L. S., Cortés Cárdenas, K., & Flores Serralta, A. E. (2026).
> *NeuroDAC: Demostrador Académico de Neuroingeniería* (versión 2.0.0)
> [Software]. División Universitaria de Neuroingeniería, UNAM.
> https://github.com/EmmanuelIsaiasGuizarBayardo/NeuroDAC

---

## Cómo se actualiza este archivo

Quien contribuya agrega su nombre con los roles CRediT que correspondan, en el
mismo *pull request* que su aportación. Los roles describen lo que se hizo, no
la jerarquía; una persona puede tener uno o varios.

`CITATION.cff` debe mantenerse en correspondencia con la lista de arriba: es
el archivo que leen GitHub y Zenodo.

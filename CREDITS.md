# Créditos

NeuroDAC es un proyecto de la **División Universitaria de Neuroingeniería
(DUNNE)**, Departamento de Ingeniería en Sistemas Biomédicos (DISB), División de
Ingeniería Mecánica e Industrial (DIMEI), Facultad de Ingeniería (FI),
Universidad Nacional Autónoma de México (UNAM).

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
documentación.

### Emilio Hernández Vargas

*Software*

Diseño e implementación originales de los dos videojuegos, Jardín Mental y
Carrera Neural, en Pygame. La mecánica de juego, los umbrales de control y la
progresión de ambos se conservan de esa versión.

### Jesús Hernández Cabañas

*Conceptualization · Project administration*

Concepción y liderazgo inicial del proyecto.

### Luis Santiago Medina Nava

*Writing – original draft · Writing – review & editing*

Redacción y revisión de la documentación del proyecto.

### Karen Cortés Cárdenas

*Writing – original draft · Writing – review & editing*

Redacción y revisión de la documentación del proyecto.

### André Emiliano Flores Serralta

*Writing – original draft · Writing – review & editing*

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

La referencia formal, con el DOI de la versión usada, está en `CITATION.cff`.

Los curadores piden que se les escriba antes de someter a revisión por pares
un manuscrito que use estos datos.

### Bibliotecas

Las bibliotecas y sus versiones exactas están en `pyproject.toml` y `uv.lock`.

---

## Cómo citar

GitHub genera la referencia desde `CITATION.cff` con el botón **Cite this
repository**. No se mantiene una cita escrita a mano: se desfasaría con cada versión.

---

## Cómo se actualiza este archivo

Quien contribuya agrega su nombre con los roles CRediT que correspondan, en el
mismo *pull request* que su aportación. Los roles describen lo que se hizo, no
la jerarquía; una persona puede tener uno o varios.

`tests/test_gobernanza.py` verifica que cada autor de `CITATION.cff` tenga aquí
su sección con el mismo nombre.

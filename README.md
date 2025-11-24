# Implementación de la Interfaz Gráfica.
Proyecto de DUNNE_UNAM

Visualización de señales EEG – NeuroDAC con Dash
Este proyecto permite visualizar señales EEG provenientes de una diadema, previamente recolectadas y guardadas como archivos.csv, con una interfaz web desarrollada con Dash de Plotly. 

 Requisitos de instalación
pip install dash dash-bootstrap-components pandas plotly mne

Estructura del Proyecto
interface_eeg/
    interfaz_grafica.py		# Script principal de visualización
    data.csv 			# Archivo CSV con señal EEG (formato: Timestamp, Raw, …)

Preparación del archivo CSV
El archivo de entrada debe ser .csv con las siguientes columnas mínimas:
Timestamp, Raw (o de cualquier señal)

Y ejemplo de contenido:
1.729289508, 0
1.729289509, 56
1.729289510, 51
1.729289511, 48
…

Si generas el CSV desde el script de adquisición (neurosky_data_collector.py), bastará con seleccionar 'raw' y activar la opción de guardado.

Ejecución del programa
Lanza el servidor Dash desde terminal con:
python interface.py
Luego accede al link que la terminal da desde el navegador; ejemplo:
http://127.0.0.1:8050/
Ejemplo de ejecución:


Funcionalidades 
Esquina superior derecha: Selector de tema oscuro/claro
Módulo izquierdo: visualización de EEG
Ajuste de rango de visualización (RangeSlider)
Modo de visualización (RadioItems)
Vista única (una señal, selección de canal con opción de filtros de frecuencia)
Vista multicanal (varias señales, con opción de seleccionar qué canales usar)
Módulo derecho: paneles informativos o de interacción.
Descripción del sistema
Instrucciones de uso

Detalles técnicos
Temas proporcionados por dash-bootstrap-componentes (Darkly y Flatly) (Plotly, 2023).
Se usa mne.io.RawArray para cargar los datos EEG, asegurando compatibilidad con futuros análisis.
La visualización usa plotly.graph_objs, con diseño responsivo para un único canal o para múltiples canales.
Los filtros de frecuencia se aplican con .filter(fmin, fmax) de MNE.
Todos los menús (Dropdown, Slider, etc.) adaptan su estilo automáticamente al tema activo.

Código base (interface.py)
A continuación, se muestra el código base utilizado para la visualización:
interfaz_grafica.py

Comentarios y retroalimentación:
Emmanuel Isaías Guízar-Bayardo1,2
1 División Universitaria de Neuroingeniería (DUNNE), Sociedad de Alumnos de Sistemas Biomédicos (SOSBI), Facultad de Ingeniería de la Universidad Nacional Autónoma de México (UNAM), Ciudad de México, México.
2 eisaiasgb03@gmail.com

Referencias
Dash Documentation & User Guide | Plotly. (2022). Plotly.com. https://dash.plotly.com/
Dash Core Components | Dash for Python Documentation | Plotly. (2022). Plotly.com. https://dash.plotly.com/dash-core-components
Jas. M., Gramfort, A. & Engemann, D.. (s.f.). Plotly.com. https://plotly.com/python/v3/ipython-notebooks/mne-tutorial/‌
neurosky_mm2_headset/data.csv at main · sr-gus/neurosky_mm2_headset. (2025). GitHub. https://github.com/sr-gus/neurosky_mm2_headset/blob/main/data.csv
bootstrap3/bootstrap-themes at main · pkp/bootstrap3. (s.f.). GitHub. https://github.com/pkp/bootstrap3/tree/main/bootstrap-themes




"""Lectura y preparacion de registros EEG.

Un registro entra al proyecto por una de dos puertas: un archivo EEGLAB
`.set`, que es como se distribuyen los datasets publicos, o un CSV, que es el
formato que la pagina de visualizacion consume. Este modulo convierte entre
ambos y garantiza dos invariantes:

- Las amplitudes estan en microvoltios.
- Cada canal tiene media cero.

La segunda importa mas de lo que parece. Un registro con offset DC se dibuja
como una linea plana pegada al borde del eje, con las oscilaciones reales
aplastadas contra ella; es lo que hacia parecer que la senal estaba muerta.

`load_demo` nunca lanza excepcion: devuelve `None` si no hay datos. Eso es lo
que permite que la aplicacion arranque en una maquina recien clonada, donde
`data/` esta vacia por diseno.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

__all__ = [
    "Recording",
    "find_demo_csv",
    "load_demo",
    "read_csv",
    "read_eeglab",
    "remove_dc_offset",
    "write_csv",
]

logger = logging.getLogger(__name__)

#: MNE entrega Volts; EEGLAB almacena microvoltios y MNE aplica la conversion
#: al leer, de modo que este factor devuelve exactamente el array original.
MICROVOLTS_PER_VOLT = 1e6

#: Nombres con los que distintas versiones del proyecto guardaron el tiempo.
TIMESTAMP_COLUMNS = ("Timestamp", "git Timestamp", "timestamp", "time")

DEFAULT_DEMO_NAME = "demo_eeg.csv"
DEFAULT_SAMPLE_RATE = 512.0


@dataclass(frozen=True)
class Recording:
    """Un registro EEG en memoria.

    Attributes
    ----------
    channels : tuple of str
        Nombres de canal, en el orden de las filas de `data`.
    data : numpy.ndarray
        Matriz de forma ``(n_canales, n_muestras)`` en microvoltios.
    sample_rate : float
        Frecuencia de muestreo en hertz.
    source : str
        Ruta o descripcion de donde salio, para poder rastrearlo.
    """

    channels: tuple[str, ...]
    data: np.ndarray
    sample_rate: float
    source: str = ""

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError(f"data debe ser 2D, no {self.data.ndim}D")
        if len(self.channels) != self.data.shape[0]:
            raise ValueError(
                f"{len(self.channels)} canales contra {self.data.shape[0]} filas"
            )
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate invalida: {self.sample_rate}")

    @property
    def n_channels(self) -> int:
        return self.data.shape[0]

    @property
    def n_samples(self) -> int:
        return self.data.shape[1]

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.sample_rate

    def index_of(self, channel: str) -> int:
        """Posicion de un canal.

        Raises
        ------
        KeyError
            Si el canal no existe en el registro.
        """
        try:
            return self.channels.index(channel)
        except ValueError:
            raise KeyError(f"canal desconocido: {channel!r}") from None

    def window(self, start_s: float, end_s: float) -> tuple[np.ndarray, np.ndarray]:
        """Recorta una ventana temporal.

        Returns
        -------
        tuple of numpy.ndarray
            Los tiempos en segundos y la matriz recortada. La ventana se
            acota a los limites del registro en vez de fallar.
        """
        start = max(0, int(start_s * self.sample_rate))
        end = min(self.n_samples, int(end_s * self.sample_rate))
        if end <= start:
            return np.empty(0), np.empty((self.n_channels, 0))
        times = np.arange(start, end) / self.sample_rate
        return times, self.data[:, start:end]


def remove_dc_offset(data: np.ndarray) -> np.ndarray:
    """Centra cada canal en cero restandole su media.

    Parameters
    ----------
    data : numpy.ndarray
        Matriz ``(n_canales, n_muestras)``.

    Returns
    -------
    numpy.ndarray
        Copia con media cero por fila.
    """
    if data.size == 0:
        return data.astype(float, copy=True)
    centered = data.astype(float, copy=True)
    centered -= centered.mean(axis=1, keepdims=True)
    return centered


def read_eeglab(path: str | Path, *, center: bool = True) -> Recording:
    """Lee un archivo EEGLAB `.set`, continuo o por epocas.

    Las epocas se concatenan en una senal continua; para una demostracion
    interesa el flujo, no la estructura de ensayos.

    Parameters
    ----------
    path : str or pathlib.Path
        Ruta al `.set`. Si hay un `.fdt` asociado debe estar al lado.
    center : bool, optional
        Quitar el offset DC de cada canal.

    Raises
    ------
    FileNotFoundError
        Si el archivo no existe.
    """
    import mne  # Import diferido: mantiene barato importar este modulo.

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no existe: {path}")

    try:
        container = mne.io.read_raw_eeglab(path, preload=True, verbose="ERROR")
        volts = container.get_data()
    except TypeError:
        # MNE rechaza los `.set` con mas de un ensayo; hay que leerlos como
        # epocas y pegarlas en el eje temporal.
        epochs = mne.io.read_epochs_eeglab(path, verbose="ERROR")
        container = epochs
        volts = np.concatenate(list(epochs.get_data()), axis=1)

    data = volts * MICROVOLTS_PER_VOLT
    if center:
        data = remove_dc_offset(data)

    return Recording(
        channels=tuple(container.ch_names),
        data=data,
        sample_rate=float(container.info["sfreq"]),
        source=str(path),
    )


def write_csv(
    recording: Recording,
    path: str | Path,
    *,
    decimals: int = 1,
) -> Path:
    """Escribe el registro como CSV con una columna por canal.

    Parameters
    ----------
    recording : Recording
        Registro a escribir.
    path : str or pathlib.Path
        Destino. Los directorios intermedios se crean.
    decimals : int, optional
        Decimales de amplitud. Medido sobre el registro de 32 canales y
        192 s de ds002778, cuya desviacion tipica ronda 50 uV:

        ===========  =======  ==================
        decimales    tamano   error maximo (uV)
        ===========  =======  ==================
        0            10.6 MB  0.50
        1            16.8 MB  0.05
        2            19.9 MB  0.005
        ===========  =======  ==================

        Un decimal deja el error veinte veces por debajo del piso de ruido
        de cualquier EEG de superficie; mas decimales solo engordan el
        archivo.
    """
    import pandas as pd

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    frame = pd.DataFrame(recording.data.T, columns=list(recording.channels))
    frame.insert(0, "Timestamp", np.arange(recording.n_samples) / recording.sample_rate)
    frame.to_csv(path, index=False, float_format=f"%.{decimals}f")
    return path


def read_csv(
    path: str | Path,
    *,
    sample_rate: float | None = None,
    center: bool = True,
) -> Recording:
    """Lee un CSV de canales.

    La frecuencia se deduce de la columna de tiempo cuando existe; si no,
    se usa `sample_rate` o el valor por omision.
    """
    import pandas as pd

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no existe: {path}")

    frame = pd.read_csv(path)
    frame.columns = [str(c).strip() for c in frame.columns]

    # Un archivo corrupto o truncado no hace fallar a pandas: devuelve un
    # marco de cero filas. Sin esta guarda, la pagina dibujaria una grafica
    # vacia en lugar de decir que faltan los datos.
    if len(frame) == 0:
        raise ValueError(f"{path} no contiene muestras")

    time_column = next((c for c in TIMESTAMP_COLUMNS if c in frame.columns), None)
    if sample_rate is None:
        sample_rate = _infer_sample_rate(frame, time_column)

    channels = [c for c in frame.columns if c != time_column]
    if not channels:
        raise ValueError(f"{path} no tiene columnas de canal")

    data = frame[channels].to_numpy(dtype=float).T
    if center:
        data = remove_dc_offset(data)

    return Recording(
        channels=tuple(channels),
        data=data,
        sample_rate=sample_rate,
        source=str(path),
    )


def _infer_sample_rate(frame, time_column: str | None) -> float:
    """Deduce la frecuencia a partir del paso mediano de la columna de tiempo."""
    if time_column is None or len(frame) < 2:
        return DEFAULT_SAMPLE_RATE

    times = frame[time_column].to_numpy(dtype=float)
    step = float(np.median(np.diff(times)))
    if not np.isfinite(step) or step <= 0:
        return DEFAULT_SAMPLE_RATE
    return 1.0 / step


def find_demo_csv(data_dir: str | Path) -> Path | None:
    """Busca el CSV de demostracion dentro del directorio de datos.

    Se prefiere el nombre canonico; si no aparece, cualquier CSV de
    `processed/`, y en ultima instancia cualquiera del directorio.
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return None

    canonical = data_dir / "processed" / DEFAULT_DEMO_NAME
    if canonical.is_file():
        return canonical

    for candidate in (data_dir / "processed", data_dir):
        if candidate.is_dir():
            found = sorted(candidate.glob("*.csv"))
            if found:
                return found[0]
    return None


def load_demo(data_dir: str | Path) -> Recording | None:
    """Carga el registro de demostracion, o `None` si no se puede.

    Nunca lanza excepcion. Un clon recien hecho tiene `data/` vacia por
    diseno, y la aplicacion debe arrancar igual para explicarle al usuario
    que le falta, en lugar de fallar al importar las paginas.
    """
    path = find_demo_csv(data_dir)
    if path is None:
        logger.warning("Sin registro de demostracion en %s", data_dir)
        return None

    try:
        recording = read_csv(path)
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo leer %s: %s", path, exc)
        return None

    logger.info(
        "Registro cargado: %s (%d canales, %.1f s)",
        path.name,
        recording.n_channels,
        recording.duration_s,
    )
    return recording

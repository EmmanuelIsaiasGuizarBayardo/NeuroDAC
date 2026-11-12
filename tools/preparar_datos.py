"""Regenera el registro de demostracion que usa la pagina de visualizacion.

El CSV no se versiona: se reconstruye desde el registro original, el `.bdf`
que publica OpenNeuro o un `.set` de EEGLAB, que vive en `data/raw/` y tampoco
se versiona. Asi el repositorio no carga megabytes de datos derivados y
cualquiera puede rehacerlos con un comando.

    uv run python tools/preparar_datos.py
    .venv/Scripts/python tools/preparar_datos.py   # sin uv

Si no hay fuente, el script dice exactamente que bajar y donde ponerlo en
lugar de fallar con un rastro de pila.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from neurodac.eeg_io import DEFAULT_DEMO_NAME, READERS, read_recording, write_csv

REPO_ROOT = Path(__file__).resolve().parent.parent

DATASET_ID = "ds002778"
DATASET_NAME = "UC San Diego Resting State EEG Data from Patients with Parkinson's Disease"
DATASET_VERSION = "1.0.2"
DATASET_URL = f"https://openneuro.org/datasets/{DATASET_ID}/versions/{DATASET_VERSION}"
DATASET_LICENSE = "CC0"
# Verificados contra dataset_description.json de la version 1.0.2.
DATASET_AUTHORS = "Rockhill, A. P., Jackson, N., George, J., Aron, A., & Swann, N. C."
DATASET_DOI = f"https://doi.org/10.18112/openneuro.{DATASET_ID}.v{DATASET_VERSION}"
DATASET_GIT = "https://github.com/OpenNeuroDatasets/ds002778.git"

formatos = ", ".join(sorted(READERS))

INSTRUCCIONES = f"""
No se encontro ningun registro en {{directorio}}

El registro de demostracion proviene de un dataset publico:

  {DATASET_NAME}
  OpenNeuro {DATASET_ID}, licencia {DATASET_LICENSE}
  {DATASET_URL}

OpenNeuro publica los datos en formato BioSemi (.bdf). Basta un sujeto.

  Opcion A, desde el navegador:
    1. Abre la liga de arriba.
    2. Entra a sub-hc1 / ses-hc / eeg y descarga
       sub-hc1_ses-hc_task-rest_eeg.bdf
    3. Dejalo en {{directorio}}

  Opcion B, con DataLad:
    datalad install {DATASET_GIT}
    cd ds002778
    datalad get sub-hc1/ses-hc/eeg/sub-hc1_ses-hc_task-rest_eeg.bdf

Despues vuelve a correr:  uv run python tools/preparar_datos.py
                   sin uv:  .venv\\Scripts\\python tools\\preparar_datos.py

Tambien puedes apuntar a un archivo concreto, en cualquiera de los
formatos soportados ({formatos}):

  uv run python tools/preparar_datos.py --source ruta\\al\\registro.bdf
"""


def find_source(raw_dir: Path) -> Path | None:
    """Primer registro en un formato soportado dentro de `data/raw/`.

    Se prefiere `.bdf`, que es como OpenNeuro publica el dataset; `.set` se
    acepta para quien traiga un derivado ya preprocesado en EEGLAB.
    """
    if not raw_dir.is_dir():
        return None
    for suffix in (".bdf", ".set"):
        found = sorted(raw_dir.rglob(f"*{suffix}"))
        if found:
            return found[0]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Registro de origen (.bdf o .set). Por omision se busca en data/raw/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "processed" / DEFAULT_DEMO_NAME,
        help="CSV de salida.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerar aunque el CSV ya exista.",
    )
    args = parser.parse_args(argv)

    if args.output.exists() and not args.force:
        print(f"Ya existe: {args.output}")
        print("Usa --force para regenerarlo.")
        return 0

    raw_dir = REPO_ROOT / "data" / "raw"
    source = args.source or find_source(raw_dir)
    if source is None:
        print(INSTRUCCIONES.format(directorio=raw_dir))
        return 1

    if not source.exists():
        print(f"No existe: {source}")
        return 1

    print(f"Leyendo  {source}")
    recording = read_recording(source)
    print(
        f"  {recording.n_channels} canales, {recording.sample_rate:.0f} Hz, "
        f"{recording.duration_s:.1f} s"
    )

    write_csv(recording, args.output)
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"Escrito  {args.output}  ({size_mb:.1f} MB)")
    print()
    print("Fuente de los datos, para citarla:")
    print(f"  {DATASET_AUTHORS} {DATASET_NAME}")
    print(f"  (Version {DATASET_VERSION}) [Conjunto de datos]. OpenNeuro. {DATASET_DOI}")
    print(f"  Licencia {DATASET_LICENSE}. El README del dataset pide citar tambien sus")
    print("  articulos asociados y escribir a los curadores antes de enviar a una")
    print("  revista arbitrada un manuscrito que use estos datos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

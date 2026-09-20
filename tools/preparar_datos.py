"""Regenera el registro de demostracion que usa la pagina de visualizacion.

El CSV no se versiona: se reconstruye desde el `.set` original, que vive en
`data/raw/` y tampoco se versiona. Asi el repositorio no carga megabytes de
datos derivados y cualquiera puede rehacerlos con un comando.

    uv run python tools/preparar_datos.py

Si no hay fuente, el script dice exactamente que bajar y donde ponerlo en
lugar de fallar con un rastro de pila.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from neurodac.eeg_io import DEFAULT_DEMO_NAME, read_eeglab, write_csv

REPO_ROOT = Path(__file__).resolve().parent.parent

DATASET_ID = "ds002778"
DATASET_NAME = "UC San Diego Resting State EEG Data from Patients with Parkinson's Disease"
DATASET_URL = f"https://openneuro.org/datasets/{DATASET_ID}/versions/1.0.2"
DATASET_LICENSE = "CC0"

INSTRUCCIONES = f"""
No se encontro ningun archivo .set en {{directorio}}

El registro de demostracion proviene de un dataset publico:

  {DATASET_NAME}
  OpenNeuro {DATASET_ID}, licencia {DATASET_LICENSE}
  {DATASET_URL}

Pasos:

  1. Descarga el sujeto sub-hc1 desde la liga de arriba.
  2. Deja el .set (y su .fdt si viene aparte) en {{directorio}}
  3. Vuelve a correr:  uv run python tools/preparar_datos.py

Tambien puedes apuntar a un archivo concreto:

  uv run python tools/preparar_datos.py --source ruta\\al\\registro.set
"""


def find_source(raw_dir: Path) -> Path | None:
    """Primer `.set` dentro del directorio de datos crudos."""
    if not raw_dir.is_dir():
        return None
    candidates = sorted(raw_dir.rglob("*.set"))
    return candidates[0] if candidates else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Archivo .set de origen. Por omision se busca en data/raw/",
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
    recording = read_eeglab(source)
    print(
        f"  {recording.n_channels} canales, {recording.sample_rate:.0f} Hz, "
        f"{recording.duration_s:.1f} s"
    )

    write_csv(recording, args.output)
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"Escrito  {args.output}  ({size_mb:.1f} MB)")
    print()
    print("Fuente de los datos, para citarla:")
    print(f"  {DATASET_NAME}")
    print(f"  OpenNeuro {DATASET_ID}, licencia {DATASET_LICENSE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

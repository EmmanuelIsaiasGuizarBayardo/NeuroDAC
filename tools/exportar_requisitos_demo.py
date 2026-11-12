"""Exporta requirements-demo.txt: lo necesario para correr NeuroDAC con pip.

Es la lista para una computadora prestada sin uv: solo las dependencias de
ejecucion, sin pytest, ruff ni pre-commit, con las mismas versiones exactas que
fija uv.lock. `--frozen` lee el lock tal cual, sin volver a resolver, asi que
la demostracion corre con las versiones con las que pasan las pruebas.

No incluye el propio NeuroDAC: tools/instalar_sin_uv.ps1 lo instala aparte en
modo editable, que es obligatorio porque content.py ubica content/ relativo al
codigo fuente. Una instalacion normal lo copiaria a site-packages y la
aplicacion no encontraria su contenido al arrancar.

Uso, en la maquina de desarrollo:
    uv run python tools/exportar_requisitos_demo.py           # escribe
    uv run python tools/exportar_requisitos_demo.py --check   # falla si esta desfasado
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "requirements-demo.txt"

CABECERA = """\
# Dependencias para correr NeuroDAC con pip, sin uv: solo ejecucion.
# Generado desde uv.lock por tools/exportar_requisitos_demo.py. No editar a mano.
#
# Para instalar en una computadora sin uv, usa tools/instalar_sin_uv.ps1: ademas
# de esta lista instala NeuroDAC en modo editable, que es obligatorio.
"""


def generate() -> str:
    """Construye el contenido desde uv.lock.

    Raises
    ------
    RuntimeError
        Si uv no esta disponible o el export falla.
    """
    if shutil.which("uv") is None:
        raise RuntimeError(
            "se necesita uv para generar la lista; corre esto en la maquina de desarrollo"
        )
    cmd = [
        "uv",
        "export",
        "--format",
        "requirements.txt",
        "--frozen",
        "--no-dev",
        "--no-hashes",
        "--no-emit-project",
        "--no-header",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"uv export fallo: {proc.stderr.strip()}")
    return CABECERA + "\n" + proc.stdout.strip() + "\n"


def main() -> int:
    generated = generate()
    if "--check" in sys.argv[1:]:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != generated:
            print(f"{OUTPUT.name} esta desfasado de uv.lock.")
            print("Corre: uv run python tools/exportar_requisitos_demo.py")
            return 1
        print(f"{OUTPUT.name} esta al dia.")
        return 0
    OUTPUT.write_bytes(generated.encode("utf-8"))
    print(f"Escrito {OUTPUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

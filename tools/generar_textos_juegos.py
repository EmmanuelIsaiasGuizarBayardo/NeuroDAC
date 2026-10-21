"""Genera assets/games/textos.js desde content/divulgacion.es.json.

Los juegos dibujan texto en su lienzo y corren en el navegador, donde no
pueden leer content/. Este script extrae de cada juego su seccion `pantalla`
y la escribe como un modulo que el juego carga junto con el motor.

`textos.js` se versiona porque Dash lo sirve tal cual; no se edita a mano: se
cambia el contenido y se vuelve a correr el script.

Uso:
    uv run python tools/generar_textos_juegos.py           # escribe
    uv run python tools/generar_textos_juegos.py --check   # falla si esta desfasado
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT = REPO_ROOT / "content" / "divulgacion.es.json"
OUTPUT = REPO_ROOT / "assets" / "games" / "textos.js"

PLANTILLA = """/* Generado por tools/generar_textos_juegos.py desde content/divulgacion.es.json.
   No se edita a mano: se cambia el contenido y se vuelve a correr el script.
   Los textos son contenido bajo CC BY 4.0 (content/LICENSE.md). */

(function (root) {{
  'use strict';

  const TEXTOS = {textos};

  if (typeof module !== 'undefined' && module.exports) module.exports = TEXTOS;
  else root.NDTextos = TEXTOS;
}})(typeof globalThis !== 'undefined' ? globalThis : this);
"""


def generate() -> str:
    """Construye el contenido de textos.js."""
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    textos = {
        juego: entrada["pantalla"]
        for juego, entrada in data["juegos"].items()
        if "pantalla" in entrada
    }
    cuerpo = json.dumps(textos, ensure_ascii=False, indent=2)
    # Sangria del objeto al nivel de la constante.
    cuerpo = cuerpo.replace("\n", "\n  ")
    return PLANTILLA.format(textos=cuerpo)


def main() -> int:
    generated = generate()
    if "--check" in sys.argv[1:]:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != generated:
            print(f"{OUTPUT.relative_to(REPO_ROOT)} está desfasado.")
            print("Corre: uv run python tools/generar_textos_juegos.py")
            return 1
        print(f"{OUTPUT.relative_to(REPO_ROOT)} está al día.")
        return 0
    OUTPUT.write_bytes(generated.encode("utf-8"))
    print(f"Escrito {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

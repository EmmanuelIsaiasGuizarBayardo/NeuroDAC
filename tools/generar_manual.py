"""Genera el manual del operador desde el archivo de contenido.

    uv run python tools/generar_manual.py
    uv run python tools/generar_manual.py --check   # solo verifica

`docs/manual-operador.md` es un archivo generado: no se edita a mano. Las
explicaciones de las bandas, de los estados y de los juegos son las mismas que
muestra la aplicación, leídas de `content/divulgacion.es.json`, de modo que el
manual y la pantalla no pueden decir cosas distintas.

El modo `--check` devuelve 1 si el archivo en disco no coincide con lo que
produciría el generador. Lo usa el CI para detectar ediciones a mano.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from neurodac.acquisition import SIGNAL_TYPES, SignalState
from neurodac.content import content

REPO_ROOT = Path(__file__).resolve().parent.parent

OUTPUT = REPO_ROOT / "docs" / "manual-operador.md"

#: Orden en que se presentan las bandas, de la más lenta a la más rápida.
BAND_ORDER = ("none", "delta", "theta", "alpha", "beta", "gamma")

AVISO = (
    "<!-- Archivo generado por tools/generar_manual.py desde\n"
    "     content/divulgacion.es.json. No editar a mano: los cambios se\n"
    "     pierden en la siguiente regeneración. -->"
)


def plain(text: str) -> str:
    """El marcado de énfasis del contenido coincide con el de Markdown."""
    return text


def build() -> str:
    """Arma el manual completo."""
    data = content()
    manual = data["manual"]
    out: list[str] = [
        AVISO,
        "",
        f"# {manual['titulo']}",
        "",
        f"*{manual['subtitulo']}*",
        "",
    ]

    for paragraph in manual["intro"]:
        out += [plain(paragraph), ""]

    out += ["---", ""]
    out += _numbered(manual["antes"])
    out += _numbered(manual["diadema"])
    out += _numbered(manual["operacion"])

    out += _states(data)
    out += _bands(data)
    out += _games(data)
    out += _signals(data)
    out += _problems(manual["problemas"])
    out += _numbered(manual["cierre"])

    out += [
        "---",
        "",
        "Contenido bajo CC BY 4.0; ver `LICENSE-CONTENIDO.md`. La documentación",
        "para quien desarrolla está en el `README.md` del repositorio.",
        "",
    ]
    return "\n".join(out)


def _numbered(section: dict) -> list[str]:
    """Una sección de pasos numerados, con nota opcional al final."""
    out = [f"## {section['titulo']}", ""]
    for index, step in enumerate(section["pasos"], start=1):
        out.append(f"{index}. {plain(step)}")
    out.append("")
    if section.get("nota"):
        out += [f"> {plain(section['nota'])}", ""]
    return out


def _states(data: dict) -> list[str]:
    """Tabla de estados, en el orden en que suelen aparecer."""
    out = [
        "## Qué significa cada estado",
        "",
        "El indicador de calidad es lo primero que hay que mirar. Cada estado",
        "trae qué hacer, no solo qué pasa.",
        "",
        "| Estado | Qué hacer |",
        "|---|---|",
    ]
    for signal_state in SignalState:
        entry = data["estados"][str(signal_state)]
        out.append(f"| **{entry['etiqueta']}** | {plain(entry['pista'])} |")
    out.append("")
    return out


def _bands(data: dict) -> list[str]:
    """Explicaciones de las bandas, para decirlas en voz alta."""
    out = [
        "## Qué explicar de cada banda",
        "",
        "Son los textos que la aplicación muestra en el panel lateral. Sirven",
        "de guion cuando el visitante pregunta qué está viendo.",
        "",
    ]
    for key in BAND_ORDER:
        entry = data["bandas"][key]
        out += [f"### {entry['titulo']}", "", plain(entry["texto"]), ""]
    return out


def _games(data: dict) -> list[str]:
    out = ["## Los dos juegos", ""]
    for key, name in (("jardin", "Jardín Mental"), ("carrera", "Carrera Neural")):
        entry = data["juegos"][key]
        out += [f"### {name}", ""]
        for paragraph in entry["parrafos"]:
            out += [plain(paragraph), ""]
    return out


def _signals(data: dict) -> list[str]:
    out = [
        "## Tipos de señal",
        "",
        "Lo que ofrece el selector. Para demostrar, `raw` es la más vistosa;",
        "`attention` y `meditation` son las que controlan los juegos.",
        "",
        "| Señal | Qué es |",
        "|---|---|",
    ]
    for key in SIGNAL_TYPES:
        out.append(f"| `{key}` | {plain(data['senales'][key])} |")
    out.append("")
    return out


def _problems(section: dict) -> list[str]:
    out = [f"## {section['titulo']}", "", "| Síntoma | Qué hacer |", "|---|---|"]
    for case in section["casos"]:
        out.append(f"| {plain(case['sintoma'])} | {plain(case['accion'])} |")
    out.append("")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="No escribe; devuelve 1 si el archivo en disco está desactualizado.",
    )
    args = parser.parse_args(argv)

    generated = build()

    if args.check:
        if not OUTPUT.exists():
            print(f"Falta {OUTPUT.relative_to(REPO_ROOT)}")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != generated:
            print(
                f"{OUTPUT.relative_to(REPO_ROOT)} no coincide con el contenido.\n"
                "Corre: uv run python tools/generar_manual.py"
            )
            return 1
        print(f"{OUTPUT.relative_to(REPO_ROOT)} está al día.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"Escrito {OUTPUT.relative_to(REPO_ROOT)}  ({len(generated.splitlines())} líneas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

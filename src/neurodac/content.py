"""Acceso al contenido divulgativo.

`content/divulgacion.es.json` es la unica fuente del texto que ve el publico.
La interfaz no contiene texto de contenido y el manual del operador se genera
desde ese mismo archivo, de modo que no pueden divergir.

El formato es JSON plano a proposito: quien redacta no necesita tocar Python
ni conocer los componentes de Dash. El unico marcado es el asterisco para
enfasis, que `render` convierte en `html.Em`.

La validacion ocurre al importar. Si falta una entrada que la interfaz
necesita, el fallo es inmediato y con nombre, en lugar de un hueco en la
pantalla durante una demostracion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

__all__ = [
    "CONTENT_PATH",
    "Entry",
    "band",
    "content",
    "game",
    "render",
    "signal",
    "state",
    "view",
]

#: El archivo vive fuera del paquete porque es contenido, no codigo: se
#: versiona aparte y lleva otra licencia.
CONTENT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "content" / "divulgacion.es.json"
)

_EMPHASIS = re.compile(r"\*([^*]+)\*")

#: Secciones que la interfaz da por hechas.
REQUIRED_SECTIONS = ("bandas", "vistas", "senales", "estados", "juegos")


@dataclass(frozen=True)
class Entry:
    """Un bloque con titulo y cuerpo."""

    title: str
    body: str


class ContentError(RuntimeError):
    """El archivo de contenido falta, esta malformado o incompleto."""


@lru_cache(maxsize=1)
def content() -> dict:
    """Carga y valida el archivo de contenido. Se cachea por proceso.

    Raises
    ------
    ContentError
        Si el archivo no existe, no es JSON valido, o le falta una seccion.
    """
    try:
        raw = CONTENT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContentError(f"no se pudo leer {CONTENT_PATH}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContentError(f"{CONTENT_PATH} no es JSON valido: {exc}") from exc

    missing = [s for s in REQUIRED_SECTIONS if s not in data]
    if missing:
        raise ContentError(f"faltan secciones en {CONTENT_PATH.name}: {missing}")

    return data


def render(text: str) -> list:
    """Convierte el marcado de enfasis en componentes de Dash.

    Parameters
    ----------
    text : str
        Texto con cero o mas tramos entre asteriscos.

    Returns
    -------
    list
        Cadenas y `html.Em` intercalados, listo para pasar como `children`.

    Examples
    --------
    >>> [type(x).__name__ for x in render("es *neurofeedback* puro")]
    ['str', 'Em', 'str']
    """
    from dash import html

    pieces: list = []
    cursor = 0
    for match in _EMPHASIS.finditer(text):
        if match.start() > cursor:
            pieces.append(text[cursor : match.start()])
        pieces.append(html.Em(match.group(1)))
        cursor = match.end()
    if cursor < len(text):
        pieces.append(text[cursor:])
    return pieces or [text]


def _entry(section: str, key: str) -> Entry:
    data = content()[section]
    if key not in data:
        raise ContentError(f"no hay entrada {key!r} en la seccion {section!r}")
    item = data[key]
    return Entry(item["titulo"], item["texto"])


def band(key: str) -> Entry:
    """Explicacion de una banda de frecuencia, o de la senal sin filtrar."""
    return _entry("bandas", key)


def view(key: str) -> Entry:
    """Explicacion de un modo de vista."""
    return _entry("vistas", key)


def signal(key: str) -> str:
    """Descripcion de un tipo de senal de la diadema."""
    data = content()["senales"]
    if key not in data:
        raise ContentError(f"no hay descripcion para la senal {key!r}")
    return data[key]


def state(key: str) -> tuple[str, str]:
    """Etiqueta e instruccion accionable de un estado de la senal.

    La instruccion es lo que convierte un diagnostico en algo que el operador
    puede hacer; sin ella el indicador solo informa que algo anda mal.
    """
    data = content()["estados"]
    if key not in data:
        raise ContentError(f"no hay texto para el estado {key!r}")
    return data[key]["etiqueta"], data[key]["pista"]


def game(key: str) -> tuple[str, list[str]]:
    """Titulo y parrafos del panel explicativo de un juego."""
    data = content()["juegos"]
    if key not in data:
        raise ContentError(f"no hay explicacion para el juego {key!r}")
    return data[key]["titulo"], list(data[key]["parrafos"])

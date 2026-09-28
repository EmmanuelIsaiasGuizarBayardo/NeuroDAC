"""Pruebas del contenido didáctico: esquema, nombres, revisión, claves y marcado.

Archivo del estandar DUNNE: se actualiza con 'copier update'. El esquema es del
proyecto y puede cambiar; las reglas que no se negocian se verifican aquí.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

CONTENIDO = Path(__file__).resolve().parent.parent / "content"
ESQUEMA = CONTENIDO / "esquema.json"
ARCHIVOS = sorted(p for p in CONTENIDO.glob("*.json") if p != ESQUEMA)
PATRON_NOMBRE = re.compile(r"^[a-z0-9_]+\.[a-z]{2}(-[A-Z]{2})?\.json$")
ETIQUETA_HTML = re.compile(r"<\s*[A-Za-z/!]")
ESTADOS = {"sin_revision", "en_revision", "revisado"}


def _leer(ruta: Path) -> object:
    """Lee un archivo JSON en UTF-8."""
    return json.loads(ruta.read_text(encoding="utf-8"))


def _recorrer(nodo: object, ruta: str = "") -> Iterator[tuple[str, str, str]]:
    """Entrega (tipo, ruta, valor) de cada clave y de cada cadena del JSON."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            yield "clave", ruta, clave
            yield from _recorrer(valor, f"{ruta}.{clave}" if ruta else clave)
    elif isinstance(nodo, list):
        for i, valor in enumerate(nodo):
            yield from _recorrer(valor, f"{ruta}[{i}]")
    elif isinstance(nodo, str):
        yield "cadena", ruta, nodo


def test_existe_el_esquema() -> None:
    """content/esquema.json existe; sin el, nada se puede validar."""
    assert ESQUEMA.is_file(), "Falta content/esquema.json, que describe la estructura del contenido"


def test_hay_contenido() -> None:
    """content/ tiene al menos un archivo de texto."""
    assert ARCHIVOS, "content/ no tiene archivos <ámbito>.<idioma>.json"


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_nombre_sigue_la_convencion(archivo: Path) -> None:
    """El nombre es <ámbito>.<idioma>.json."""
    assert PATRON_NOMBRE.match(archivo.name), (
        f"{archivo.name} no sigue <ámbito>.<idioma>.json, por ejemplo divulgacion.es.json"
    )


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_declara_estado_de_revision(archivo: Path) -> None:
    """El estado de la revisión académica está declarado, aunque sea sin revisar."""
    datos = _leer(archivo)
    estado = datos.get("review", {}).get("status") if isinstance(datos, dict) else None
    assert estado in ESTADOS, f"{archivo.name} debe declarar review.status: {sorted(ESTADOS)}"


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_valida_contra_el_esquema(archivo: Path) -> None:
    """El contenido cumple content/esquema.json."""
    validador = Draft202012Validator(_leer(ESQUEMA))
    errores = [
        f"{'/'.join(map(str, e.absolute_path)) or '(raíz)'}: {e.message}"
        for e in validador.iter_errors(_leer(archivo))
    ]
    assert not errores, f"{archivo.name} no cumple el esquema:\n  " + "\n  ".join(errores)


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_claves_ascii_y_sin_html(archivo: Path) -> None:
    """Las claves son ASCII y ninguna cadena contiene HTML."""
    problemas = []
    for tipo, ruta, valor in _recorrer(_leer(archivo)):
        if tipo == "clave" and not valor.isascii():
            problemas.append(f"clave con caracteres no ASCII: {valor!r} en {ruta or '(raíz)'}")
        elif tipo == "cadena" and ETIQUETA_HTML.search(valor):
            problemas.append(f"HTML en {ruta}")
    assert not problemas, f"{archivo.name}:\n  " + "\n  ".join(problemas)

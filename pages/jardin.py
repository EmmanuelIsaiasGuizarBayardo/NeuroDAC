"""Jardin Mental: neurofeedback de meditacion.

La pagina solo declara que la distingue; el armado vive en
`neurodac.game_page`, compartido con Carrera Neural.
"""

from __future__ import annotations

import dash
from dash import html

from neurodac.content import game, render
from neurodac.game_page import GameSpec, build


def _explanation(key: str) -> list:
    """Panel divulgativo, leido del archivo de contenido."""
    title, paragraphs = game(key)
    return [html.H6(title)] + [html.P(render(p), style={"fontSize": "0.88rem"}) for p in paragraphs]


SPEC = GameSpec(
    prefix="jardin",
    path="/jardin",
    title="Jardin Mental",
    asset="games/jardin.html",
    signal="meditation",
    # Ninguna: dentro de la aplicacion la senal viene solo de la diadema o de
    # la fuente simulada, declarada en pantalla. Las flechas simulan la senal
    # unicamente con el juego abierto fuera de la aplicacion.
    keys=(),
    explanation=_explanation("jardin"),
    game_width=7,
    canvas_height="66vh",
    # La de assets/games/jardin.js: la pagina encuadra el lienzo en un
    # multiplo entero exacto y el juego lo llena sin franjas.
    logical_size=(240, 180),
)

layout = build(SPEC)

dash.register_page(__name__, path=SPEC.path, name=SPEC.title)

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
    return [html.H6(title)] + [
        html.P(render(p), style={"fontSize": "0.88rem"}) for p in paragraphs
    ]


SPEC = GameSpec(
    prefix="jardin",
    path="/jardin",
    title="Jardin Mental",
    asset="games/jardin.html",
    signal="meditation",
    keys=("ArrowUp", "ArrowDown"),
    explanation=_explanation("jardin"),
    game_width=7,
    canvas_height="66vh",
)

layout = build(SPEC)

dash.register_page(__name__, path=SPEC.path, name=SPEC.title)

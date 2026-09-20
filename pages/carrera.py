"""Carrera Neural: neurofeedback de atencion.

La pagina solo declara que la distingue; el armado vive en
`neurodac.game_page`, compartido con Jardin Mental.
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
    prefix="carrera",
    path="/carrera",
    title="Carrera Neural",
    asset="games/carrera.html",
    signal="attention",
    keys=("ArrowLeft", "ArrowRight", "w", "W", "s", "S"),
    explanation=_explanation("carrera"),
    # El lienzo es angosto y alto: la carretera se lee mejor vertical.
    game_width=5,
    canvas_height="76vh",
)

layout = build(SPEC)

dash.register_page(__name__, path=SPEC.path, name=SPEC.title)

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
    return [html.H6(title)] + [html.P(render(p), style={"fontSize": "0.88rem"}) for p in paragraphs]


SPEC = GameSpec(
    prefix="carrera",
    path="/carrera",
    title="Carrera Neural",
    asset="games/carrera.html",
    signal="attention",
    # Solo los carriles: W y S alterarian la atencion mostrada. Simulan la
    # senal unicamente con el juego abierto fuera de la aplicacion.
    keys=("ArrowLeft", "ArrowRight"),
    explanation=_explanation("carrera"),
    # El lienzo es angosto y alto: la carretera se lee mejor vertical.
    game_width=5,
    canvas_height="76vh",
    # Las de assets/games/carrera.js: el juego llena su recuadro en ambos
    # ejes; con la ventana mas alta se ve mas carretera por delante.
    logical_size=(144, 192),
    logical_width_max=176,
    logical_height_max=288,
)

layout = build(SPEC)

dash.register_page(__name__, path=SPEC.path, name=SPEC.title)

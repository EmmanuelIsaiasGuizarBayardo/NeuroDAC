"""Carrera Neural: neurofeedback de atencion.

La pagina solo declara que la distingue; el armado vive en
`neurodac.game_page`, compartido con Jardin Mental.
"""

from __future__ import annotations

import dash
from dash import html

from neurodac.game_page import GameSpec, build

EXPLANATION = [
    html.H6("Como funciona"),
    html.P(
        [
            "La Carrera Neural es un ejercicio de ",
            html.Em("neurofeedback"),
            (
                " basado en atencion. La senal de atencion de la diadema controla "
                "la velocidad del coche: a mayor concentracion sostenida, mas "
                "rapido avanza. Las flechas cambian de carril para esquivar "
                "obstaculos, y chocar cuesta velocidad durante unos segundos."
            ),
        ],
        style={"fontSize": "0.88rem"},
    ),
    html.P(
        "El coche gris es el rival, que avanza a velocidad constante. Como el "
        "juego no arranca hasta que la senal sirve, nadie empieza la carrera "
        "con medio kilometro de desventaja; volver de una caida reinicia la "
        "carrera en lugar de continuarla perdida.",
        style={"fontSize": "0.88rem"},
    ),
]

SPEC = GameSpec(
    prefix="carrera",
    path="/carrera",
    title="Carrera Neural",
    asset="games/carrera.html",
    signal="attention",
    keys=("ArrowLeft", "ArrowRight", "w", "W", "s", "S"),
    explanation=EXPLANATION,
    # El lienzo es angosto y alto: la carretera se lee mejor vertical.
    game_width=5,
    canvas_height="76vh",
)

layout = build(SPEC)

dash.register_page(__name__, path=SPEC.path, name=SPEC.title)

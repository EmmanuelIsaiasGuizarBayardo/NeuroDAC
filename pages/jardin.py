"""Jardin Mental: neurofeedback de meditacion.

La pagina solo declara que la distingue; el armado vive en
`neurodac.game_page`, compartido con Carrera Neural.
"""

from __future__ import annotations

import dash
from dash import html

from neurodac.game_page import GameSpec, build

EXPLANATION = [
    html.H6("Como funciona"),
    html.P(
        [
            "El Jardin Mental es un ejercicio de ",
            html.Em("neurofeedback"),
            (
                " basado en meditacion. La senal de meditacion de la diadema hace "
                "crecer las flores: por encima de 55 la flor sube de etapa, por "
                "debajo de 45 pierde salud. El objetivo es hacer florecer las "
                "cinco manteniendo la calma, no concentrandose con fuerza."
            ),
        ],
        style={"fontSize": "0.88rem"},
    ),
    html.P(
        "El juego no arranca hasta que la senal sirve. Antes de eso, un cero "
        "de 'todavia no hay datos' entraba como si fuera meditacion nula y la "
        "flor se marchitaba sola en unos diecisiete segundos.",
        style={"fontSize": "0.88rem"},
    ),
]

SPEC = GameSpec(
    prefix="jardin",
    path="/jardin",
    title="Jardin Mental",
    asset="games/jardin.html",
    signal="meditation",
    keys=("ArrowUp", "ArrowDown"),
    explanation=EXPLANATION,
    game_width=7,
    canvas_height="66vh",
)

layout = build(SPEC)

dash.register_page(__name__, path=SPEC.path, name=SPEC.title)

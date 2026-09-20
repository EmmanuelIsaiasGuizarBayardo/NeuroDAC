"""Pagina de visualizacion en tiempo real.

Es la implementacion de referencia del patron: la pagina no abre puertos ni
lanza hilos, solo pide una sesion al registro y lee de ella. Toda la logica de
adquisicion vive en `neurodac.acquisition`.
"""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import Input, Output, State, dcc, html, no_update

from neurodac.acquisition import registry, validate_signal_type
from neurodac.content import signal as signal_text
from neurodac.simulator import SimulatedSource
from neurodac.ui import PanelIds, connection_panel, render_quality

dash.register_page(__name__, path="/tiempo-real", name="Tiempo Real")

IDS = PanelIds("rt")

#: Clave con la que la sesion simulada queda en el registro.
SIM_NAME = "simulada"

#: Rangos fijos donde el protocolo los define; el resto se deja automatico.
Y_RANGES = {"raw": [-2048, 2048], "attention": [0, 100], "meditation": [0, 100]}

WINDOW_POINTS = 512


def _colors(theme: str) -> dict[str, str]:
    if theme == "dark":
        return {
            "bg": "#222",
            "font": "#fff",
            "grid": "rgba(255,255,255,0.08)",
            "zero": "rgba(255,255,255,0.2)",
            "trace": "#4DA8DA",
        }
    return {
        "bg": "#fff",
        "font": "#212529",
        "grid": "rgba(0,0,0,0.06)",
        "zero": "rgba(0,0,0,0.15)",
        "trace": "#375a7f",
    }


def empty_figure(signal_type: str, theme: str, title: str) -> go.Figure:
    """Figura vacia con los ejes ya configurados para esa senal."""
    c = _colors(theme)
    return go.Figure(
        data=[go.Scatter(y=[], mode="lines", line={"color": c["trace"], "width": 1.5})],
        layout=go.Layout(
            title={"text": title, "font": {"size": 12}},
            xaxis={"title": "Muestras", "gridcolor": c["grid"]},
            yaxis={
                "title": "Amplitud",
                "range": Y_RANGES.get(signal_type),
                "gridcolor": c["grid"],
                "zeroline": True,
                "zerolinecolor": c["zero"],
            },
            paper_bgcolor=c["bg"],
            plot_bgcolor=c["bg"],
            font={"family": "Outfit", "color": c["font"], "size": 11},
            margin={"t": 40, "l": 50, "r": 20, "b": 40},
        ),
    )


def _session_name(source_kind: str, port: str | None) -> str:
    return SIM_NAME if source_kind == "sim" else (port or "")


layout = html.Div(
    className="page-content",
    children=[
        html.H2("Tiempo Real", className="section-title"),
        dbc.Row(
            [
                dbc.Col(
                    width=4,
                    children=[
                        connection_panel(IDS, default_signal="raw"),
                        html.Div(id="rt-signal-info", className="edu-panel"),
                        html.Div(
                            className="neuron-decoration", style={"height": "200px"}
                        ),
                    ],
                ),
                dbc.Col(
                    width=8,
                    children=html.Div(
                        className="graph-container",
                        children=dcc.Graph(id="rt-graph", style={"height": "70vh"}),
                    ),
                ),
            ]
        ),
        dcc.Interval(id=IDS.interval, interval=200, disabled=True),
        dcc.Store(id=IDS.store, data=None),
    ],
)


@dash.callback(
    Output(IDS.port, "disabled"),
    Output(IDS.port, "placeholder"),
    Input(IDS.source, "value"),
)
def toggle_port_input(source_kind: str):
    """Con fuente simulada el puerto no aplica."""
    if source_kind == "sim":
        return True, "No aplica con fuente simulada"
    return False, "COM3"


@dash.callback(
    Output("rt-signal-info", "children"),
    Input(IDS.signal, "value"),
)
def update_signal_info(signal_type: str):
    return [
        html.H6(signal_type.capitalize()),
        html.P(signal_text(signal_type), style={"fontSize": "0.88rem"}),
    ]


@dash.callback(
    Output(IDS.status, "children"),
    Output(IDS.interval, "disabled"),
    Output("rt-graph", "figure"),
    Output(IDS.store, "data"),
    Input(IDS.connect, "n_clicks"),
    Input(IDS.stop, "n_clicks"),
    State(IDS.source, "value"),
    State(IDS.port, "value"),
    State(IDS.signal, "value"),
    State("theme-store", "data"),
    prevent_initial_call=True,
)
def manage_connection(_connect, _stop, source_kind, port, signal_type, theme):
    """Conecta o detiene. No abre nada por su cuenta: delega en el registro."""
    triggered = dash.ctx.triggered_id
    name = _session_name(source_kind, port)

    if triggered == IDS.stop:
        registry.stop(name)
        return (
            _alert("Detenido.", "secondary"),
            True,
            empty_figure(signal_type, theme, "Detenido"),
            None,
        )

    if source_kind == "real" and not port:
        return (
            _alert("Indica el puerto serial.", "warning"),
            True,
            empty_figure(signal_type, theme, "Puerto requerido"),
            None,
        )

    try:
        validate_signal_type(signal_type)
    except ValueError as exc:
        return _alert(str(exc), "danger"), True, no_update, None

    source = SimulatedSource(SIM_NAME) if source_kind == "sim" else _serial_source(port)

    try:
        registry.acquire(source, signal_type)
    except Exception as exc:  # noqa: BLE001
        # El mensaje del sistema operativo es el dato util aqui: distingue
        # "puerto ocupado" de "puerto inexistente".
        return (
            _alert(f"No se pudo conectar: {exc}", "danger"),
            True,
            empty_figure(signal_type, theme, "Error de conexion"),
            None,
        )

    return (
        _alert(f"Sesion activa en {name}.", "success"),
        False,
        empty_figure(signal_type, theme, signal_type.capitalize()),
        name,
    )


@dash.callback(
    Output("rt-graph", "extendData"),
    Output(IDS.quality, "children"),
    Input(IDS.interval, "n_intervals"),
    State(IDS.store, "data"),
    prevent_initial_call=True,
)
def refresh(_n, name):
    """Vacia la cola hacia la grafica y refresca el bloque de calidad."""
    session = registry.get(name) if name else None
    if session is None:
        return no_update, no_update

    quality = session.quality
    samples = session.drain()
    extend = no_update if not samples else ({"y": [samples]}, [0], WINDOW_POINTS)
    return extend, render_quality(quality)


def _serial_source(port: str):
    """Import diferido: pyserial solo hace falta con diadema real."""
    from neurodac.acquisition import SerialSource

    return SerialSource(port)


def _alert(message: str, color: str):
    return dbc.Alert(message, color=color, className="py-2 mb-0")

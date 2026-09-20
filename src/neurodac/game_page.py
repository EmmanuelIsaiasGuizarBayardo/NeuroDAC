"""Armado de las paginas de juego.

Jardin y Carrera son la misma pagina con distinto lienzo: panel de conexion a
la derecha, juego a la izquierda, y una compuerta que impide que el juego
corra mientras la senal no sirva. Ese patron vive aqui una sola vez, sobre
todo por la compuerta, que es la parte de la que depende que la demostracion
no arranque con la flor marchitandose sola.

Una pagina se reduce entonces a declarar su `GameSpec` y llamar a `build`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, no_update

from .acquisition import registry, validate_signal_type
from .simulator import SimulatedSource
from .ui import PanelIds, connection_panel, gate_children, render_quality

__all__ = ["GameSpec", "build"]

#: Clave de la sesion simulada. Es la misma en todas las paginas a proposito:
#: el registro comparte una sesion por fuente, asi que cambiar de pagina
#: reutiliza la que ya existe en lugar de abrir otra.
SIMULATED_NAME = "simulada"

REFRESH_MS = 200
GRAPH_POINTS = 512


@dataclass(frozen=True)
class GameSpec:
    """Lo que distingue a una pagina de juego de la otra.

    Attributes
    ----------
    prefix : str
        Raiz de los identificadores de Dash; debe ser unica por pagina.
    path : str
        Ruta de la pagina.
    title : str
        Titulo visible.
    asset : str
        Ruta del HTML dentro de `assets/`.
    signal : str
        Senal que el juego consume.
    keys : tuple of str
        Teclas que la pagina reenvia al iframe. El iframe solo recibe
        eventos de teclado cuando tiene el foco, asi que la pagina los
        reenvia por `postMessage` y el visitante no tiene que hacer clic
        dentro del lienzo primero.
    explanation : list
        Contenido del panel divulgativo.
    game_width : int
        Columnas de Bootstrap para el lienzo.
    canvas_height : str
        Altura CSS del lienzo.
    """

    prefix: str
    path: str
    title: str
    asset: str
    signal: str
    keys: tuple[str, ...]
    explanation: list = field(default_factory=list)
    game_width: int = 7
    canvas_height: str = "66vh"


def build(spec: GameSpec) -> callable:
    """Registra la pagina y sus callbacks; devuelve la funcion de layout."""
    ids = PanelIds(spec.prefix)
    frame_id = f"{spec.prefix}-frame"
    gate_id = f"{spec.prefix}-gate"
    graph_id = f"{spec.prefix}-graph"
    bridge_id = f"{spec.prefix}-bridge"

    def layout() -> html.Div:
        return html.Div(
            className="page-content",
            children=[
                html.H2(spec.title, className="section-title"),
                dbc.Row(
                    [
                        dbc.Col(
                            _canvas_column(spec, frame_id, gate_id),
                            width=spec.game_width,
                        ),
                        dbc.Col(
                            _side_column(spec, ids, graph_id),
                            width=12 - spec.game_width,
                        ),
                    ]
                ),
                dcc.Interval(id=ids.interval, interval=REFRESH_MS, disabled=True),
                dcc.Store(id=ids.store),
                dcc.Store(id=bridge_id, data={"signalValue": 50, "ready": False}),
            ],
        )

    @dash.callback(
        Output(ids.port, "disabled"),
        Output(ids.port, "placeholder"),
        Input(ids.source, "value"),
    )
    def toggle_port_input(source_kind: str):
        """Con fuente simulada el puerto no aplica."""
        if source_kind == "sim":
            return True, "No aplica con fuente simulada"
        return False, "COM3"

    @dash.callback(
        Output(ids.status, "children"),
        Output(ids.interval, "disabled"),
        Output(ids.store, "data"),
        Input(ids.connect, "n_clicks"),
        Input(ids.stop, "n_clicks"),
        State(ids.source, "value"),
        State(ids.port, "value"),
        prevent_initial_call=True,
    )
    def manage_connection(_connect, _stop, source_kind, port):
        """Conecta o detiene. La pagina no abre nada: delega en el registro."""
        name = SIMULATED_NAME if source_kind == "sim" else (port or "")

        if dash.ctx.triggered_id == ids.stop:
            registry.stop(name)
            return _alert("Detenido.", "secondary"), True, None

        if source_kind == "real" and not port:
            return _alert("Indica el puerto serial.", "warning"), True, None

        try:
            validate_signal_type(spec.signal)
        except ValueError as exc:
            return _alert(str(exc), "danger"), True, None

        source = (
            SimulatedSource(SIMULATED_NAME)
            if source_kind == "sim"
            else _serial_source(port)
        )

        try:
            registry.acquire(source, spec.signal)
        except Exception as exc:  # noqa: BLE001
            # El mensaje del sistema operativo distingue "puerto ocupado"
            # de "puerto inexistente", y eso es lo util en vivo.
            return _alert(f"No se pudo conectar: {exc}", "danger"), True, None

        return _alert(f"Sesion activa en {name}.", "success"), False, name

    @dash.callback(
        Output(graph_id, "extendData"),
        Output(ids.quality, "children"),
        Output(gate_id, "children"),
        Output(gate_id, "className"),
        Output(bridge_id, "data"),
        Input(ids.interval, "n_intervals"),
        State(ids.store, "data"),
        prevent_initial_call=True,
    )
    def refresh(_n, name):
        """Vacia la cola, refresca calidad y decide si la compuerta se abre."""
        session = registry.get(name) if name else None
        if session is None:
            return no_update, no_update, no_update, no_update, no_update

        quality = session.quality
        samples = session.drain()
        extend = no_update if not samples else ({"y": [samples]}, [0], GRAPH_POINTS)

        gate = gate_children(quality)
        latest = session.latest(spec.signal)

        return (
            extend,
            render_quality(quality),
            gate,
            "nd-gate" if gate else "nd-gate d-none",
            {
                "signalValue": float(latest) if latest is not None else 50.0,
                "ready": gate is None,
            },
        )

    # El puente con el iframe: valor, tema y compuerta en un solo mensaje, mas
    # el reenvio de teclas para que funcionen sin hacer clic dentro del lienzo.
    dash.clientside_callback(
        f"""
        function(bridge, theme) {{
            var frame = document.getElementById('{frame_id}');
            if (!frame || !frame.contentWindow) {{ return ''; }}
            frame.contentWindow.postMessage(
                Object.assign({{theme: theme}}, bridge || {{}}), '*');

            if (!window._ndKeys_{spec.prefix}) {{
                window._ndKeys_{spec.prefix} = true;
                var keys = {list(spec.keys)!r};
                document.addEventListener('keydown', function (event) {{
                    if (keys.indexOf(event.key) === -1) {{ return; }}
                    var target = document.getElementById('{frame_id}');
                    if (target && target.contentWindow) {{
                        target.contentWindow.postMessage(
                            {{keydown: event.key}}, '*');
                    }}
                }});
            }}
            return '';
        }}
        """,
        Output(frame_id, "title"),
        Input(bridge_id, "data"),
        Input("theme-store", "data"),
    )

    # Ojo: `register_page` NO se llama aqui. Dash descubre las paginas
    # escaneando el texto de cada archivo en busca de ese literal, asi que
    # tiene que aparecer en el modulo de la pagina o el archivo se ignora
    # sin aviso. Ver dash/_pages.py, _import_layouts_from_pages.
    return layout


def _canvas_column(spec: GameSpec, frame_id: str, gate_id: str) -> list:
    """Lienzo del juego con la compuerta encima y el panel divulgativo debajo."""
    return [
        html.Div(
            className="game-canvas-container",
            style={"height": spec.canvas_height, "position": "relative"},
            children=[
                html.Iframe(
                    id=frame_id,
                    src=dash.get_asset_url(spec.asset),
                    style={
                        "width": "100%",
                        "height": "100%",
                        "border": "none",
                        "borderRadius": "10px",
                    },
                ),
                # La compuerta nace visible: sin sesion no hay senal, y sin
                # senal el juego no debe correr.
                html.Div(id=gate_id, className="nd-gate"),
            ],
        ),
        html.Div(className="edu-panel mt-2", children=spec.explanation),
    ]


def _side_column(spec: GameSpec, ids: PanelIds, graph_id: str) -> list:
    """Panel de conexion, calidad, grafica de la senal y decoracion."""
    return [
        connection_panel(ids, default_signal=spec.signal, title="Diadema"),
        html.Div(
            className="graph-container mt-3",
            children=[
                dcc.Graph(
                    id=graph_id,
                    figure=_blank_figure(spec.signal),
                    style={"height": "260px"},
                )
            ],
        ),
        html.Div(className="neuron-decoration", style={"height": "150px"}),
    ]


def _blank_figure(signal: str):
    """Figura inicial vacia, con el rango que el protocolo define."""
    import plotly.graph_objs as go

    ranges = {"raw": [-2048, 2048], "attention": [0, 100], "meditation": [0, 100]}
    return go.Figure(
        data=[go.Scatter(y=[], mode="lines", line={"color": "#4DA8DA", "width": 1.5})],
        layout=go.Layout(
            title={"text": signal.capitalize(), "font": {"size": 12}},
            xaxis={"title": "Tiempo (s)", "gridcolor": "rgba(128,128,128,0.15)"},
            yaxis={
                "title": "Amplitud",
                "range": ranges.get(signal),
                "gridcolor": "rgba(128,128,128,0.15)",
            },
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "Outfit", "size": 10},
            margin={"t": 32, "l": 44, "r": 16, "b": 32},
        ),
    )


def _serial_source(port: str):
    """Import diferido: pyserial solo hace falta con diadema real."""
    from .acquisition import SerialSource

    return SerialSource(port)


def _alert(message: str, color: str):
    return dbc.Alert(message, color=color, className="py-2 mb-0")

"""Armado de las paginas de juego.

Jardin y Carrera son la misma pagina con distinto lienzo: juego a la
izquierda; grafica, panel de conexion y calidad a la derecha; y una compuerta
que impide que el juego corra mientras la senal no sirva. Ese patron vive aqui
una sola vez, sobre todo por la compuerta, que es la parte de la que depende
que la demostracion no arranque con la flor marchitandose sola.

Una pagina se reduce entonces a declarar su `GameSpec` y llamar a `build`.
El protocolo con el juego esta en docs/contrato-juegos.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, no_update

from .acquisition import Quality, SignalState, registry, validate_signal_type
from .simulator import SimulatedSource
from .ui import (
    PanelIds,
    connection_panel,
    gate_children,
    gate_for,
    render_quality,
    sim_badge,
    sim_badge_class,
)

__all__ = ["GameSpec", "bridge_payload", "build", "idle_payload"]

#: Clave de la sesion simulada. Es la misma en todas las paginas a proposito:
#: el registro comparte una sesion por fuente, asi que cambiar de pagina
#: reutiliza la que ya existe en lugar de abrir otra.
SIMULATED_NAME = "simulada"

#: Marca de los mensajes de la aplicacion; el juego ignora cualquier otro.
BRIDGE_SOURCE = "neurodac"

#: La grafica y el valor del juego se refrescan rapido; el panel de calidad y
#: la compuerta, que el operador lee y no anima, van mas lento.
GRAPH_MS = 100
QUALITY_MS = 500
GRAPH_POINTS = 512


def bridge_payload(quality: Quality | None, latest: float | None, simulated: bool) -> dict:
    """Mensaje que la pagina manda al juego.

    `ready` exige el estado listo y ademas un valor: la sesion puede quedar
    lista antes de que llegue el primer paquete eSense, y entonces no hay nada
    que consumir. La ausencia viaja como `None`, nunca como un numero que
    podria ser una lectura legitima.
    """
    has_value = latest is not None
    return {
        "source": BRIDGE_SOURCE,
        "signalValue": float(latest) if has_value else None,
        "ready": bool(quality is not None and quality.state is SignalState.READY and has_value),
        "simulated": simulated,
    }


def idle_payload() -> dict:
    """Puente sin sesion: el juego se detiene y no hay valor."""
    return bridge_payload(None, None, simulated=False)


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
        Altura CSS del lienzo; con `logical_size`, es la altura maxima.
    logical_size : tuple of int, optional
        Resolucion logica de un juego de pixel art. Con ella, la pagina ajusta
        el contenedor al mayor multiplo entero que cabe (assets/encuadre.js),
        y el juego llena su iframe sin franjas. Debe coincidir con la del juego.
    logical_width_max : int, optional
        Si se da, `logical_size` es el ancho minimo y el juego llena el ancho
        de su recuadro: dibuja tantas columnas como quepan hasta este maximo.
    logical_height_max : int, optional
        Junto con `logical_width_max`, el juego llena tambien el alto: dibuja
        tantas filas como quepan. Con la ventana mas alta se ve mas juego.
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
    logical_size: tuple[int, int] | None = None
    logical_width_max: int | None = None
    logical_height_max: int | None = None


def build(spec: GameSpec) -> callable:
    """Registra la pagina y sus callbacks; devuelve la funcion de layout."""
    ids = PanelIds(spec.prefix)
    frame_id = f"{spec.prefix}-frame"
    gate_id = f"{spec.prefix}-gate"
    graph_id = f"{spec.prefix}-graph"
    bridge_id = f"{spec.prefix}-bridge"
    quality_interval_id = f"{spec.prefix}-quality-interval"
    sim_id = f"{spec.prefix}-sim"

    def layout() -> html.Div:
        return html.Div(
            className="page-content",
            children=[
                html.H2(spec.title, className="section-title"),
                dbc.Row(
                    [
                        dbc.Col(
                            _canvas_column(spec, frame_id, gate_id, sim_id),
                            width=spec.game_width,
                        ),
                        dbc.Col(
                            _side_column(spec, ids, graph_id),
                            width=12 - spec.game_width,
                        ),
                    ]
                ),
                dcc.Interval(id=ids.interval, interval=GRAPH_MS, disabled=True),
                dcc.Interval(id=quality_interval_id, interval=QUALITY_MS, disabled=True),
                dcc.Store(id=ids.store),
                dcc.Store(id=bridge_id, data=idle_payload()),
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
        Output(quality_interval_id, "disabled"),
        Output(ids.store, "data"),
        Output(bridge_id, "data", allow_duplicate=True),
        Output(gate_id, "children", allow_duplicate=True),
        Output(gate_id, "className", allow_duplicate=True),
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
            return stopped_outputs("Detenido.", "secondary")

        if source_kind == "real" and not port:
            return stopped_outputs("Indica el puerto serial.", "warning")

        try:
            validate_signal_type(spec.signal)
        except ValueError as exc:
            return stopped_outputs(str(exc), "danger")

        source = SimulatedSource(SIMULATED_NAME) if source_kind == "sim" else _serial_source(port)

        try:
            registry.acquire(source, spec.signal)
        except Exception as exc:  # noqa: BLE001
            # El mensaje del sistema operativo distingue "puerto ocupado"
            # de "puerto inexistente", y eso es lo util en vivo.
            return stopped_outputs(f"No se pudo conectar: {exc}", "danger")

        return (
            _alert(f"Sesion activa en {name}.", "success"),
            False,
            False,
            name,
            idle_payload(),
            no_update,
            no_update,
        )

    @dash.callback(Output(sim_id, "className"), Input(ids.store, "data"))
    def show_sim_badge(name):
        """El aviso sale del nombre de la sesion activa: no puede desincronizarse."""
        return sim_badge_class(name == SIMULATED_NAME)

    @dash.callback(
        Output(graph_id, "extendData"),
        Output(bridge_id, "data"),
        Input(ids.interval, "n_intervals"),
        State(ids.store, "data"),
        prevent_initial_call=True,
    )
    def refresh_signal(_n, name):
        """Vacia la cola hacia la grafica y le pasa al juego el ultimo valor."""
        session = registry.get(name) if name else None
        if session is None:
            return no_update, idle_payload()

        samples = session.drain()
        extend = no_update if not samples else ({"y": [samples]}, [0], GRAPH_POINTS)
        payload = bridge_payload(
            session.quality, session.latest(spec.signal), name == SIMULATED_NAME
        )
        return extend, payload

    @dash.callback(
        Output(ids.quality, "children"),
        Output(gate_id, "children"),
        Output(gate_id, "className"),
        Input(quality_interval_id, "n_intervals"),
        State(ids.store, "data"),
        prevent_initial_call=True,
    )
    def refresh_quality(_n, name):
        """Refresca el panel del operador y decide si la compuerta se abre."""
        session = registry.get(name) if name else None
        if session is None:
            return no_update, no_update, no_update

        quality = session.quality
        gate = gate_children(quality)
        return render_quality(quality), gate, "nd-gate" if gate else "nd-gate d-none"

    # El puente con el iframe: valor, tema y compuerta en un solo mensaje, mas
    # el reenvio de teclas para que funcionen sin hacer clic dentro del lienzo.
    # Se reenvia tambien keyup: sin el, el juego cree que la tecla sigue
    # oprimida y deja de registrar las siguientes pulsaciones.
    dash.clientside_callback(
        f"""
        function(bridge, theme) {{
            var frame = document.getElementById('{frame_id}');
            if (!frame || !frame.contentWindow) {{ return ''; }}
            var origin = window.location.origin;
            frame.contentWindow.postMessage(
                Object.assign({{theme: theme}}, bridge || {{}}), origin);

            if (!window._ndKeys_{spec.prefix}) {{
                window._ndKeys_{spec.prefix} = true;
                var keys = {list(spec.keys)!r};
                var forward = function (kind) {{
                    return function (event) {{
                        if (keys.indexOf(event.key) === -1) {{ return; }}
                        var target = document.getElementById('{frame_id}');
                        if (!target || !target.contentWindow) {{ return; }}
                        var message = {{source: '{BRIDGE_SOURCE}'}};
                        message[kind] = event.key;
                        target.contentWindow.postMessage(message, origin);
                    }};
                }};
                document.addEventListener('keydown', forward('keydown'));
                document.addEventListener('keyup', forward('keyup'));
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


def stopped_outputs(message: str, color: str) -> tuple:
    """Salidas de la conexion cuando no hay sesion activa.

    Ademas de apagar los intervalos, le avisa al juego: sin esto conservaba el
    ultimo `ready: true` y seguia corriendo con la senal congelada.
    """
    return (
        _alert(message, color),
        True,
        True,
        None,
        idle_payload(),
        gate_for(SignalState.DISCONNECTED),
        "nd-gate",
    )


def _canvas_column(spec: GameSpec, frame_id: str, gate_id: str, sim_id: str) -> list:
    """Aviso de senal simulada, lienzo con su compuerta y explicacion debajo."""
    return [
        # Toda senal simulada se declara en pantalla mientras esta activa. Va
        # como franja sobre el lienzo y no encima de el, para no tapar el
        # marcador del juego.
        sim_badge(sim_id),
        html.Div(
            className="game-canvas-container",
            style={"height": spec.canvas_height, "position": "relative"},
            # Datos para el encuadre entero; sin ellos el contenedor conserva
            # su altura fija.
            **_frame_data(spec),
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
                html.Div(
                    id=gate_id,
                    className="nd-gate",
                    children=gate_for(SignalState.DISCONNECTED),
                ),
            ],
        ),
        html.Div(className="edu-panel mt-2", children=spec.explanation),
    ]


def _frame_data(spec: GameSpec) -> dict:
    """Atributos data-* que lee assets/encuadre.js."""
    if spec.logical_size is None:
        return {}
    lw, lh = spec.logical_size
    data = {"data-lw": str(lw), "data-lh": str(lh), "data-maxh": spec.canvas_height}
    if spec.logical_width_max is not None:
        data["data-lwmax"] = str(spec.logical_width_max)
    if spec.logical_height_max is not None:
        data["data-lhmax"] = str(spec.logical_height_max)
    return data


def _side_column(spec: GameSpec, ids: PanelIds, graph_id: str) -> list:
    """Grafica de la senal arriba, para que no la tape el panel; luego conexion."""
    return [
        html.Div(
            className="graph-container mb-3",
            children=[
                dcc.Graph(
                    id=graph_id,
                    figure=_blank_figure(spec.signal),
                    style={"height": "240px"},
                )
            ],
        ),
        connection_panel(ids, default_signal=spec.signal, title="Diadema"),
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

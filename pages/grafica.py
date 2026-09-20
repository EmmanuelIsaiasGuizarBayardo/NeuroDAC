"""Visualizacion de registros EEG pregrabados.

Esta pagina no toca la diadema: dibuja un registro que ya esta en disco. Su
particularidad es que el registro no se versiona, asi que en un clon recien
hecho no existe. En vez de fallar al importar, que tumbaria toda la
aplicacion, la pagina arranca y explica que comando lo regenera.

El filtrado se cachea por banda. Medido sobre el registro de 32 canales y
192 s, filtrarlo completo toma 1.5 s; hacerlo dentro del callback, que
dispara cada 250 ms durante la reproduccion, volveria la pagina inusable.
Con cache el costo se paga una vez al elegir la banda.
"""

from __future__ import annotations

import logging
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objs as go
from dash import Input, Output, State, callback_context, dcc, html, no_update

from neurodac.content import band, view
from neurodac.eeg_io import Recording, load_demo

logger = logging.getLogger(__name__)

dash.register_page(
    __name__, path="/", name="Visualizacion EEG", redirect_from=["/grafica"]
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: Registro cargado al importar. `None` si `data/` esta vacia, que es el
#: estado por omision de un clon nuevo.
RECORDING: Recording | None = load_demo(DATA_DIR)

#: Bandas clasicas del EEG, en hertz.
BANDS: dict[str, tuple[float, float]] = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 12.0),
    "beta": (12.0, 30.0),
    "gamma": (30.0, 50.0),
}

#: Un arreglo filtrado por banda, calculado la primera vez que se pide.
#: Cada entrada pesa lo mismo que el registro, unos 24 MB.
_FILTER_CACHE: dict[str, np.ndarray] = {}

WINDOW_DEFAULT_S = 10
PLAYBACK_BASE_MS = 500

IDS = {
    "range": "eeg-range",
    "play": "eeg-play",
    "stop": "eeg-stop",
    "speed": "eeg-speed",
    "status": "eeg-playback-status",
    "view": "eeg-view",
    "signal_box": "eeg-signal-box",
    "signal": "eeg-signal",
    "filter": "eeg-filter",
    "channel_box": "eeg-channel-box",
    "channels": "eeg-channels",
    "all": "eeg-select-all",
    "none": "eeg-select-none",
    "graph": "eeg-graph",
    "edu": "eeg-edu",
    "view_info": "eeg-view-info",
    "tick": "eeg-tick",
    "state": "eeg-playback-state",
}

# --------------------------------------------------------------- divulgacion


# ------------------------------------------------------------------- helpers


def filtered_data(band: str) -> np.ndarray:
    """Registro filtrado en una banda, calculado una sola vez.

    Parameters
    ----------
    band : str
        Nombre de banda, o cualquier otra cosa para obtener la senal cruda.

    Returns
    -------
    numpy.ndarray
        Matriz ``(n_canales, n_muestras)``. Se devuelve el arreglo cacheado
        sin copiar; quien lo reciba no debe modificarlo.
    """
    if RECORDING is None:
        return np.empty((0, 0))
    if band not in BANDS:
        return RECORDING.data

    cached = _FILTER_CACHE.get(band)
    if cached is None:
        import mne

        low, high = BANDS[band]
        logger.info("Filtrando banda %s (una sola vez)", band)
        cached = mne.filter.filter_data(
            RECORDING.data,
            sfreq=RECORDING.sample_rate,
            l_freq=low,
            h_freq=high,
            fir_design="firwin",
            verbose="ERROR",
        )
        _FILTER_CACHE[band] = cached
    return cached


def graph_colors(theme: str) -> dict[str, str]:
    """Paleta de la grafica segun el tema activo."""
    if theme == "dark":
        return {
            "bg": "#222",
            "font": "#fff",
            "grid": "rgba(255,255,255,0.08)",
            "zero": "rgba(255,255,255,0.25)",
        }
    return {
        "bg": "#fff",
        "font": "#212529",
        "grid": "rgba(0,0,0,0.06)",
        "zero": "rgba(0,0,0,0.2)",
    }


def symmetric_range(values: np.ndarray, padding: float = 1.1) -> list[float]:
    """Rango vertical simetrico, para que el cero quede siempre al centro.

    Un eje autoescalado deja el cero en cualquier lado y hace que dos
    segmentos de la misma senal parezcan distintos; centrarlo vuelve
    comparables dos momentos del registro.
    """
    if values.size == 0:
        return [-500.0, 500.0]
    limit = float(np.abs(values).max())
    if limit == 0.0:
        return [-100.0, 100.0]
    return [-limit * padding, limit * padding]


def empty_figure(theme: str, message: str) -> go.Figure:
    """Figura vacia con un mensaje al centro."""
    colors = graph_colors(theme)
    figure = go.Figure()
    figure.update_layout(
        paper_bgcolor=colors["bg"],
        plot_bgcolor=colors["bg"],
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14, "color": colors["font"]},
            }
        ],
        margin={"t": 20, "l": 20, "r": 20, "b": 20},
    )
    return figure


# -------------------------------------------------------------------- layout


def missing_data_panel() -> html.Div:
    """Lo que ve quien clono el repositorio y todavia no genero los datos."""
    return html.Div(
        className="page-content",
        children=[
            html.H2("Visualizacion EEG", className="section-title"),
            dbc.Alert(
                color="warning",
                className="mx-auto",
                style={"maxWidth": "760px"},
                children=[
                    html.H5("Falta el registro de demostracion"),
                    html.P(
                        "Los datos no se versionan: se regeneran desde el "
                        "dataset publico con un comando. El resto de la "
                        "aplicacion funciona sin ellos."
                    ),
                    html.Pre(
                        "uv run python tools/preparar_datos.py",
                        className="bg-dark text-light p-2 rounded",
                    ),
                    html.P(
                        "Ese script dice que descargar y donde ponerlo si "
                        "todavia no tienes el archivo de origen. Al terminar, "
                        "recarga esta pagina.",
                        className="mb-0 small",
                    ),
                ],
            ),
        ],
    )


def controls() -> html.Div:
    """Panel izquierdo: rango, reproduccion, vista, canales."""
    duration = int(RECORDING.duration_s)
    step = max(30, duration // 5)
    channels = list(RECORDING.channels)

    return html.Div(
        [
            html.H2("Visualizacion EEG", className="section-title"),
            dbc.Label(
                "Rango de tiempo (segundos):",
                style={"fontSize": "0.82rem", "fontWeight": "500"},
            ),
            # Saber que archivo se esta viendo evita la confusion de mirar un
            # registro distinto del que se cree.
            html.Div(
                f"Registro: {Path(RECORDING.source).name} · "
                f"{RECORDING.n_channels} canales · {RECORDING.sample_rate:.0f} Hz",
                className="nd-hint mb-1",
            ),
            dcc.RangeSlider(
                id=IDS["range"],
                min=0,
                max=duration,
                step=1,
                value=[0, WINDOW_DEFAULT_S],
                marks={i: f"{i}s" for i in range(0, duration + 1, step)},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            html.Div(
                className="playback-controls mb-2",
                children=[
                    dbc.Button(
                        "Reproducir", id=IDS["play"], className="btn-play", size="sm"
                    ),
                    dbc.Button(
                        "Detener", id=IDS["stop"], className="btn-play-stop", size="sm"
                    ),
                    html.Span("Velocidad:", className="speed-label ms-2"),
                    dcc.Dropdown(
                        id=IDS["speed"],
                        options=[
                            {"label": "0.5x", "value": 0.25},
                            {"label": "1x", "value": 0.5},
                            {"label": "2x", "value": 1.0},
                            {"label": "4x", "value": 2.0},
                        ],
                        value=0.5,
                        clearable=False,
                        style={"width": "92px", "display": "inline-block"},
                    ),
                    html.Span(id=IDS["status"], className="speed-label ms-2"),
                ],
            ),
            dbc.RadioItems(
                id=IDS["view"],
                options=[
                    {"label": "  Vista unica", "value": "unica"},
                    {"label": "  Vista multicanal", "value": "multi"},
                    {"label": "  Vista superpuesta", "value": "superpuesta"},
                ],
                value="unica",
                inline=True,
                className="mb-2",
            ),
            html.Div(
                id=IDS["signal_box"],
                children=dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Canal:", style={"fontSize": "0.8rem"}),
                                dcc.Dropdown(
                                    id=IDS["signal"],
                                    options=[
                                        {"label": c, "value": c} for c in channels
                                    ],
                                    value=channels[0],
                                    clearable=False,
                                ),
                            ],
                            width=8,
                        ),
                        dbc.Col(
                            [
                                dbc.Label("Filtro:", style={"fontSize": "0.8rem"}),
                                dcc.Dropdown(
                                    id=IDS["filter"],
                                    options=[
                                        {"label": "Sin filtro", "value": "none"},
                                        {"label": "Delta (0.5-4 Hz)", "value": "delta"},
                                        {"label": "Theta (4-8 Hz)", "value": "theta"},
                                        {"label": "Alpha (8-12 Hz)", "value": "alpha"},
                                        {"label": "Beta (12-30 Hz)", "value": "beta"},
                                        {"label": "Gamma (30-50 Hz)", "value": "gamma"},
                                    ],
                                    value="none",
                                    clearable=False,
                                ),
                            ],
                            width=4,
                        ),
                    ]
                ),
            ),
            html.Div(
                id=IDS["channel_box"],
                children=[
                    dbc.Label("Canales:", style={"fontSize": "0.8rem"}),
                    dbc.Row(
                        [
                            dbc.Col(
                                dcc.Dropdown(
                                    id=IDS["channels"],
                                    options=[
                                        {"label": c, "value": c} for c in channels
                                    ],
                                    value=channels[: min(8, len(channels))],
                                    multi=True,
                                    searchable=True,
                                    placeholder="Selecciona canales...",
                                ),
                                width=9,
                            ),
                            dbc.Col(
                                dbc.ButtonGroup(
                                    [
                                        dbc.Button(
                                            "Todos",
                                            id=IDS["all"],
                                            size="sm",
                                            className="btn-nd-primary",
                                        ),
                                        dbc.Button(
                                            "Ninguno",
                                            id=IDS["none"],
                                            size="sm",
                                            className="btn-nd-danger",
                                        ),
                                    ]
                                ),
                                width=3,
                                className="d-flex align-items-end justify-content-end",
                            ),
                        ]
                    ),
                ],
            ),
            html.Div(
                className="graph-container mt-2",
                children=[dcc.Graph(id=IDS["graph"], style={"minHeight": "520px"})],
            ),
        ]
    )


def sidebar() -> html.Div:
    """Panel derecho: divulgacion y navegacion."""
    return html.Div(
        [
            html.Div(id=IDS["edu"], className="edu-panel"),
            html.Div(id=IDS["view_info"], className="edu-panel"),
            html.Hr(style={"borderColor": "var(--nd-border)"}),
            dbc.Button(
                "Jardin Mental",
                href="/jardin",
                size="sm",
                className="btn-nd-primary w-100 mb-2",
            ),
            dbc.Button(
                "Carrera Neural",
                href="/carrera",
                size="sm",
                className="btn-nd-primary w-100 mb-2",
            ),
            html.Div(className="neuron-decoration", style={"height": "220px"}),
        ]
    )


def layout() -> html.Div:
    """Layout de la pagina.

    Es una funcion y no una variable para que Dash la evalue en cada visita:
    asi, tras correr el script de preparacion, basta recargar el navegador
    en lugar de reiniciar el servidor.
    """
    if RECORDING is None:
        return missing_data_panel()

    return html.Div(
        className="page-content",
        children=[
            dbc.Row(
                [
                    dbc.Col(controls(), width=9),
                    dbc.Col(sidebar(), width=3),
                ]
            ),
            dcc.Interval(id=IDS["tick"], interval=PLAYBACK_BASE_MS, disabled=True),
            dcc.Store(id=IDS["state"], data={"playing": False}),
        ],
    )


# ------------------------------------------------------------------ callbacks


@dash.callback(
    Output(IDS["signal_box"], "style"),
    Output(IDS["channel_box"], "style"),
    Input(IDS["view"], "value"),
)
def toggle_controls(view: str):
    """Muestra el selector que corresponde al modo de vista."""
    single = {"display": "block"}, {"display": "none"}
    multi = {"display": "none"}, {"display": "block"}
    return single if view == "unica" else multi


@dash.callback(
    Output(IDS["channels"], "value"),
    Input(IDS["all"], "n_clicks"),
    Input(IDS["none"], "n_clicks"),
    prevent_initial_call=True,
)
def select_channels(_all_clicks, _none_clicks):
    if RECORDING is None:
        return no_update
    triggered = callback_context.triggered[0]["prop_id"].split(".")[0]
    return list(RECORDING.channels) if triggered == IDS["all"] else []


@dash.callback(
    Output(IDS["edu"], "children"),
    Input(IDS["filter"], "value"),
    Input(IDS["view"], "value"),
)
def update_edu(band_key: str, view_mode: str):
    """Texto divulgativo, en funcion del filtro y del modo."""
    entry = band("multicanal" if view_mode != "unica" else band_key or "none")
    return [html.H6(entry.title), html.P(entry.body, style={"fontSize": "0.88rem"})]


@dash.callback(Output(IDS["view_info"], "children"), Input(IDS["view"], "value"))
def update_view_info(view_mode: str):
    entry = view(view_mode or "unica")
    return [html.H6(entry.title), html.P(entry.body, style={"fontSize": "0.88rem"})]


@dash.callback(
    Output(IDS["tick"], "disabled"),
    Output(IDS["tick"], "interval"),
    Output(IDS["status"], "children"),
    Output(IDS["state"], "data"),
    Input(IDS["play"], "n_clicks"),
    Input(IDS["stop"], "n_clicks"),
    State(IDS["speed"], "value"),
    prevent_initial_call=True,
)
def control_playback(_play, _stop, speed: float):
    """Enciende o apaga la reproduccion."""
    triggered = callback_context.triggered[0]["prop_id"].split(".")[0]
    if triggered == IDS["play"]:
        interval = int(PLAYBACK_BASE_MS / (speed / 0.5))
        return False, interval, "Reproduciendo", {"playing": True}
    return True, PLAYBACK_BASE_MS, "", {"playing": False}


@dash.callback(
    Output(IDS["range"], "value"),
    Input(IDS["tick"], "n_intervals"),
    State(IDS["state"], "data"),
    State(IDS["speed"], "value"),
    State(IDS["range"], "value"),
    prevent_initial_call=True,
)
def advance_window(_ticks, state: dict, speed: float, window: list[float]):
    """Desplaza la ventana y vuelve al inicio al llegar al final."""
    if RECORDING is None or not state or not state.get("playing"):
        return no_update

    width = window[1] - window[0]
    start = window[0] + speed
    if start + width >= RECORDING.duration_s:
        start = 0.0
    return [start, start + width]


@dash.callback(
    Output(IDS["graph"], "figure"),
    Input(IDS["signal"], "value"),
    Input(IDS["range"], "value"),
    Input(IDS["view"], "value"),
    Input(IDS["filter"], "value"),
    Input(IDS["channels"], "value"),
    Input("theme-store", "data"),
)
def draw(signal, window, view, band, channels, theme):
    """Dibuja la figura correspondiente al modo de vista activo."""
    if RECORDING is None:
        return empty_figure(theme or "dark", "Sin registro cargado")

    colors = graph_colors(theme or "dark")
    start, end = window
    data = filtered_data(band if view == "unica" else "none")

    sample_start = max(0, int(start * RECORDING.sample_rate))
    sample_end = min(RECORDING.n_samples, int(end * RECORDING.sample_rate))
    if sample_end <= sample_start:
        return empty_figure(theme or "dark", "Ventana vacia")
    times = np.arange(sample_start, sample_end) / RECORDING.sample_rate

    if view == "unica":
        return _single(signal, data, times, sample_start, sample_end, colors)

    selected = channels or []
    if not selected:
        return empty_figure(theme or "dark", "Selecciona al menos un canal")
    if view == "multi":
        return _stacked(selected, data, times, sample_start, sample_end, colors)
    return _overlaid(selected, data, times, sample_start, sample_end, colors)


def _single(signal, data, times, start, end, colors) -> go.Figure:
    """Un canal, con el cero centrado."""
    try:
        index = RECORDING.index_of(signal)
    except KeyError:
        return empty_figure("dark", f"Canal desconocido: {signal}")

    values = data[index, start:end]
    return go.Figure(
        data=[go.Scatter(x=times, y=values, mode="lines", line={"width": 1.2})],
        layout=go.Layout(
            title={"text": signal, "font": {"size": 13}},
            xaxis={
                "title": "Tiempo (s)",
                "gridcolor": colors["grid"],
                "zeroline": False,
            },
            yaxis={
                "title": "Amplitud (uV)",
                "gridcolor": colors["grid"],
                "range": symmetric_range(values),
                "zeroline": True,
                "zerolinecolor": colors["zero"],
                "zerolinewidth": 1.5,
            },
            font={"family": "Outfit", "color": colors["font"], "size": 11},
            paper_bgcolor=colors["bg"],
            plot_bgcolor=colors["bg"],
            height=620,
            margin={"t": 36, "l": 62, "r": 20, "b": 48},
        ),
    )


def _stacked(selected, data, times, start, end, colors) -> go.Figure:
    """Montaje vertical, un eje por canal."""
    indices = [RECORDING.index_of(c) for c in selected if c in RECORDING.channels]
    step = 1.0 / len(indices)

    layout = go.Layout(
        showlegend=False,
        paper_bgcolor=colors["bg"],
        plot_bgcolor=colors["bg"],
        autosize=False,
        height=max(620, len(indices) * 52),
        margin={"t": 36, "l": 62, "r": 20, "b": 36},
        xaxis={
            "title": "Tiempo (s)",
            "side": "top",
            "gridcolor": colors["grid"],
            "zeroline": False,
            "color": colors["font"],
        },
    )

    traces, annotations = [], []
    for position, index in enumerate(indices):
        domain = [1 - (position + 1) * step, 1 - position * step]
        axis = "" if position == 0 else str(position + 1)
        layout[f"yaxis{axis}"] = go.layout.YAxis(
            domain=domain,
            showticklabels=False,
            zeroline=True,
            zerolinecolor=colors["zero"],
            zerolinewidth=0.5,
            gridcolor=colors["grid"],
        )
        traces.append(
            go.Scatter(
                x=times,
                y=data[index, start:end],
                yaxis=f"y{axis}",
                mode="lines",
                line={"width": 0.8},
            )
        )
        annotations.append(
            go.layout.Annotation(
                x=-0.055,
                y=sum(domain) / 2,
                xref="paper",
                yref=f"y{axis}",
                text=RECORDING.channels[index],
                showarrow=False,
                font={"size": 9, "color": colors["font"]},
            )
        )

    layout.annotations = annotations
    layout.font = {"family": "Outfit", "color": colors["font"], "size": 11}
    return go.Figure(data=traces, layout=layout)


def _overlaid(selected, data, times, start, end, colors) -> go.Figure:
    """Todos los canales sobre el mismo eje."""
    indices = [RECORDING.index_of(c) for c in selected if c in RECORDING.channels]
    block = data[indices, start:end]

    figure = go.Figure()
    for row, index in enumerate(indices):
        figure.add_trace(
            go.Scatter(
                x=times,
                y=block[row],
                name=RECORDING.channels[index],
                mode="lines",
                line={"width": 1},
            )
        )

    figure.update_layout(
        title={"text": "Senales superpuestas", "font": {"size": 13}},
        xaxis_title="Tiempo (s)",
        yaxis_title="Amplitud (uV)",
        yaxis={
            "range": symmetric_range(block),
            "zeroline": True,
            "zerolinecolor": colors["zero"],
            "zerolinewidth": 1.5,
        },
        paper_bgcolor=colors["bg"],
        plot_bgcolor=colors["bg"],
        font={"family": "Outfit", "color": colors["font"], "size": 11},
        height=620,
        margin={"t": 36, "l": 62, "r": 20, "b": 48},
    )
    return figure

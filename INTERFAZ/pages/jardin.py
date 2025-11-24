# jardin.py (Py3.9 compatible, FIX) – integra el juego Jardín Mental con multiprocessing
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objs as go
import mne
import os
import signal
from multiprocessing import Process
from typing import Optional

import planta  # juego pygame

dash.register_page(__name__, path="/jardin")

HERE = os.path.dirname(__file__)
CANDIDATES = [
    os.path.abspath(os.path.join(HERE, "..", "data", "data.csv")),
    os.path.abspath(os.path.join(HERE, "data", "data.csv")),
    os.path.abspath(os.path.join(HERE, "..", "..", "data", "data.csv")),
]
DATA_CSV = next((p for p in CANDIDATES if os.path.exists(p)), None)
if DATA_CSV is None:
    raise FileNotFoundError("No se encontró data.csv en:\n" + "\n".join(CANDIDATES))

df = pd.read_csv(DATA_CSV)
df.columns = df.columns.str.strip()
df.rename(columns={"git Timestamp": "Timestamp"}, inplace=True)
signal_options = df.columns.drop('Timestamp').tolist()

sample_rate = 512
max_duration = int(len(df) / sample_rate)

data = df[signal_options].to_numpy().T
info = mne.create_info(ch_names=signal_options, sfreq=sample_rate, ch_types=['eeg'] * len(signal_options))
raw = mne.io.RawArray(data, info)

_planta_proc: Optional[Process] = None

def _planta_running() -> bool:
    return _planta_proc is not None and _planta_proc.is_alive()

def _planta_start():
    global _planta_proc
    if _planta_running():
        return
    _planta_proc = Process(target=planta.main, daemon=True)
    _planta_proc.start()

def _planta_stop():
    global _planta_proc
    if _planta_proc is not None and _planta_proc.is_alive():
        try:
            os.kill(_planta_proc.pid, signal.SIGTERM)
        except Exception:
            pass
    _planta_proc = None

jardin_card = dbc.Card(
    [
        dbc.CardHeader("🌱 Jardín Mental (floración por atención)"),
        dbc.CardBody(
            [
                html.P("Pulsa Jugar para abrir la ventana del jardín. Usa ↑/↓ para subir/bajar atención. Completa cada flor y pasa a la siguiente.", className="mb-2"),
                dbc.ButtonGroup([
                    dbc.Button("Jugar", id="btn-planta-start", color="success"),
                    dbc.Button("Detener", id="btn-planta-stop", color="danger", outline=True),
                ], className="mb-2"),
                html.Div(id="planta-status", className="text-secondary"),
            ]
        ),
    ],
    className="mb-3",
)

layout = dbc.Container([
    dbc.Row([dbc.Col(html.H2("Jardín Mental", className="text-center"), width=12)]),
    dbc.Row([dbc.Col(jardin_card, width=12)]),
    dbc.Row([
        dbc.Col([
            dbc.Label("Selecciona rango de tiempo (segundos):"),
            dcc.RangeSlider(
                id='time-range-slider-jardin', min=0, max=max_duration, step=10, value=[0, 10],
                marks={i: f'{i}s' for i in range(0, max_duration + 1, max(30, int(max_duration/5)))}
            ),
            html.Div(children=dbc.Row([
                dbc.Col([
                    dbc.Label("Tipo de señal:"),
                    dcc.Dropdown(
                        id='signal-selector-jardin',
                        options=[{'label': sig, 'value': sig} for sig in signal_options],
                        value=signal_options[0] if signal_options else None,
                        style={'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'}
                    )
                ], width=8),
                dbc.Col([
                    dbc.Label("Filtro de frecuencia:"),
                    dcc.Dropdown(
                        id='filter-selector-jardin',
                        options=[
                            {'label': 'Sin filtro', 'value': 'none'},
                            {'label': 'Delta (0.5-4 Hz)', 'value': 'delta'},
                            {'label': 'Theta (4-8 Hz)', 'value': 'theta'},
                            {'label': 'Alpha (8-12 Hz)', 'value': 'alpha'},
                            {'label': 'Beta (12-30 Hz)', 'value': 'beta'},
                            {'label': 'Gamma (30-50 Hz)', 'value': 'gamma'}
                        ],
                        value='none', clearable=False,
                        style={'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'}
                    )
                ], width=4)
            ])),
            html.Div(dcc.Graph(id='eeg-graph-jardin', style={'height': '100%', 'minHeight': '100px'}), style={'height': 'calc(50vh - 50px)'})
        ], width=12),
    ]),
], fluid=True)

@dash.callback(
    Output('eeg-graph-jardin', 'figure'),
    Input('signal-selector-jardin', 'value'),
    Input('filter-selector-jardin', 'value'),
    Input('time-range-slider-jardin', 'value'),
    Input('theme-store', 'data')
)
def update_graph(signal_type, filter_band, time_range, theme):
    bgcolor = "black" if theme == 'dark' else "white"
    fontcolor = "white" if theme == 'dark' else "black"

    start, end = time_range
    start_idx = int(start * sample_rate)
    end_idx = int(end * sample_rate)

    raw_filtered = raw.copy()
    bands = {'delta': (0.5, 4), 'theta': (4, 8), 'alpha': (8, 12), 'beta': (12, 30), 'gamma': (30, 50)}
    if filter_band in bands:
        raw_filtered.filter(*bands[filter_band], fir_design='firwin', verbose='ERROR')

    ch_idx = raw.ch_names.index(signal_type)
    data, times = raw_filtered[ch_idx, start_idx:end_idx]
    times = times.flatten()
    fig = go.Figure(
        data=[go.Scatter(x=times, y=data[0], mode='lines')],
        layout=go.Layout(
            title=f'Señal EEG: {signal_type}',
            xaxis=dict(title='Tiempo (s)', gridcolor='gray'),
            yaxis=dict(title='Amplitud (µV)', gridcolor='gray'),
            font=dict(family="Times New Roman", color=fontcolor),
            paper_bgcolor=bgcolor, plot_bgcolor=bgcolor,
            margin=dict(t=40, l=20, r=40, b=40)
        )
    )
    return fig

@dash.callback(
    Output("planta-status", "children"),
    Output("btn-planta-start", "disabled"),
    Output("btn-planta-stop", "disabled"),
    Input("btn-planta-start", "n_clicks"),
    Input("btn-planta-stop", "n_clicks"),
    prevent_initial_call=True,
)
def handle_planta_buttons(n_start, n_stop):
    ctx = dash.callback_context
    if not ctx.triggered:
        running = _planta_running()
        return ("Estado: ejecutándose" if running else "Estado: detenido", running, not running)

    which = ctx.triggered[0]["prop_id"].split(".")[0]
    if which == "btn-planta-start":
        _planta_start()
    elif which == "btn-planta-stop":
        _planta_stop()

    running = _planta_running()
    return ("Estado: ejecutándose" if running else "Estado: detenido", running, not running)

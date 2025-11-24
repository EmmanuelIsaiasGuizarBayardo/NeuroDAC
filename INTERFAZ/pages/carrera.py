# carrera.py
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

import coche  

dash.register_page(__name__, path="/carrera")

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
raw1 = mne.io.RawArray(data, info)
raw2 = mne.io.RawArray(data.copy(), info.copy())

_coche_proc: Optional[Process] = None

def _coche_running() -> bool:
    return _coche_proc is not None and _coche_proc.is_alive()

def _coche_start():
    global _coche_proc
    if _coche_running():
        return
    _coche_proc = Process(target=coche.main, daemon=True)
    _coche_proc.start()

def _coche_stop():
    global _coche_proc
    if _coche_proc is not None and _coche_proc.is_alive():
        try:
            os.kill(_coche_proc.pid, signal.SIGTERM)
        except Exception:
            pass
    _coche_proc = None

def build_graph(raw, signal_type, filter_band, time_range, theme):
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
            margin=dict(t=40, l=20, r=40, b=40), height=300
        )
    )
    return fig

juego_card = dbc.Card(
    [
        dbc.CardHeader("🎮 Carrera de Coches (atención)"),
        dbc.CardBody(
            [
                html.P("Pulsa Jugar para abrir la ventana del juego. Usa W/S para subir/bajar atención, ←/→ para cambiar de carril. Cierra la ventana para terminar.", className="mb-2"),
                dbc.ButtonGroup([
                    dbc.Button("Jugar", id="btn-coche-start", color="primary"),
                    dbc.Button("Detener", id="btn-coche-stop", color="danger", outline=True),
                ], className="mb-2"),
                html.Div(id="coche-status", className="text-secondary"),
            ]
        ),
    ],
    className="mb-3",
)

layout = dbc.Container([
    dbc.Row([dbc.Col(html.H2("Carrera de Coches", className="text-center"), width=12)]),
    dbc.Row([dbc.Col(juego_card, width=12)]),
    dbc.Row([
        dbc.Label("Selecciona rango de tiempo (segundos):"),
        dcc.RangeSlider(
            id='time-range-slider-carrera', min=0, max=max_duration, step=10, value=[0, 10],
            marks={i: f'{i}s' for i in range(0, max_duration + 1, max(30, int(max_duration/5)))}
        ),
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Tipo de señal DIADEMA1:"),
                    dcc.Dropdown(
                        id='signal-selector-c1',
                        options=[{'label': sig, 'value': sig} for sig in signal_options],
                        value=signal_options[0] if signal_options else None,
                        style={'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'}
                    )
                ], width=9),
                dbc.Col([
                    dbc.Label("Filtro DIADEMA1:"),
                    dcc.Dropdown(
                        id='filter-selector-c1',
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
                ], width=3)
            ]),
            dcc.Graph(id='eeg-graph-c1', style={'height': '300px'})
        ], width=6),
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Tipo de señal DIADEMA2:"),
                    dcc.Dropdown(
                        id='signal-selector-c2',
                        options=[{'label': sig, 'value': sig} for sig in signal_options],
                        value=signal_options[0] if signal_options else None,
                        style={'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'}
                    )
                ], width=9),
                dbc.Col([
                    dbc.Label("Filtro DIADEMA2:"),
                    dcc.Dropdown(
                        id='filter-selector-c2',
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
                ], width=3)
            ]),
            dcc.Graph(id='eeg-graph-c2', style={'height': '300px'})
        ], width=6)
    ])
], fluid=True)

@dash.callback(
    Output('eeg-graph-c1', 'figure'),
    Input('signal-selector-c1', 'value'),
    Input('filter-selector-c1', 'value'),
    Input('time-range-slider-carrera', 'value'),
    Input('theme-store', 'data')
)
def update_graph_1(signal_type, filter_band, time_range, theme):
    return build_graph(raw1, signal_type, filter_band, time_range, theme)

@dash.callback(
    Output('eeg-graph-c2', 'figure'),
    Input('signal-selector-c2', 'value'),
    Input('filter-selector-c2', 'value'),
    Input('time-range-slider-carrera', 'value'),
    Input('theme-store', 'data')
)
def update_graph_2(signal_type, filter_band, time_range, theme):
    return build_graph(raw2, signal_type, filter_band, time_range, theme)

@dash.callback(
    Output("coche-status", "children"),
    Output("btn-coche-start", "disabled"),
    Output("btn-coche-stop", "disabled"),
    Input("btn-coche-start", "n_clicks"),
    Input("btn-coche-stop", "n_clicks"),
    prevent_initial_call=True,
)
def handle_coche_buttons(n_start, n_stop):
    ctx = dash.callback_context
    if not ctx.triggered:
        running = _coche_running()
        return ("Estado: ejecutándose" if running else "Estado: detenido", running, not running)

    which = ctx.triggered[0]["prop_id"].split(".")[0]
    if which == "btn-coche-start":
        _coche_start()
    elif which == "btn-coche-stop":
        _coche_stop()

    running = _coche_running()
    return ("Estado: ejecutándose" if running else "Estado: detenido", running, not running)

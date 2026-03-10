# pages/tiempo_real.py — Visualización en Tiempo Real v5
# Conexión directa con diadema NeuroSky MindWave vía Bluetooth/Serial

import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import os
import sys
import time
import threading
from collections import deque

# Agregar directorio raíz al path para importar módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from modules.neurosky_data_collector import NeuroSkyDataCollector, validate_signal_type

# =============================================================
# Estado global de conexión
# =============================================================
LIVE_DATA_BUFFER = deque()
global_collector = None
collector_thread = None

dash.register_page(__name__, path="/tiempo-real", name="Tiempo Real")

# Tipos de señal disponibles en NeuroSky
SIGNAL_OPTIONS = [
    'raw', 'attention', 'meditation', 'blink',
    'delta', 'theta', 'low-alpha', 'high-alpha',
    'low-beta', 'high-beta', 'low-gamma', 'mid-gamma',
]

# Descripciones educativas de cada tipo de señal
SIGNAL_INFO = {
    'raw': 'Señal cruda del electrodo; mezcla de todas las frecuencias cerebrales.',
    'attention': 'Índice propietario de NeuroSky (0–100) que estima el nivel de concentración.',
    'meditation': 'Índice propietario (0–100) que refleja estados de relajación y calma mental.',
    'blink': 'Detecta artefactos de parpadeo; útil para interfaces BCI basadas en EOG.',
    'delta': 'Potencia en banda delta (0.5–4 Hz); sueño profundo.',
    'theta': 'Potencia en banda theta (4–8 Hz); meditación y memoria.',
    'low-alpha': 'Alpha baja (8–10 Hz); relajación cortical temprana.',
    'high-alpha': 'Alpha alta (10–12 Hz); relajación cortical profunda.',
    'low-beta': 'Beta baja (12–18 Hz); ritmo sensoriomotor (SMR).',
    'high-beta': 'Beta alta (18–30 Hz); actividad mental intensa.',
    'low-gamma': 'Gamma baja (30–40 Hz); procesamiento cognitivo.',
    'mid-gamma': 'Gamma media (40–50 Hz); binding perceptual.',
}


# =============================================================
# Funciones auxiliares
# =============================================================
def get_colors(theme):
    """Retorna colores de gráfica según el tema."""
    if theme == 'dark':
        return {
            'bg': '#222', 'paper': '#222', 'font': '#fff',
            'grid': 'rgba(255,255,255,0.08)',
            'zero': 'rgba(255,255,255,0.2)',
            'trace': '#4DA8DA',
        }
    return {
        'bg': '#fff', 'paper': '#fff', 'font': '#212529',
        'grid': 'rgba(0,0,0,0.06)',
        'zero': 'rgba(0,0,0,0.15)',
        'trace': '#375a7f',
    }


def create_empty_figure(signal_type, theme, title="Esperando datos..."):
    """Crea una figura vacía con ejes configurados según el tipo de señal."""
    c = get_colors(theme)

    # Rango del eje Y según tipo de señal
    y_range = None
    if signal_type == 'raw':
        y_range = [-2048, 2048]
    elif signal_type in ['attention', 'meditation']:
        y_range = [0, 100]

    return go.Figure(
        data=[go.Scatter(
            y=[], mode='lines',
            line=dict(color=c['trace'], width=1.5)
        )],
        layout=go.Layout(
            title=dict(text=title, font=dict(size=12)),
            xaxis=dict(
                title='Tiempo (s)', gridcolor=c['grid'],
                zeroline=True, zerolinecolor=c['zero']
            ),
            yaxis=dict(
                title='Amplitud', range=y_range,
                gridcolor=c['grid'],
                zeroline=True, zerolinecolor=c['zero']
            ),
            paper_bgcolor=c['paper'], plot_bgcolor=c['bg'],
            font=dict(family="Outfit", color=c['font'], size=11),
            margin=dict(t=40, l=50, r=20, b=40),
        )
    )


def collect_data(collector_instance):
    """Hilo de recolección: lee datos de la diadema y los agrega al buffer."""
    while collector_instance.running:
        try:
            value = collector_instance.get_signal_value(
                collector_instance.signal_type
            )
            LIVE_DATA_BUFFER.append(value)
            time.sleep(1.0 / collector_instance.sample_freq)
        except Exception as e:
            if collector_instance.running:
                print(f"Error en hilo de recolección: {e}")


# =============================================================
# Layout
# =============================================================
layout = html.Div(className='page-content', children=[
    html.H2("Tiempo Real", className="section-title"),

    dbc.Row([
        # --- Columna izquierda: controles + info ---
        dbc.Col(width=4, children=[
            dbc.Card(className="mb-3", children=[
                dbc.CardBody([
                    dbc.Label(
                        "Puerto serial:",
                        style={"fontSize": "0.8rem", "fontWeight": "500"}
                    ),
                    dbc.Input(
                        id="rt-com-port-input",
                        placeholder="COM3 o /dev/ttyUSB0",
                        type="text", className="mb-2"
                    ),
                    dbc.Label(
                        "Tipo de señal:",
                        style={"fontSize": "0.8rem", "fontWeight": "500"}
                    ),
                    dcc.Dropdown(
                        id="rt-signal-type-dropdown",
                        options=[
                            {'label': s.capitalize(), 'value': s}
                            for s in SIGNAL_OPTIONS
                        ],
                        value='raw', clearable=False, className='mb-3'
                    ),
                    dbc.Row([
                        dbc.Col(
                            dbc.Button(
                                "Conectar", id="rt-connect-button",
                                className="btn-nd-primary w-100"
                            ), width=6
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Detener", id="rt-stop-button",
                                className="btn-nd-danger w-100"
                            ), width=6
                        ),
                    ]),
                    html.Div(id="rt-connection-status", className="mt-2"),
                ])
            ]),

            # Panel informativo de la señal seleccionada
            html.Div(
                id='rt-signal-info', className='edu-panel',
                children=[
                    html.H6("Señal cruda (Raw)"),
                    html.P(
                        SIGNAL_INFO['raw'],
                        style={"fontSize": "0.88rem"}
                    ),
                ]
            ),

            # Decoración animada de neuronas
            html.Div(className='neuron-decoration', style={"height": "200px"}),
        ]),

        # --- Columna derecha: gráfica ---
        dbc.Col(width=8, children=[
            html.Div(className="graph-container", children=[
                dcc.Graph(id="rt-live-graph", style={'height': '70vh'})
            ])
        ]),
    ]),

    # Motor de actualización (10 Hz)
    dcc.Interval(
        id='rt-interval-component',
        interval=100, n_intervals=0, disabled=True
    ),
])


# =============================================================
# Callbacks
# =============================================================

# Actualizar información de la señal seleccionada
@dash.callback(
    Output('rt-signal-info', 'children'),
    Input('rt-signal-type-dropdown', 'value')
)
def update_signal_info(signal_type):
    return [
        html.H6(signal_type.capitalize()),
        html.P(
            SIGNAL_INFO.get(signal_type, ''),
            style={"fontSize": "0.88rem"}
        ),
    ]


# Gestionar conexión/desconexión con la diadema
@dash.callback(
    Output('rt-connection-status', 'children'),
    Output('rt-interval-component', 'disabled'),
    Output('rt-live-graph', 'figure'),
    Input('rt-connect-button', 'n_clicks'),
    Input('rt-stop-button', 'n_clicks'),
    State('rt-com-port-input', 'value'),
    State('rt-signal-type-dropdown', 'value'),
    State('theme-store', 'data'),
    prevent_initial_call=True
)
def manage_connection(connect_clicks, stop_clicks, port, signal_type, theme):
    global global_collector, collector_thread
    triggered = dash.ctx.triggered_id

    if triggered == 'rt-connect-button':
        # Validar puerto
        if not port:
            return (
                html.Span("Puerto requerido.", className="status-badge disconnected"),
                True,
                create_empty_figure(signal_type, theme, "Puerto requerido")
            )

        # Validar tipo de señal
        try:
            validate_signal_type(signal_type)
        except ValueError as e:
            return (
                html.Span(str(e), className="status-badge disconnected"),
                True,
                create_empty_figure(signal_type, theme, "Error")
            )

        # Detener conexión anterior si existe
        if global_collector and global_collector.running:
            global_collector.stop()
            if collector_thread and collector_thread.is_alive():
                collector_thread.join()
        LIVE_DATA_BUFFER.clear()

        # Intentar nueva conexión
        try:
            global_collector = NeuroSkyDataCollector(
                port=port, signal_type=signal_type, save_to_csv=False
            )
            global_collector.connect()
            global_collector.running = True

            collector_thread = threading.Thread(
                target=collect_data,
                args=(global_collector,),
                daemon=True
            )
            collector_thread.start()

            return (
                html.Span(
                    [html.Span(className="dot"), f" {port}"],
                    className="status-badge connected"
                ),
                False,  # Habilitar intervalo
                create_empty_figure(signal_type, theme, f"{signal_type.capitalize()}")
            )
        except Exception as e:
            if global_collector:
                global_collector.running = False
            return (
                html.Span(f"Error: {e}", className="status-badge disconnected"),
                True,
                create_empty_figure(signal_type, theme, f"Error: {e}")
            )

    elif triggered == 'rt-stop-button':
        if global_collector and global_collector.running:
            global_collector.stop()
            if collector_thread and collector_thread.is_alive():
                collector_thread.join()
            LIVE_DATA_BUFFER.clear()
            return (
                html.Span("Detenido.", className="status-badge disconnected"),
                True,
                create_empty_figure(signal_type, theme, "Detenido")
            )
        return (
            html.Span("Sin conexión.", className="status-badge disconnected"),
            True, no_update
        )

    return no_update, no_update, no_update


# Actualizar gráfica con nuevos datos del buffer
@dash.callback(
    Output('rt-live-graph', 'extendData'),
    Input('rt-interval-component', 'n_intervals'),
    prevent_initial_call=True
)
def update_graph(n_intervals):
    # Vaciar buffer de puntos nuevos
    new_points = []
    while True:
        try:
            new_points.append(LIVE_DATA_BUFFER.popleft())
        except IndexError:
            break

    if not new_points:
        return no_update

    # Enviar datos a la traza 0; mantener últimos 512 puntos
    return ({'y': [new_points]}, [0], 512)

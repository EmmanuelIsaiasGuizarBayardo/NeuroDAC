#jardin.py
import dash
from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import os
import time
import threading
from collections import deque

# --- IMPORTACIONES PARA JUEGO ---
import signal
from multiprocessing import Process, Value # <--- 1. Importar Value
from typing import Optional
import planta  # Importar el juego Pygame

# --- IMPORTACIÓN DE MÓDULOS ---
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Importar desde la carpeta 'modules'
from modules.neurosky_data_collector import NeuroSkyDataCollector, validate_signal_type

# --- OBJETOS GLOBALES (TIEMPO REAL) ---
LIVE_DATA_BUFFER_JARDIN = deque()
COLLECTOR_JARDIN = None
THREAD_JARDIN = None

# --- OBJETOS GLOBALES (JUEGO PYGAME) ---
_planta_proc: Optional[Process] = None
# --- 2. Crear el valor de memoria compartida (entero, inicializado en 50) ---
_shared_signal_value_jardin = Value('i', 50)

dash.register_page(__name__, path="/jardin")

# --- FUNCIONES AUXILIARES (JUEGO PYGAME) ---
def _planta_running() -> bool:
    return _planta_proc is not None and _planta_proc.is_alive()

def _planta_start():
    global _planta_proc
    if _planta_running():
        return
    # --- 3. Pasar el valor compartido como argumento al proceso ---
    _planta_proc = Process(target=planta.main, args=(_shared_signal_value_jardin,), daemon=True)
    _planta_proc.start()

def _planta_stop():
    global _planta_proc
    _shared_signal_value_jardin.value = 50 # Resetear valor al detener
    if _planta_proc is not None and _planta_proc.is_alive():
        try:
            os.kill(_planta_proc.pid, signal.SIGTERM)
            _planta_proc.join(timeout=1) 
            if _planta_proc.is_alive():
                _planta_proc.terminate() 
        except Exception as e:
            print(f"Error al detener proceso planta: {e}")
            try:
                _planta_proc.terminate() 
            except Exception:
                pass
    _planta_proc = None

# --- COMPONENTES DE LAYOUT ---
signal_options_rt = [
    'raw', 'attention', 'meditation', 'blink', 'delta', 'theta', 
    'low-alpha', 'high-alpha', 'low-beta', 'high-beta', 
    'low-gamma', 'mid-gamma'
]

jardin_card = dbc.Card(
    [
        dbc.CardHeader("🌱 Jardín Mental (Meditación)"),
        dbc.CardBody(
            [
                # --- 4. Texto actualizado ---
                html.P("Pulsa Jugar para abrir la ventana. El juego se controlará con el valor de 'meditation' de la diadema.", className="mb-2"),
                html.P("Umbrales: > 35 (Crece), < 25 (Decrece)", className="text-muted small"),
                dbc.ButtonGroup([
                    dbc.Button("Jugar", id="btn-planta-start", color="success"),
                    dbc.Button("Detener", id="btn-planta-stop", color="danger", outline=True),
                ], className="mb-2 w-100"),
                html.Div(id="planta-status", className="text-secondary text-center mt-2"),
            ]
        ),
    ],
    className="mb-3",
)

# Layout de la página Jardín Mental
layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("Jardín Mental", className="text-center"), width=12)
    ]),
    dbc.Row([
        dbc.Col(jardin_card, width=7),
        dbc.Col([
            dbc.Card([
                    dbc.CardHeader(dbc.Button("¿Qué es esta página?", id={'type': 'button-jardin', 'index': 1}, color="Dark", className="w-100")),
                    dbc.Collapse(dbc.CardBody([
                        html.P(["Jardín Mental.", html.Br(), 
                               "Haz crecer un jardín con tu mente. La meditación sostenida permite que las flores crezcan. "
                               "Observa tu actividad cerebral en la gráfica de la derecha mientras juegas."], className="card-text")
                    ]), id={'type': 'collapse-jardin', 'index': 1}, is_open=True)
                ], className="mb-2"),
                dbc.Card([
                    dbc.CardHeader(dbc.Button("¿Cómo usar la interfaz?", id={'type': 'button-jardin', 'index': 2}, color="Dark", className="w-100")),
                    dbc.Collapse(dbc.CardBody([
                        html.P(["1. Conecta la diadema (Puerto, Señal='meditation').", html.Br(),
                                "2. Presiona 'Jugar' en el panel de la izquierda.", html.Br(),
                                "3. Controla el juego con tu nivel de meditación."], className="card-text")
                    ]), id={'type': 'collapse-jardin', 'index': 2}, is_open=False)
                ]),
            
            html.Hr(),
            dbc.Row([
                dbc.Col(dbc.Label("Puerto (ej. COM3):"), width=12),
                dbc.Col(dbc.Input(id="rt-com-port-jardin", placeholder="COM3", type="text"), width=12),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col(dbc.Label("Tipo de Señal:"), width=12),
                dbc.Col(dcc.Dropdown(
                    id="rt-signal-type-jardin",
                    options=[{'label': s.capitalize(), 'value': s} for s in signal_options_rt],
                    value='meditation', # Default a meditation para este juego
                    clearable=False,
                    style={'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'}
                ), width=12),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col(dbc.Button("Conectar", id="rt-connect-jardin", color="primary", className="me-2"), width="auto"),
                dbc.Col(dbc.Button("Detener", id="rt-stop-jardin", color="danger"), width="auto"),
            ]),
            html.Div(id="rt-status-jardin", className="mt-2"),
            dcc.Graph(id='rt-graph-jardin', style={'height': '300px'}),
            dcc.Interval(
                id='rt-interval-jardin',
                interval=100,
                n_intervals=0,
                disabled=True
            )
        ], width=5)
    ])
], fluid=True)

# ---
# Funciones Auxiliares (Tiempo Real)
# ---
def create_empty_realtime_figure(signal_type, theme, title="Esperando datos..."):
    bgcolor = "black" if theme == 'dark' else "white"
    fontcolor = "white" if theme == 'dark' else "black"
    y_range = None
    if signal_type == 'raw':
        y_range = [-2048, 2048]
    elif signal_type in ['attention', 'meditation']:
        y_range = [0, 100]

    layout = go.Layout(
        title=title,
        xaxis=dict(title='Tiempo (s)', gridcolor='gray'),
        yaxis=dict(title='Amplitud', range=y_range, gridcolor='gray'),
        paper_bgcolor=bgcolor,
        plot_bgcolor=bgcolor,
        font=dict(color=fontcolor),
        margin=dict(t=40, l=20, r=40, b=40)
    )
    fig = go.Figure(
        data=[go.Scatter(y=[], mode='lines', name=signal_type)],
        layout=layout
    )
    return fig

def collect_to_buffer(collector_instance, buffer_instance):
    while collector_instance.running:
        try:
            signal_value = collector_instance.get_signal_value(collector_instance.signal_type)
            buffer_instance.append(signal_value)
            time.sleep(1.0 / collector_instance.sample_freq) 
        except Exception as e:
            if collector_instance.running:
                print(f"Error en el hilo de recolección (Jardin): {e}")
    print("Hilo de recolección (Jardin) detenido.")

# ---
# Callbacks
# ---

# Callback para colapsar tarjetas de instrucciones
@dash.callback(
    Output({'type': 'collapse-jardin', 'index': dash.dependencies.MATCH}, 'is_open'),
    Input({'type': 'button-jardin', 'index': dash.dependencies.MATCH}, 'n_clicks'),
    State({'type': 'collapse-jardin', 'index': dash.dependencies.MATCH}, 'is_open'),
    prevent_initial_call=True
)
def toggle_collapse_jardin(n, is_open):
    if n:
        return not is_open
    return is_open

# Callback: Manejar botones de Conectar/Detener (Tiempo Real)
@dash.callback(
    Output('rt-status-jardin', 'children'),
    Output('rt-interval-jardin', 'disabled'),
    Output('rt-graph-jardin', 'figure'),
    Input('rt-connect-jardin', 'n_clicks'),
    Input('rt-stop-jardin', 'n_clicks'),
    State('rt-com-port-jardin', 'value'),
    State('rt-signal-type-jardin', 'value'),
    State('theme-store', 'data'),
    prevent_initial_call=True
)
def manage_realtime_connection_jardin(connect_clicks, stop_clicks, port, signal_type, theme):
    global COLLECTOR_JARDIN, THREAD_JARDIN
    
    triggered_id = dash.ctx.triggered_id
    
    if triggered_id == 'rt-connect-jardin':
        if not port:
            fig = create_empty_realtime_figure(signal_type, theme, title="Especifique un puerto")
            return dbc.Alert("Por favor, especifica un puerto serial.", color="warning"), True, fig
        
        try:
            validate_signal_type(signal_type)
        except ValueError as e:
            fig = create_empty_realtime_figure(signal_type, theme, title="Error de señal")
            return dbc.Alert(str(e), color="danger"), True, fig

        if COLLECTOR_JARDIN and COLLECTOR_JARDIN.running:
            COLLECTOR_JARDIN.stop()
            if THREAD_JARDIN and THREAD_JARDIN.is_alive():
                THREAD_JARDIN.join()
        
        LIVE_DATA_BUFFER_JARDIN.clear()
        
        try:
            COLLECTOR_JARDIN = NeuroSkyDataCollector(port=port, signal_type=signal_type, save_to_csv=False)
            COLLECTOR_JARDIN.connect()
            COLLECTOR_JARDIN.running = True
            
            THREAD_JARDIN = threading.Thread(
                target=collect_to_buffer, 
                args=(COLLECTOR_JARDIN, LIVE_DATA_BUFFER_JARDIN),
                daemon=True
            )
            THREAD_JARDIN.start()
            
            initial_fig = create_empty_realtime_figure(signal_type, theme, f"Datos en Tiempo Real: {signal_type.capitalize()}")
            return dbc.Alert(f"Conectado a {port} recolectando '{signal_type}'", color="success"), False, initial_fig

        except Exception as e:
            if COLLECTOR_JARDIN:
                COLLECTOR_JARDIN.running = False
            fig = create_empty_realtime_figure(signal_type, theme, title=f"Error de conexión: {e}")
            return dbc.Alert(f"Error al conectar: {e}", color="danger"), True, fig

    elif triggered_id == 'rt-stop-jardin':
        if COLLECTOR_JARDIN and COLLECTOR_JARDIN.running:
            COLLECTOR_JARDIN.stop()
            if THREAD_JARDIN and THREAD_JARDIN.is_alive():
                THREAD_JARDIN.join()
            LIVE_DATA_BUFFER_JARDIN.clear()
            fig = create_empty_realtime_figure(signal_type, theme, title="Conexión detenida")
            return dbc.Alert("Conexión detenida.", color="info"), True, fig
        else:
            return dbc.Alert("No hay conexión activa.", color="warning"), True, no_update
            
    return no_update, no_update, no_update


# Callback: Actualizar el gráfico en tiempo real
@dash.callback(
    Output('rt-graph-jardin', 'extendData'),
    Input('rt-interval-jardin', 'n_intervals'),
    prevent_initial_call=True
)
def update_realtime_graph_jardin(n_intervals):
    new_points = []
    while True:
        try:
            new_points.append(LIVE_DATA_BUFFER_JARDIN.popleft())
        except IndexError:
            break
    
    if not new_points:
        return no_update

    # --- 5. LÓGICA IPC: Enviar el último valor al proceso del juego ---
    if _planta_running():
        try:
            # Usar el valor más reciente de la ráfaga
            latest_value = int(new_points[-1]) 
            _shared_signal_value_jardin.value = latest_value
        except (IndexError, TypeError, ValueError):
            pass # Ignorar si new_points está vacío o el valor no es convertible
        except Exception as e:
            print(f"Error al actualizar valor compartido (Jardin): {e}")
    # --- FIN LÓGICA IPC ---

    data_to_extend = ({'y': [new_points]}, [0], 512)
    return data_to_extend

# Callback: Manejar botones del JUEGO
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
    status_text = "Estado: ejecutándose..." if running else "Estado: detenido"
    return (status_text, running, not running)
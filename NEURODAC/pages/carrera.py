#carrera.py
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
import coche  # Importar el juego Pygame

# --- IMPORTACIÓN DE MÓDULOS ---
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Importar desde la carpeta 'modules'
from modules.neurosky_data_collector import NeuroSkyDataCollector, validate_signal_type

# --- OBJETOS GLOBALES (TIEMPO REAL) ---
LIVE_DATA_BUFFER_C1 = deque()
COLLECTOR_C1 = None
THREAD_C1 = None
LIVE_DATA_BUFFER_C2 = deque()
COLLECTOR_C2 = None
THREAD_C2 = None

# --- OBJETOS GLOBALES (JUEGO PYGAME) ---
_coche_proc: Optional[Process] = None
# --- 2. Crear el valor de memoria compartida ---
_shared_signal_value_carrera = Value('i', 50) # Controlado por J1

dash.register_page(__name__, path="/carrera")

# --- FUNCIONES AUXILIARES (JUEGO PYGAME) ---
def _coche_running() -> bool:
    return _coche_proc is not None and _coche_proc.is_alive()

def _coche_start():
    global _coche_proc
    if _coche_running():
        return
    # --- 3. Pasar el valor compartido como argumento ---
    _coche_proc = Process(target=coche.main, args=(_shared_signal_value_carrera,), daemon=True)
    _coche_proc.start()

def _coche_stop():
    global _coche_proc
    _shared_signal_value_carrera.value = 50 # Resetear valor
    if _coche_proc is not None and _coche_proc.is_alive():
        try:
            os.kill(_coche_proc.pid, signal.SIGTERM)
            _coche_proc.join(timeout=1)
            if _coche_proc.is_alive():
                _coche_proc.terminate()
        except Exception as e:
            print(f"Error al detener proceso coche: {e}")
            try:
                _coche_proc.terminate()
            except Exception:
                pass
    _coche_proc = None

# --- COMPONENTES DE LAYOUT ---
signal_options_rt = [
    'raw', 'attention', 'meditation', 'blink', 'delta', 'theta', 
    'low-alpha', 'high-alpha', 'low-beta', 'high-beta', 
    'low-gamma', 'mid-gamma'
]

juego_card = dbc.Card(
    [
        dbc.CardHeader("🎮 Carrera de Coches (Atención)"),
        dbc.CardBody(
            [
                # --- 4. Texto actualizado ---
                html.P("Pulsa Jugar para abrir la ventana. Usa ←/→ para moverte.", className="mb-2"),
                html.P("La velocidad se controla con la señal de 'attention' del Jugador 1.", className="text-muted small"),
                html.P("Umbrales: > 35 (Acelera), < 25 (Frena)", className="text-muted small"),
                dbc.ButtonGroup([
                    dbc.Button("Jugar", id="btn-coche-start", color="primary"),
                    dbc.Button("Detener", id="btn-coche-stop", color="danger", outline=True),
                ], className="mb-2 w-100"),
                html.Div(id="coche-status", className="text-secondary text-center mt-2"),
            ]
        ),
    ],
    className="mb-3",
)

# Layout de la página Carrera de Coches
layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("Carrera de Coches", className="text-center"), width=12)
    ]),
    dbc.Row([
        # Columna Izquierda (Controles y Gráficas de Tiempo Real)
        dbc.Col([
            dbc.Card([
                    dbc.CardHeader(dbc.Button("¿Qué es esta página?", id={'type': 'button-carrera', 'index': 1}, color="Dark", className="w-100")),
                    dbc.Collapse(dbc.CardBody([
                        html.P(["Carrera de Coches.", html.Br(), 
                               "Compite contra otro jugador (u otro estado mental) para ganar la carrera. "
                               "La velocidad del coche dependerá de tu actividad cerebral. ¡Mantén la concentración para acelerar!"], className="card-text")
                    ]), id={'type': 'collapse-carrera', 'index': 1}, is_open=True)
                ], className="mb-2"),
                dbc.Card([
                    dbc.CardHeader(dbc.Button("¿Cómo usar la interfaz?", id={'type': 'button-carrera', 'index': 2}, color="Dark", className="w-100")),
                    dbc.Collapse(dbc.CardBody([
                        html.P(["1. Conecta la diadema del J1 (Puerto, Señal='attention').", html.Br(),
                                "2. (Opcional) Conecta la diadema del J2 para comparar gráficas.", html.Br(),
                                "3. Presiona 'Jugar' en el panel de la derecha.", html.Br(),
                                "4. Controla el coche con J1 y las flechas laterales."], className="card-text")
                    ]), id={'type': 'collapse-carrera', 'index': 2}, is_open=False)
                ]),
            
            html.Hr(),

            # --- Gráfica JUGADOR 1 (CONTROL) ---
            dbc.Label("Jugador 1 - Puerto (ej. COM3):"),
            dbc.Input(id="rt-com-port-c1", placeholder="COM3", type="text", className="mb-2"),
            dbc.Label("Jugador 1 - Tipo de Señal:"),
            dcc.Dropdown(
                id="rt-signal-type-c1",
                options=[{'label': s.capitalize(), 'value': s} for s in signal_options_rt],
                value='attention', # Default a attention para este juego
                clearable=False,
                style={'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'},
                className="mb-2"
            ),
            dbc.Row([
                dbc.Col(dbc.Button("Conectar J1", id="rt-connect-c1", color="primary", className="me-2"), width="auto"),
                dbc.Col(dbc.Button("Detener J1", id="rt-stop-c1", color="danger"), width="auto"),
            ]),
            html.Div(id="rt-status-c1", className="mt-2"),
            dcc.Graph(id='rt-graph-c1', style={'height': '300px'}),
            dcc.Interval(id='rt-interval-c1', interval=100, disabled=True),
            
            html.Hr(), # Separador

            # --- Gráfica JUGADOR 2 (COMPARACIÓN) ---
            dbc.Label("Jugador 2 - Puerto (ej. COM4):"),
            dbc.Input(id="rt-com-port-c2", placeholder="COM4", type="text", className="mb-2"),
            dbc.Label("Jugador 2 - Tipo de Señal:"),
            dcc.Dropdown(
                id="rt-signal-type-c2",
                options=[{'label': s.capitalize(), 'value': s} for s in signal_options_rt],
                value='attention', 
                clearable=False,
                style={'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'},
                className="mb-2"
            ),
            dbc.Row([
                dbc.Col(dbc.Button("Conectar J2", id="rt-connect-c2", color="primary", className="me-2"), width="auto"),
                dbc.Col(dbc.Button("Detener J2", id="rt-stop-c2", color="danger"), width="auto"),
            ]),
            html.Div(id="rt-status-c2", className="mt-2"),
            dcc.Graph(id='rt-graph-c2', style={'height': '300px'}),
            dcc.Interval(id='rt-interval-c2', interval=100, disabled=True),

        ], width=5), 

        # Columna Derecha (Visualización del Juego)
        dbc.Col(
            juego_card,
            width=7 
        )
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
                print(f"Error en el hilo de recolección (Carrera): {e}")
    print(f"Hilo de recolección (Carrera) detenido.")


# ---
# Callbacks
# ---

# Callback para colapsar tarjetas de instrucciones
@dash.callback(
    Output({'type': 'collapse-carrera', 'index': dash.dependencies.MATCH}, 'is_open'),
    Input({'type': 'button-carrera', 'index': dash.dependencies.MATCH}, 'n_clicks'),
    State({'type': 'collapse-carrera', 'index': dash.dependencies.MATCH}, 'is_open'),
    prevent_initial_call=True
)
def toggle_collapse_carrera(n, is_open):
    if n:
        return not is_open
    return is_open

# --- Callbacks JUGADOR 1 (Tiempo Real) ---
@dash.callback(
    Output('rt-status-c1', 'children'),
    Output('rt-interval-c1', 'disabled'),
    Output('rt-graph-c1', 'figure'),
    Input('rt-connect-c1', 'n_clicks'),
    Input('rt-stop-c1', 'n_clicks'),
    State('rt-com-port-c1', 'value'),
    State('rt-signal-type-c1', 'value'),
    State('theme-store', 'data'),
    prevent_initial_call=True
)
def manage_realtime_connection_c1(connect_clicks, stop_clicks, port, signal_type, theme):
    global COLLECTOR_C1, THREAD_C1
    triggered_id = dash.ctx.triggered_id
    if triggered_id == 'rt-connect-c1':
        if not port:
            fig = create_empty_realtime_figure(signal_type, theme, title="J1: Especifique puerto")
            return dbc.Alert("J1: Especifica un puerto.", color="warning"), True, fig
        try:
            validate_signal_type(signal_type)
        except ValueError as e:
            fig = create_empty_realtime_figure(signal_type, theme, title="J1: Error de señal")
            return dbc.Alert(f"J1: {e}", color="danger"), True, fig
        if COLLECTOR_C1 and COLLECTOR_C1.running:
            COLLECTOR_C1.stop()
            if THREAD_C1 and THREAD_C1.is_alive():
                THREAD_C1.join()
        LIVE_DATA_BUFFER_C1.clear()
        try:
            COLLECTOR_C1 = NeuroSkyDataCollector(port=port, signal_type=signal_type, save_to_csv=False)
            COLLECTOR_C1.connect()
            COLLECTOR_C1.running = True
            THREAD_C1 = threading.Thread(
                target=collect_to_buffer, 
                args=(COLLECTOR_C1, LIVE_DATA_BUFFER_C1),
                daemon=True
            )
            THREAD_C1.start()
            initial_fig = create_empty_realtime_figure(signal_type, theme, f"J1: {signal_type.capitalize()}")
            return dbc.Alert(f"J1: Conectado a {port}", color="success"), False, initial_fig
        except Exception as e:
            if COLLECTOR_C1:
                COLLECTOR_C1.running = False
            fig = create_empty_realtime_figure(signal_type, theme, title=f"J1: Error {e}")
            return dbc.Alert(f"J1: Error al conectar: {e}", color="danger"), True, fig
    elif triggered_id == 'rt-stop-c1':
        if COLLECTOR_C1 and COLLECTOR_C1.running:
            COLLECTOR_C1.stop()
            if THREAD_C1 and THREAD_C1.is_alive():
                THREAD_C1.join()
            LIVE_DATA_BUFFER_C1.clear()
            fig = create_empty_realtime_figure(signal_type, theme, title="J1: Detenido")
            return dbc.Alert("J1: Conexión detenida.", color="info"), True, fig
        else:
            return dbc.Alert("J1: No hay conexión activa.", color="warning"), True, no_update
    return no_update, no_update, no_update

@dash.callback(
    Output('rt-graph-c1', 'extendData'),
    Input('rt-interval-c1', 'n_intervals'),
    prevent_initial_call=True
)
def update_realtime_graph_c1(n_intervals):
    new_points = []
    while True:
        try:
            new_points.append(LIVE_DATA_BUFFER_C1.popleft())
        except IndexError:
            break
    if not new_points:
        return no_update

    # --- 5. LÓGICA IPC: Enviar el último valor (de J1) al juego ---
    if _coche_running():
        try:
            latest_value = int(new_points[-1])
            _shared_signal_value_carrera.value = latest_value
        except (IndexError, TypeError, ValueError):
            pass # Ignorar
        except Exception as e:
            print(f"Error al actualizar valor compartido (Carrera J1): {e}")
    # --- FIN LÓGICA IPC ---

    data_to_extend = ({'y': [new_points]}, [0], 512)
    return data_to_extend

# --- Callbacks JUGADOR 2 (Tiempo Real) ---
@dash.callback(
    Output('rt-status-c2', 'children'),
    Output('rt-interval-c2', 'disabled'),
    Output('rt-graph-c2', 'figure'),
    Input('rt-connect-c2', 'n_clicks'),
    Input('rt-stop-c2', 'n_clicks'),
    State('rt-com-port-c2', 'value'),
    State('rt-signal-type-c2', 'value'),
    State('theme-store', 'data'),
    prevent_initial_call=True
)
def manage_realtime_connection_c2(connect_clicks, stop_clicks, port, signal_type, theme):
    global COLLECTOR_C2, THREAD_C2
    triggered_id = dash.ctx.triggered_id
    if triggered_id == 'rt-connect-c2':
        if not port:
            fig = create_empty_realtime_figure(signal_type, theme, title="J2: Especifique puerto")
            return dbc.Alert("J2: Especifica un puerto.", color="warning"), True, fig
        try:
            validate_signal_type(signal_type)
        except ValueError as e:
            fig = create_empty_realtime_figure(signal_type, theme, title="J2: Error de señal")
            return dbc.Alert(f"J2: {e}", color="danger"), True, fig
        if COLLECTOR_C2 and COLLECTOR_C2.running:
            COLLECTOR_C2.stop()
            if THREAD_C2 and THREAD_C2.is_alive():
                THREAD_C2.join()
        LIVE_DATA_BUFFER_C2.clear()
        try:
            COLLECTOR_C2 = NeuroSkyDataCollector(port=port, signal_type=signal_type, save_to_csv=False)
            COLLECTOR_C2.connect()
            COLLECTOR_C2.running = True
            THREAD_C2 = threading.Thread(
                target=collect_to_buffer, 
                args=(COLLECTOR_C2, LIVE_DATA_BUFFER_C2),
                daemon=True
            )
            THREAD_C2.start()
            initial_fig = create_empty_realtime_figure(signal_type, theme, f"J2: {signal_type.capitalize()}")
            return dbc.Alert(f"J2: Conectado a {port}", color="success"), False, initial_fig
        except Exception as e:
            if COLLECTOR_C2:
                COLLECTOR_C2.running = False
            fig = create_empty_realtime_figure(signal_type, theme, title=f"J2: Error {e}")
            return dbc.Alert(f"J2: Error al conectar: {e}", color="danger"), True, fig
    elif triggered_id == 'rt-stop-c2':
        if COLLECTOR_C2 and COLLECTOR_C2.running:
            COLLECTOR_C2.stop()
            if THREAD_C2 and THREAD_C2.is_alive():
                THREAD_C2.join()
            LIVE_DATA_BUFFER_C2.clear()
            fig = create_empty_realtime_figure(signal_type, theme, title="J2: Detenido")
            return dbc.Alert("J2: Conexión detenida.", color="info"), True, fig
        else:
            return dbc.Alert("J2: No hay conexión activa.", color="warning"), True, no_update
    return no_update, no_update, no_update

@dash.callback(
    Output('rt-graph-c2', 'extendData'),
    Input('rt-interval-c2', 'n_intervals'),
    prevent_initial_call=True
)
def update_realtime_graph_c2(n_intervals):
    # Este callback solo actualiza la gráfica del J2, no controla el juego.
    new_points = []
    while True:
        try:
            new_points.append(LIVE_DATA_BUFFER_C2.popleft())
        except IndexError:
            break
    if not new_points:
        return no_update
    data_to_extend = ({'y': [new_points]}, [0], 512)
    return data_to_extend

# --- Callback: Manejar botones del JUEGO ---
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
    status_text = "Estado: ejecutándose..." if running else "Estado: detenido"
    return (status_text, running, not running)
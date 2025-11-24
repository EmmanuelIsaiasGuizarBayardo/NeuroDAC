# pages/tiempo_real.py
import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import os
import time
import threading
from collections import deque

# --- IMPORTACIÓN DE MÓDULOS ---
# Añadimos la ruta raíz del proyecto (un nivel arriba de 'pages')
# para que Python pueda encontrar la carpeta 'modules'
import sys
# Obtener la ruta absoluta del directorio que contiene este script (pages)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Obtener la ruta del directorio padre (la raíz del proyecto)
parent_dir = os.path.dirname(current_dir)
# Añadir el directorio padre al sys.path
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Ahora podemos importar desde la carpeta 'modules'
from modules.neurosky_data_collector import NeuroSkyDataCollector, validate_signal_type

# --- OBJETOS GLOBALES PARA TIEMPO REAL ---
# Usamos 'deque' como una cola FIFO (First-In, First-Out) eficiente
# para almacenar temporalmente los puntos nuevos entre intervalos.
LIVE_DATA_BUFFER = deque()

# Instancia global para el colector. La manejaremos con los callbacks.
global_collector = None
# Hilo global para el proceso de recolección de datos
collector_thread = None

# --- REGISTRO DE LA PÁGINA ---
dash.register_page(
    __name__,
    path="/tiempo-real",
    name="Tiempo Real"
)

# --- FUNCIÓN PARA CREAR EL LAYOUT DE TIEMPO REAL ---
def create_realtime_layout():
    signal_options_rt = [
        'raw', 'attention', 'meditation', 'blink', 'delta', 'theta', 
        'low-alpha', 'high-alpha', 'low-beta', 'high-beta', 
        'low-gamma', 'mid-gamma'
    ]
    
    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Input(id="rt-com-port-input", placeholder="Puerto (ej. COM3 o /dev/ttyUSB0)", type="text"), width=3),
            dbc.Col(dcc.Dropdown(
                id="rt-signal-type-dropdown",
                options=[{'label': s.capitalize(), 'value': s} for s in signal_options_rt],
                value='raw',
                clearable=False
            ), width=3),
            dbc.Col(dbc.Button("Conectar e Iniciar", id="rt-connect-button", color="primary", className="me-2"), width="auto"),
            dbc.Col(dbc.Button("Detener", id="rt-stop-button", color="danger"), width="auto"),
        ]),
        dbc.Row([
            dbc.Col(html.Div(id="rt-connection-status", className="mt-2"), width=12)
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(id="rt-live-graph", style={'height': '75vh'}), width=12)
        ]),
        
        # Este componente es el "motor" que dispara el callback de actualización
        dcc.Interval(
            id='rt-interval-component',
            interval=100,      # Actualiza 10 veces por segundo (100ms)
            n_intervals=0,
            disabled=True      # Empezar deshabilitado
        )
    ])

# --- LAYOUT DE LA PÁGINA ---
# El layout principal es simplemente el contenedor con el layout de tiempo real
layout = dbc.Container([
    create_realtime_layout()
], fluid=True, className="mt-4")


# --- FUNCIÓN AUXILIAR PARA GRÁFICO EN TIEMPO REAL ---
def create_empty_realtime_figure(signal_type, theme, title="Esperando datos..."):
    """
    Crea la figura inicial (vacía) para el gráfico en tiempo real.
    """
    bgcolor = "black" if theme == 'dark' else "white"
    fontcolor = "white" if theme == 'dark' else "black"

    # Determinar rango del eje Y basado en el tipo de señal
    y_range = None
    if signal_type == 'raw':
        y_range = [-2048, 2048]
    elif signal_type in ['attention', 'meditation']:
        y_range = [0, 100]

    layout = go.Layout(
        title=title,
        xaxis=dict(
            title='Tiempo (s)',
            gridcolor='gray',
            zeroline=True,
            zerolinecolor=fontcolor,
            zerolinewidth=1
        ),
        yaxis=dict(title='Amplitud (µV)', range=y_range, gridcolor='gray', zeroline=True, zerolinecolor=fontcolor, zerolinewidth=1),
        # dict(
        #     gridcolor='gray',
        #     zeroline=True,
        #     zerolinecolor=fontcolor,
        #     zerolinewidth=1
        # ),
        paper_bgcolor=bgcolor,
        plot_bgcolor=bgcolor,
        font=dict(color=fontcolor)
    )
    
    # Creamos una traza inicial vacía
    fig = go.Figure(
        data=[go.Scatter(y=[], mode='lines', name=signal_type)],
        layout=layout
    )
    
    return fig

# ---
# Callbacks para TIEMPO REAL
# ---

# Función de recolección de datos que se ejecutará en un hilo
def collect_to_buffer(collector_instance):
    """
    Función objetivo para el hilo. Lee datos del colector y los
    añade al LIVE_DATA_BUFFER global.
    """
    while collector_instance.running:
        try:
            signal_value = collector_instance.get_signal_value(collector_instance.signal_type)
            LIVE_DATA_BUFFER.append(signal_value)
            time.sleep(1.0 / collector_instance.sample_freq)
        except Exception as e:
            if collector_instance.running:
                print(f"Error en el hilo de recolección: {e}")
    print("Hilo de recolección detenido.")


# Callback 1: Manejar botones de Conectar/Detener y crear gráfico inicial
@dash.callback(
    Output('rt-connection-status', 'children'),
    Output('rt-interval-component', 'disabled'),
    Output('rt-live-graph', 'figure'),
    Input('rt-connect-button', 'n_clicks'),
    Input('rt-stop-button', 'n_clicks'),
    State('rt-com-port-input', 'value'),
    State('rt-signal-type-dropdown', 'value'),
    State('theme-store', 'data'),      # Lee el tema desde el dcc.Store en interfaz.py
    prevent_initial_call=True
)
def manage_realtime_connection(connect_clicks, stop_clicks, port, signal_type, theme):
    global global_collector, collector_thread
    
    triggered_id = dash.ctx.triggered_id
    
    if triggered_id == 'rt-connect-button':
        if not port:
            fig = create_empty_realtime_figure(signal_type, theme, title="Especifique un puerto")
            return dbc.Alert("Por favor, especifica un puerto serial.", color="warning"), True, fig
        
        try:
            validate_signal_type(signal_type)
        except ValueError as e:
            fig = create_empty_realtime_figure(signal_type, theme, title="Error de señal")
            return dbc.Alert(str(e), color="danger"), True, fig

        # --- Detener conexión anterior si existe ---
        if global_collector and global_collector.running:
            global_collector.stop()
            if collector_thread and collector_thread.is_alive():
                collector_thread.join()
        
        LIVE_DATA_BUFFER.clear()
        
        # --- Iniciar nueva conexión ---
        try:
            global_collector = NeuroSkyDataCollector(
                port=port, 
                signal_type=signal_type, 
                save_to_csv=False
            )
            global_collector.connect()
            global_collector.running = True # <-- El FIX del Punto 1
            
            collector_thread = threading.Thread(
                target=collect_to_buffer, 
                args=(global_collector,),
                daemon=True
            )
            collector_thread.start()
            
            initial_fig = create_empty_realtime_figure(signal_type, theme, f"Datos en Tiempo Real: {signal_type.capitalize()}")
            
            return dbc.Alert(f"Conectado a {port} recolectando '{signal_type}'", color="success"), False, initial_fig

        except Exception as e:
            if global_collector:
                global_collector.running = False
            fig = create_empty_realtime_figure(signal_type, theme, title=f"Error de conexión: {e}")
            return dbc.Alert(f"Error al conectar: {e}", color="danger"), True, fig

    elif triggered_id == 'rt-stop-button':
        if global_collector and global_collector.running:
            global_collector.stop()
            if collector_thread and collector_thread.is_alive():
                collector_thread.join()
            LIVE_DATA_BUFFER.clear()
            fig = create_empty_realtime_figure(signal_type, theme, title="Conexión detenida por el usuario")
            return dbc.Alert("Conexión detenida.", color="info"), True, fig
        else:
            return dbc.Alert("No hay conexión activa para detener.", color="warning"), True, no_update
            
    return no_update, no_update, no_update


# Callback 2: Actualizar el gráfico en tiempo real (El "motor" EFICIENTE)
@dash.callback(
    Output('rt-live-graph', 'extendData'),
    Input('rt-interval-component', 'n_intervals'),
    prevent_initial_call=True
)
def update_realtime_graph(n_intervals):
    
    new_points = []
    while True:
        try:
            new_points.append(LIVE_DATA_BUFFER.popleft())
        except IndexError:
            break
    
    if not new_points:
        return no_update

    # Envía los nuevos datos a 'extendData'
    # 'y': [new_points] -> Apila estos puntos en el eje Y
    # [0] -> Hazlo en la primera traza (trace 0)
    # 512 -> Mantén solo los últimos 512 puntos
    data_to_extend = ({'y': [new_points]}, [0], 512)
    
    return data_to_extend
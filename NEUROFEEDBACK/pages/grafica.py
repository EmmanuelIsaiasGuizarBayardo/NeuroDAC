# pages/grafica.py — Visualización EEG v5
# Página principal: visualización de señales EEG pregrabadas
# con filtrado por bandas, reproducción automática y panel educativo.

import dash
from dash import dcc, html, Input, Output, State, no_update, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objs as go
import mne
import os
import numpy as np

dash.register_page(
    __name__, path="/",
    name="Visualización EEG",
    redirect_from=["/grafica"]
)

# =============================================================
# Carga de datos
# =============================================================
csv_path = os.path.join(
    os.path.dirname(__file__), "..", "data",
    "sub-hc1_ses-hc_task-rest_eeg_clean.csv"
    #"sub-hc1_ses-hc_task-rest_eeg_maestro.csv"
    #"data.csv"
)
df = pd.read_csv(csv_path)
df.columns = df.columns.str.strip()
df.rename(columns={"git Timestamp": "Timestamp"}, inplace=True)

# Lista de canales disponibles (todas las columnas excepto Timestamp)
signal_options = df.columns.drop('Timestamp').tolist()
DEFAULT_SIGNAL = signal_options[0]  # Primer canal como default

# Parámetros de muestreo
SAMPLE_RATE = 512
MAX_DURATION = int(len(df) / SAMPLE_RATE)

# Crear objeto RawArray de MNE para filtrado
data_np = df[signal_options].to_numpy().T
info = mne.create_info(
    ch_names=signal_options,
    sfreq=SAMPLE_RATE,
    ch_types=['eeg'] * len(signal_options)
)
raw = mne.io.RawArray(data_np, info)

# =============================================================
# Contenido educativo (divulgativo, en Times New Roman)
# =============================================================
EDU = {
    'none': (
        'Señal EEG sin procesar',
        'Lo que ves aquí es la actividad eléctrica de tu cerebro tal cual la capta '
        'el electrodo. Es como escuchar todas las conversaciones de un salón al mismo '
        'tiempo; una mezcla de muchas frecuencias distintas. Los picos grandes suelen '
        'ser artefactos (parpadeos, movimientos musculares) y no actividad cerebral real.'
    ),
    'delta': (
        'Ondas Delta · Las más lentas',
        'Las ondas delta son como el latido profundo del cerebro dormido. Aparecen '
        'cuando estamos en sueño profundo y nuestro cuerpo se dedica a repararse. '
        'Si las vemos en alguien despierto, podría indicar que algo no anda bien '
        'en el cerebro; por eso los neurólogos les prestan mucha atención.'
    ),
    'theta': (
        'Ondas Theta · Soñar despierto',
        'Theta es la frecuencia de la creatividad y la ensoñación. Aparece cuando '
        'tu mente divaga, cuando meditas profundamente, o cuando estás a punto de '
        'quedarte dormido. El hipocampo; la región del cerebro encargada de formar '
        'memorias; usa este ritmo para consolidar lo que aprendiste durante el día.'
    ),
    'alpha': (
        'Ondas Alpha · Relajación consciente',
        'Las ondas alpha fueron las primeras que se descubrieron en el EEG, allá por '
        '1929. Aparecen cuando cierras los ojos y te relajas; es como si tu corteza '
        'visual dijera "no hay nada que ver, descansemos". Si abres los ojos o '
        'empiezas a pensar en algo, desaparecen inmediatamente. Por eso se usan mucho '
        'en neurofeedback para enseñar a relajarse.'
    ),
    'beta': (
        'Ondas Beta · Pensamiento activo',
        'Beta es la frecuencia del cerebro concentrado. Cuando resuelves un problema '
        'de matemáticas, lees con atención o mantienes una conversación, tu cerebro '
        'vibra en beta. Hay dos tipos: beta baja (concentración calmada) y beta alta '
        '(estrés o ansiedad). En las interfaces cerebro-computadora, esta banda es '
        'clave para detectar intenciones de movimiento.'
    ),
    'gamma': (
        'Ondas Gamma · El pegamento de la conciencia',
        'Gamma es la frecuencia más rápida y misteriosa. Se cree que es responsable de '
        '"pegar" toda la información sensorial en una experiencia unificada; lo que los '
        'neurocientíficos llaman binding. Cuando ves un gato, gamma une su forma, color, '
        'sonido y textura en un solo percepto. Son difíciles de medir porque los músculos '
        'de la cara generan señales similares.'
    ),
}

VINFO = {
    'única': (
        'Vista única',
        'Visualiza un solo canal. Ideal para examinar la forma de la señal en '
        'detalle o aplicar filtros para aislar una banda de frecuencia.'
    ),
    'multi': (
        'Vista multicanal',
        'Montaje vertical como en un electroencefalógrafo clínico. Cada canal '
        'con su propio color para distinguir regiones cerebrales.'
    ),
    'superpuesta': (
        'Vista superpuesta',
        'Todas las señales en el mismo eje. Útil para comparar amplitudes; '
        'se recomienda con 2–4 señales.'
    ),
}

# Bandas de frecuencia para filtrado
BANDS = {
    'delta': (0.5, 4),
    'theta': (4, 8),
    'alpha': (8, 12),
    'beta': (12, 30),
    'gamma': (30, 50),
}


# =============================================================
# Funciones auxiliares
# =============================================================
def get_colors(theme):
    """Retorna colores de gráfica según el tema activo."""
    if theme == 'dark':
        return {
            'bg': '#222', 'paper': '#222', 'font': '#fff',
            'grid': 'rgba(255,255,255,0.08)',
            'zero': 'rgba(255,255,255,0.2)',
        }
    return {
        'bg': '#fff', 'paper': '#fff', 'font': '#212529',
        'grid': 'rgba(0,0,0,0.06)',
        'zero': 'rgba(0,0,0,0.15)',
    }


def symmetric_yrange(data, padding=1.1):
    """Calcula un rango Y simétrico centrado en 0."""
    if len(data) == 0:
        return [-500, 500]
    max_abs = max(abs(np.min(data)), abs(np.max(data)))
    if max_abs == 0:
        return [-100, 100]
    return [-max_abs * padding, max_abs * padding]


# =============================================================
# Layout
# =============================================================
layout = html.Div(className='page-content', children=[
    dbc.Row([
        # --- Panel principal (izquierda) ---
        dbc.Col(width=9, children=[
            html.H2("Visualización EEG", className="section-title"),

            # Selector de rango de tiempo
            html.Div(className="mb-2", children=[
                dbc.Label(
                    "Rango de tiempo (segundos):",
                    style={"fontSize": "0.82rem", "fontWeight": "500"}
                ),
                dcc.RangeSlider(
                    id='time-range-slider',
                    min=0, max=MAX_DURATION, step=1,
                    value=[0, 10],
                    marks={
                        i: f'{i}s'
                        for i in range(
                            0, MAX_DURATION + 1,
                            max(30, int(MAX_DURATION / 5))
                        )
                    },
                    tooltip={"placement": "bottom", "always_visible": False},
                ),
            ]),

            # Controles de reproducción
            html.Div(className="playback-controls mb-2", children=[
                dbc.Button("▶ Play", id='btn-play', className='btn-play', size="sm"),
                dbc.Button("■ Stop", id='btn-stop', className='btn-play-stop', size="sm"),
                html.Span("Velocidad:", className="speed-label ms-2"),
                dcc.Dropdown(
                    id='playback-speed',
                    options=[
                        {'label': '0.5x', 'value': 0.25},
                        {'label': '1x', 'value': 0.5},
                        {'label': '2x', 'value': 1.0},
                        {'label': '4x', 'value': 2.0},
                    ],
                    value=0.5, clearable=False,
                    style={"width": "80px", "display": "inline-block"}
                ),
                html.Span(id='playback-status', className="speed-label ms-2"),
            ]),

            # Selector de modo de vista
            dbc.RadioItems(
                id='view-mode',
                options=[
                    {'label': '  Vista única', 'value': 'única'},
                    {'label': '  Vista multicanal', 'value': 'multi'},
                    {'label': '  Vista superpuesta', 'value': 'superpuesta'},
                ],
                value='única', inline=True, className="mb-2"
            ),

            # Controles de vista única (señal + filtro)
            html.Div(id='filter-selector-container', children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Señal:", style={"fontSize": "0.8rem"}),
                        dcc.Dropdown(
                            id='signal-selector',
                            options=[{'label': s, 'value': s} for s in signal_options],
                            value=DEFAULT_SIGNAL,
                        ),
                    ], width=9),
                    dbc.Col([
                        dbc.Label("Filtro:", style={"fontSize": "0.8rem"}),
                        dcc.Dropdown(
                            id='filter-selector',
                            options=[
                                {'label': 'Sin filtro', 'value': 'none'},
                                {'label': 'Delta (0.5–4 Hz)', 'value': 'delta'},
                                {'label': 'Theta (4–8 Hz)', 'value': 'theta'},
                                {'label': 'Alpha (8–12 Hz)', 'value': 'alpha'},
                                {'label': 'Beta (12–30 Hz)', 'value': 'beta'},
                                {'label': 'Gamma (30–50 Hz)', 'value': 'gamma'},
                            ],
                            value='none', clearable=False,
                        ),
                    ], width=3),
                ])
            ]),

            # Controles de vista multicanal/superpuesta
            html.Div(id='channel-selector-container', children=[
                dbc.Label("Canales:", style={"fontSize": "0.8rem"}),
                dbc.Row([
                    dbc.Col(
                        dcc.Dropdown(
                            id='channel-selector',
                            options=[{'label': s, 'value': s} for s in signal_options],
                            value=signal_options[:24],
                            multi=True, searchable=True,
                            placeholder="Selecciona canales...",
                        ),
                        width=10
                    ),
                    dbc.Col(
                        dbc.ButtonGroup([
                            dbc.Button(
                                "Todo", id="select-all-channels",
                                size="sm", className="btn-nd-primary"
                            ),
                            dbc.Button(
                                "Ninguno", id="clear-channels",
                                size="sm", className="btn-nd-danger"
                            ),
                        ]),
                        width=2,
                        className="d-flex align-items-end justify-content-end"
                    ),
                ])
            ]),

            # Gráfica EEG
            html.Div(
                className="graph-container mt-2",
                style={'height': 'calc(100vh - 320px)'},
                children=[
                    dcc.Graph(
                        id='eeg-graph',
                        style={'height': '100%', 'minHeight': '520px'}
                    )
                ]
            ),
        ]),

        # --- Panel lateral derecho ---
        dbc.Col(width=3, children=[
            html.Div(id='edu-content-panel', className='edu-panel'),
            html.Div(id='view-mode-info-panel', className='edu-panel'),
            html.Hr(style={"borderColor": "var(--nd-border)"}),
            dbc.Button(
                "Jardín Mental", href="/jardin",
                className="btn-nd-primary w-100 mb-2", size="sm"
            ),
            dbc.Button(
                "Carrera Neural", href="/carrera",
                className="btn-nd-primary w-100 mb-2", size="sm"
            ),
            # Decoración animada de neuronas
            html.Div(className='neuron-decoration', style={"height": "250px"}),
        ]),
    ]),

    # Intervalo para reproducción automática (deshabilitado por defecto)
    dcc.Interval(
        id='playback-interval', interval=500,
        disabled=True, n_intervals=0
    ),
    dcc.Store(id='playback-state', data={'playing': False, 'position': 0}),
])


# =============================================================
# Callbacks
# =============================================================

# Mostrar/ocultar controles según el modo de vista
@dash.callback(
    Output('filter-selector-container', 'style'),
    Output('channel-selector-container', 'style'),
    Input('view-mode', 'value')
)
def toggle_tools(view_mode):
    if view_mode == 'única':
        return {'display': 'block'}, {'display': 'none'}
    return {'display': 'none'}, {'display': 'block'}


# Botones de seleccionar todo / ninguno en canales
@dash.callback(
    Output('channel-selector', 'value'),
    Input('select-all-channels', 'n_clicks'),
    Input('clear-channels', 'n_clicks'),
    prevent_initial_call=True
)
def update_channels(select_all, clear):
    btn = callback_context.triggered[0]['prop_id'].split('.')[0]
    return signal_options if btn == 'select-all-channels' else []


# Actualizar panel educativo según filtro y modo de vista
@dash.callback(
    Output('edu-content-panel', 'children'),
    Input('filter-selector', 'value'),
    Input('view-mode', 'value')
)
def update_edu(filter_band, view_mode):
    if view_mode != 'única':
        return [
            html.H6("Exploración multicanal"),
            html.P(
                "Cada canal con su propio color. Observa cómo diferentes "
                "partes del cerebro se activan de manera distinta.",
                style={"fontSize": "0.88rem"}
            ),
        ]
    title, text = EDU.get(filter_band, EDU['none'])
    return [
        html.H6(title),
        html.P(text, style={"fontSize": "0.88rem"}),
    ]


# Actualizar panel de información del modo de vista
@dash.callback(
    Output('view-mode-info-panel', 'children'),
    Input('view-mode', 'value')
)
def update_view_info(view_mode):
    title, text = VINFO.get(view_mode, VINFO['única'])
    return [
        html.H6(title),
        html.P(text, style={"fontSize": "0.88rem"}),
    ]


# Controlar reproducción automática (Play/Stop)
@dash.callback(
    Output('playback-interval', 'disabled'),
    Output('playback-interval', 'interval'),
    Output('playback-status', 'children'),
    Output('playback-state', 'data'),
    Input('btn-play', 'n_clicks'),
    Input('btn-stop', 'n_clicks'),
    State('playback-speed', 'value'),
    State('time-range-slider', 'value'),
    State('playback-state', 'data'),
    prevent_initial_call=True
)
def control_playback(play_clicks, stop_clicks, speed, slider_range, state):
    triggered = callback_context.triggered[0]['prop_id'].split('.')[0]
    if triggered == 'btn-play':
        window = slider_range[1] - slider_range[0]
        interval_ms = int(500 / (speed / 0.5))
        return (
            False, interval_ms, "▶ Reproduciendo...",
            {'playing': True, 'position': slider_range[0], 'window': window}
        )
    return True, 500, "", {'playing': False, 'position': 0, 'window': 10}


# Avanzar la ventana de tiempo durante reproducción (con loop)
@dash.callback(
    Output('time-range-slider', 'value'),
    Input('playback-interval', 'n_intervals'),
    State('playback-state', 'data'),
    State('playback-speed', 'value'),
    State('time-range-slider', 'value'),
    prevent_initial_call=True
)
def advance_playback(n_intervals, state, speed, current_range):
    if not state or not state.get('playing'):
        return no_update
    window = current_range[1] - current_range[0]
    new_start = current_range[0] + speed
    # Loop: volver al inicio al llegar al final
    if new_start + window >= MAX_DURATION:
        new_start = 0
    return [new_start, new_start + window]


# Actualizar la gráfica EEG principal
@dash.callback(
    Output('eeg-graph', 'figure'),
    Input('signal-selector', 'value'),
    Input('time-range-slider', 'value'),
    Input('view-mode', 'value'),
    Input('theme-store', 'data'),
    Input('filter-selector', 'value'),
    Input('channel-selector', 'value')
)
def update_graph(signal, time_range, view_mode, theme, filter_band, channels):
    c = get_colors(theme)
    start, end = time_range
    start_idx = int(start * SAMPLE_RATE)
    end_idx = int(end * SAMPLE_RATE)

    # --- Vista única ---
    if view_mode == 'única':
        raw_filtered = raw.copy()
        if filter_band in BANDS:
            raw_filtered.filter(
                *BANDS[filter_band],
                fir_design='firwin', verbose='ERROR'
            )
        ch_idx = raw.ch_names.index(signal)
        data_arr, times = raw_filtered[ch_idx, start_idx:end_idx]
        times = times.flatten()
        y = data_arr[0]

        return go.Figure(
            data=[go.Scatter(x=times, y=y, mode='lines', line=dict(width=1.2))],
            layout=go.Layout(
                title=dict(text=signal, font=dict(size=13)),
                xaxis=dict(
                    title='Tiempo (s)',
                    gridcolor=c['grid'], zeroline=False
                ),
                yaxis=dict(
                    title='Amplitud (µV)',
                    gridcolor=c['grid'],
                    range=symmetric_yrange(y),
                    zeroline=True,
                    zerolinecolor=c['zero'], zerolinewidth=1.5
                ),
                font=dict(family="Outfit", color=c['font'], size=11),
                height=650,
                paper_bgcolor=c['paper'], plot_bgcolor=c['bg'],
                margin=dict(t=35, l=60, r=20, b=50),
            )
        )

    # --- Vista multicanal ---
    elif view_mode == 'multi':
        selected = channels if channels else [DEFAULT_SIGNAL]
        picks = [raw.ch_names.index(ch) for ch in selected]
        data_arr, times = raw[picks, start_idx:end_idx]
        times = times.flatten()

        step = 1.0 / len(selected)
        height = max(650, len(selected) * 50)
        layout_fig = go.Layout(
            showlegend=False,
            paper_bgcolor=c['paper'], plot_bgcolor=c['bg'],
            autosize=False, height=height,
            margin=dict(t=35, l=60, r=20, b=35),
            xaxis=dict(
                title='Tiempo (s)', side='top',
                showgrid=True, gridcolor=c['grid'],
                zeroline=False, color=c['font']
            ),
        )

        traces = []
        annotations = []
        for ii, ch in enumerate(selected):
            domain = [1 - (ii + 1) * step, 1 - ii * step]
            axis_id = '' if ii == 0 else str(ii + 1)

            # Crear eje Y individual para cada canal
            layout_fig[f'yaxis{axis_id}'] = go.layout.YAxis(
                domain=domain, showticklabels=False,
                zeroline=True, zerolinecolor=c['zero'],
                zerolinewidth=0.5, gridcolor=c['grid']
            )
            traces.append(go.Scatter(
                x=times, y=data_arr[ii],
                yaxis=f'y{axis_id}',
                mode='lines', line=dict(width=0.8)
            ))
            annotations.append(go.layout.Annotation(
                x=-0.06, y=sum(domain) / 2,
                xref='paper', yref=f'y{axis_id}',
                text=ch, showarrow=False,
                font=dict(size=9, color=c['font'])
            ))

        layout_fig.annotations = annotations
        layout_fig.font = dict(family="Outfit", color=c['font'], size=11)
        return go.Figure(data=traces, layout=layout_fig)

    # --- Vista superpuesta ---
    else:
        selected = channels if channels else [DEFAULT_SIGNAL]
        picks = [raw.ch_names.index(ch) for ch in selected]
        data_arr, times = raw[picks, start_idx:end_idx]
        times = times.flatten()

        fig = go.Figure()
        for i, ch in enumerate(selected):
            fig.add_trace(go.Scatter(
                x=times, y=data_arr[i],
                name=ch, mode='lines', line=dict(width=1)
            ))

        fig.update_layout(
            title=dict(text="Señales superpuestas", font=dict(size=13)),
            xaxis_title="Tiempo (s)",
            yaxis_title="Amplitud (µV)",
            yaxis=dict(
                range=symmetric_yrange(data_arr.flatten()),
                zeroline=True,
                zerolinecolor=c['zero'], zerolinewidth=1.5
            ),
            paper_bgcolor=c['paper'], plot_bgcolor=c['bg'],
            font=dict(family="Outfit", color=c['font'], size=11),
            height=650,
            margin=dict(t=35, l=60, r=20, b=50),
        )
        return fig

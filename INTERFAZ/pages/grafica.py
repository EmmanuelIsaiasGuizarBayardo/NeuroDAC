#grafica.py
import dash
from dash import dcc, html, Input, Output, State, MATCH
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objs as go
import mne
import os

dash.register_page(
    __name__,
    path="/",                            
    name="Gráfica",
    redirect_from=["/grafica"]         
)

# Leer datos
csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "data.csv")
df = pd.read_csv(csv_path)
df.columns = df.columns.str.strip()
df.rename(columns={"git Timestamp": "Timestamp"}, inplace=True)
signal_options = df.columns.drop('Timestamp').tolist()

# Definir tasa de muestreo y duración máxima
sample_rate = 512
max_duration = int(len(df) / sample_rate)

# Reorganizar los datos para MNE
data = df[signal_options].to_numpy().T
info = mne.create_info(ch_names=signal_options, sfreq=sample_rate, ch_types=['eeg'] * len(signal_options))
raw = mne.io.RawArray(data, info)


layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("Visualización EEG - NeuroDAC", className="text-center"), width=12)
    ]),
    dbc.Row([
        # Módulo izquierdo
        dbc.Col(width=9, children=[
            # Rango de tiempo
            dbc.Label("Selecciona rango de tiempo (segundos):"),
            dcc.RangeSlider(
                id='time-range-slider',
                min=0, max=max_duration, step=10,
                value=[0, 10],
                marks={i: f'{i}s' for i in range(0, max_duration + 1, max(30, int(max_duration/5)))},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            # Selector de modo de vista
            dbc.RadioItems(
                id='view-mode',
                options=[
                    {'label': 'Vista única', 'value': 'única'},
                    {'label': 'Vista multicanal', 'value': 'multi'},
                    {'label': 'Vista superpuesta', 'value': 'superpuesta'}
                ], value='única', inline=True
            ),
            # Filtros y tipo de señal (para vista única)
            html.Div(
                id='filter-selector-container',
                children=dbc.Row([
                    dbc.Col([
                        dbc.Label("Tipo de señal:"),
                        dcc.Dropdown(
                            id='signal-selector',
                            options=[{'label': sig, 'value': sig} for sig in signal_options],
                            value='Raw'
                        )
                    ], width=9),
                    dbc.Col([
                        dbc.Label("Filtro de frecuencia:"),
                        dcc.Dropdown(
                            id='filter-selector',
                            options=[
                                {'label': 'Sin filtro', 'value': 'none'},
                                {'label': 'Delta (0.5-4 Hz)', 'value': 'delta'},
                                {'label': 'Theta (4-8 Hz)', 'value': 'theta'},
                                {'label': 'Alpha (8-12 Hz)', 'value': 'alpha'},
                                {'label': 'Beta (12-30 Hz)', 'value': 'beta'},
                                {'label': 'Gamma (30-50 Hz)', 'value': 'gamma'}
                            ],
                            value='none',
                            clearable=False,
                        )
                    ], width=3)
                ])
            ),
            # Checklist de canales (para vista multicanal y superpuesta)
            html.Div(
                id='channel-selector-container',
                children=[
                    dbc.Label("Selecciona los canales a mostrar:"),
                    dbc.Row([
                        dbc.Col(
                            html.Div([
                                dcc.Dropdown(
                                    id='channel-selector',
                                    options=[{'label': sig, 'value': sig} for sig in signal_options],
                                    value=signal_options[:24],
                                    multi=True,
                                    searchable=True,
                                    placeholder="Escribe o selecciona un canal...",
                                    style={'width': '95%'}
                                )
                            ], """style={
                                'minHeight': '66px',
                                'maxHeight': '99px',
                                'overflowY': 'auto',
                                'overflowX': 'hidden'
                            }"""),
                            width=10
                        ),
                        dbc.Col(
                            dbc.ButtonGroup([
                                dbc.Button("Todo", id="select-all-channels", size="md", color="secondary"),
                                dbc.Button("Ninguno", id="clear-channels", size="md", color="secondary")
                            ]),
                            width=2, className="d-flex align-items-center justify-content-end"
                        )
                    ])
                ]
            ),
            html.Div(
                dcc.Graph(id='eeg-graph', style={'height': '100%', 'minHeight': '550px'}),
                # Ajustar la altura del gráfico
                style={'height': 'calc(100vh - 250px)'} 
            )
        ]),
        # Módulo derecho
        dbc.Col(width=3, children=[
            dbc.Card([
                    dbc.CardHeader(dbc.Button("¿Qué es esta página?", id={'type': 'button', 'index': 1}, color="Dark", className="w-100")),
                    dbc.Collapse(dbc.CardBody([
                        html.P(["Esta interfaz permite visualizar señales EEG recolectadas con la diadema.", html.Br(), 
                               "Se diseñó para exposiciones y capacitación técnica, priorizando claridad y estética."], className="card-text")
                    ]), id={'type': 'collapse', 'index': 1}, is_open=True)
                ], className="mb-2"),
                dbc.Card([
                    dbc.CardHeader(dbc.Button("¿Cómo usar la interfaz?", id={'type': 'button', 'index': 2}, color="Dark", className="w-100")),
                    dbc.Collapse(dbc.CardBody([
                        html.P(["Ajusta el rango de tiempo. Usa las opciones para cambiar la vista.", html.Br(), 
                               "- En vista única visualizas una señal en específico con opción de filtrar su frecuencia.", html.Br(),
                               "- En vista multicanal visualizas varios canales a la vez y puedes seleccionar que canales mostrar.", html.Br(),
                               "La gráfica se actualiza automáticamente."], className="card-text")
                    ]), id={'type': 'collapse', 'index': 2}, is_open=False)
                ]),
            html.Div([
                dbc.Button("Jardín Mental", href="/jardin", color="primary", className="me-2"),
                dbc.Button("Carrera de Coches", href="/carrera", color="primary")
            ], className="d-flex justify-content-end mt-3")
        ])
    ])
], fluid=True)

# Callbacks para mostrar/ocultar herramientas según el modo de vista
@dash.callback(
    Output('filter-selector-container', 'style'),
    Output('channel-selector-container', 'style'),
    Input('view-mode', 'value')
)
def toggle_tools(view_mode):
    if view_mode == 'única':
        return {'display': 'block'}, {'display': 'none'}
    elif view_mode == 'multi':
        return {'display': 'none'}, {'display': 'block'}
    elif view_mode == 'superpuesta':
        return {'display': 'none'}, {'display': 'block'}
    return {'display': 'none'}, {'display': 'none'}

# Callbacks para la selección de canales
@dash.callback(
    Output('channel-selector', 'value'),
    Input('select-all-channels', 'n_clicks'),
    Input('clear-channels', 'n_clicks'),
    prevent_initial_call=True
)
def update_channel_selection(select_all, clear):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    btn = ctx.triggered[0]['prop_id'].split('.')[0]
    if btn == 'select-all-channels':
        return signal_options
    return []

# Callback para actualizar la gráfica
@dash.callback(
    Output('eeg-graph', 'figure'),
    Input('signal-selector', 'value'),
    Input('time-range-slider', 'value'),
    Input('view-mode', 'value'),
    Input('theme-store', 'data'),
    Input('filter-selector', 'value'),
    Input('channel-selector', 'value')
)
def update_graph(signal_type, time_range, view_mode, theme, filter_band, selected_channels):
    bgcolor = "black" if theme == 'dark' else "white"
    fontcolor = "white" if theme == 'dark' else "black"

    start, end = time_range
    start_idx = int(start * sample_rate)
    end_idx = int(end * sample_rate)

    if view_mode == 'única':
        raw_filtered = raw.copy()
        bands = {
            'delta': (0.5, 4),
            'theta': (4, 8),
            'alpha': (8, 12),
            'beta': (12, 30),
            'gamma': (30, 50)
        }
        if filter_band in bands:
            raw_filtered.filter(*bands[filter_band], fir_design='firwin', verbose='ERROR')

        ch_idx = raw.ch_names.index(signal_type)
        data, times = raw_filtered[ch_idx, start_idx:end_idx]
        times = times.flatten()
        fig = go.Figure(
            data=[go.Scatter(x=times, y=data[0], mode='lines')],
            layout=go.Layout(
                title=f'Señal EEG: {signal_type}',
                xaxis=dict(
                    title='Tiempo (s)',
                    gridcolor='gray',
                    zeroline=True,
                    zerolinecolor=fontcolor,
                    zerolinewidth=1
                ),
                yaxis=dict(
                    title='Amplitud (µV)',
                    gridcolor='gray',
                    zeroline=True,
                    zerolinecolor=fontcolor,
                    zerolinewidth=1
                ),
                font=dict(family="Times New Roman", color=fontcolor),
                height=700,
                paper_bgcolor=bgcolor,
                plot_bgcolor=bgcolor,
                margin=dict(t=40, l=60, r=20, b=60)
            )
        )
        return fig
    elif view_mode == 'multi':
        selected = selected_channels if selected_channels else ['Raw']
        picks = [raw.ch_names.index(ch) for ch in selected]
        data, times = raw[picks, start_idx:end_idx]
        ch_names = selected

        step = 1. / len(ch_names)
        height = max(700, len(ch_names) * 50)
        layout = go.Layout(
            showlegend=False,
            paper_bgcolor=bgcolor,
            plot_bgcolor=bgcolor,
            autosize=False,
            margin=dict(t=40, l=60, r=20, b=40),
            height=height,
            xaxis=dict(
                title='Tiempo (s)', 
                side='top',            
                showgrid=True,
                gridcolor='gray',
                zeroline=False,
                showticklabels=True,
                color=fontcolor  
            )
        ) 
        traces = []
        annotations = []
        times = times.flatten()
        for ii, ch in enumerate(ch_names):
            domain = [1 - (ii + 1) * step, 1 - ii * step]
            axis_id = '' if ii == 0 else str(ii + 1)
            layout[f'yaxis{axis_id}'] = go.layout.YAxis(domain=domain, showticklabels=False, zeroline=False, gridcolor='gray')
            trace = go.Scatter(x=times, y=data[ii], yaxis=f'y{axis_id}', mode='lines')
            traces.append(trace)
            annotations.append(go.layout.Annotation(x=-0.06, y=sum(domain)/2, xref='paper', yref=f'y{axis_id}', text=ch, showarrow=False, font=dict(size=9, color=fontcolor)))

        layout.annotations = annotations
        layout.font = dict(family="Times New Roman", color=fontcolor)
        fig = go.Figure(data=traces, layout=layout)
        return fig
    elif view_mode == 'superpuesta':
        selected = selected_channels if selected_channels else ['Raw']
        picks = [raw.ch_names.index(ch) for ch in selected]
        data, times = raw[picks, start_idx:end_idx]
        times = times.flatten()

        fig = go.Figure()
        for i, ch in enumerate(selected):
            fig.add_trace(go.Scatter(x=times, y=data[i], name=ch, mode='lines'))

        fig.update_layout(
            title="Señales EEG Superpuestas",
            xaxis_title="Tiempo (s)",
            yaxis_title="Amplitud (µV)",
            paper_bgcolor=bgcolor,
            plot_bgcolor=bgcolor,
            font=dict(color=fontcolor),
            height=700
        )
        return fig

# Callback para mostrar/ocultar colapsables
@dash.callback(
    Output({'type': 'collapse', 'index': MATCH}, 'is_open'),
    Input({'type': 'button', 'index': MATCH}, 'n_clicks'),
    State({'type': 'collapse', 'index': MATCH}, 'is_open')
)
def toggle_collapse(n, is_open):
    return not is_open if n else is_open

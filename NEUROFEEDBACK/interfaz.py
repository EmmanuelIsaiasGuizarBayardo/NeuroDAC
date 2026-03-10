# interfaz.py — NEURODAC v4
# Aplicación principal Dash · División Universitaria de Neuroingeniería (DUNNE)
# Ejecutar con: python interfaz.py

import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc

# =============================================================
# Configuración de la aplicación
# =============================================================
app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700"
        "&family=Playfair+Display:ital,wght@0,400;0,600;1,400&display=swap"
    ],
    suppress_callback_exceptions=True,
    title="NEURODAC · DUNNE"
)

# =============================================================
# Layout principal
# =============================================================
app.layout = html.Div([
    # Stores y elementos auxiliares
    dcc.Store(id='theme-store', data='dark'),
    html.Div(id='_theme-dummy', style={'display': 'none'}),

    # --- Navbar ---
    html.Nav(className='neurodac-navbar', children=[
        dbc.Container(fluid=True, children=[
            dbc.Row([
                # Logo y nombre
                dbc.Col(width=3, children=[
                    html.A(
                        className='neurodac-brand', href="/",
                        children=[
                            html.Img(src=app.get_asset_url('LOGO.jpg')),
                            html.Div([
                                html.Span("NEURODAC"),
                                html.Span(
                                    "Demostrador Académico · DUNNE",
                                    className='brand-sub'
                                )
                            ])
                        ]
                    )
                ]),

                # Navegación
                dbc.Col(width=6, children=[
                    dbc.Nav([
                        dbc.NavLink("Visualización EEG", href="/", active="exact"),
                        dbc.NavLink("Tiempo Real", href="/tiempo-real", active="exact"),
                        dbc.NavLink("Jardín Mental", href="/jardin", active="exact"),
                        dbc.NavLink("Carrera Neural", href="/carrera", active="exact"),
                    ], pills=True, className="justify-content-center")
                ]),

                # Toggle de tema (dark/light)
                dbc.Col(width=3, children=[
                    html.Div(className='theme-toggle-wrapper', children=[
                        html.Span("Dark", className='theme-toggle-label'),
                        html.Div(
                            id='theme-toggle-track',
                            className='theme-toggle-track',
                            n_clicks=0,
                            children=[html.Div(className='theme-toggle-knob')]
                        ),
                        html.Span("Light", className='theme-toggle-label'),
                    ])
                ])
            ], align="center")
        ])
    ]),

    # --- Contenido de las páginas ---
    dbc.Container(fluid=True, className="py-3", children=[
        dash.page_container
    ])
])


# =============================================================
# Callbacks
# =============================================================

# Alternar entre tema oscuro y claro al hacer clic en el toggle
@app.callback(
    Output('theme-store', 'data'),
    Output('theme-toggle-track', 'className'),
    Input('theme-toggle-track', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_theme(n):
    if n and n % 2 == 1:
        return 'light', 'theme-toggle-track light'
    return 'dark', 'theme-toggle-track'


# Aplicar el atributo data-theme al elemento <html> para que el CSS responda
app.clientside_callback(
    "function(t){document.documentElement.setAttribute('data-theme',t);return t;}",
    Output('_theme-dummy', 'children'),
    Input('theme-store', 'data')
)


# =============================================================
# Ejecución
# =============================================================
if __name__ == "__main__":
    print("NEURODAC — CTRL + C para detener.")
    app.run(debug=True)

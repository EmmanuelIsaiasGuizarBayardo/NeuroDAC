# interfaz.py 
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc

themes = {'dark': dbc.themes.DARKLY, 'light': dbc.themes.FLATLY}
app = dash.Dash(__name__, use_pages=True, external_stylesheets=[themes['dark']])
app.title = "NEURODAC"

def dropdown_style(theme):
    return {'backgroundColor': 'white', 'color': 'black', 'border': '1px solid #ccc'}

app.layout = html.Div([
    dcc.Store(id='theme-store', data='dark'),
    html.Link(id='theme-link', rel='stylesheet'),
    dbc.Container([
        dbc.Row([
            dbc.Col(dbc.Nav([
                dbc.NavLink("Gráfica", href="/", active="exact"),
                dbc.NavLink("Jardín Mental", href="/jardin", active="exact"),
                dbc.NavLink("Carrera de Coches", href="/carrera", active="exact"),
            ], pills=True), width=9),
            dbc.Col(html.Div([
                html.Span("🌑"),
                dbc.Switch(id='theme-switch', value=False),
                html.Span("🌕", style={"marginLeft": "-8px"})
            ], className="d-flex align-items-center justify-content-end"), width=3)
        ], className="my-2"),
        dash.page_container
    ], fluid=True, style={"fontFamily": "Times New Roman, serif"})
])

@app.callback(Output('theme-link', 'href'), Input('theme-store', 'data'))
def update_theme(theme):
    return themes[theme]

@app.callback(Output('theme-store', 'data'), Input('theme-switch', 'value'))
def toggle_theme(val):
    return 'light' if val else 'dark'

@app.callback(
    Output('signal-selector', 'style'),
    Output('filter-selector', 'style'),
    Output('channel-selector', 'style'),
    Input('theme-store', 'data'),
    prevent_initial_call=True
)
def update_all_dropdown_styles(theme):
    style = dropdown_style(theme)
    return style, style, style

@app.callback(
    Output('signal-selector-jardin', 'style'),
    Output('filter-selector-jardin', 'style'),
    Input('theme-store', 'data'),
    prevent_initial_call=True
)
def update_dropdown_style_jardin(theme):
    style = dropdown_style(theme)
    return style, style

@app.callback(
    Output('signal-selector-c1', 'style'),
    Output('filter-selector-c1', 'style'),
    Output('signal-selector-c2', 'style'),
    Output('filter-selector-c2', 'style'),
    Input('theme-store', 'data'),
    prevent_initial_call=True
)
def update_dropdown_style_carrera(theme):
    style = dropdown_style(theme)
    return style, style, style, style

if __name__ == "__main__":
    print("CTRL + C para detener la aplicación.")
    app.run(debug=True)

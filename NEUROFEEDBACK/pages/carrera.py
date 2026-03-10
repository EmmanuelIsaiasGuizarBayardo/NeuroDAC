# pages/carrera.py — Carrera Neural v3 (vertical layout, theme-responsive)
# Juego de neurofeedback basado en atención.
# La señal 'attention' de NeuroSky controla la velocidad del coche.
# Reimplementado en HTML5 Canvas (originalmente Pygame).

import os
import sys
import time
import threading
from collections import deque

import dash
from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objs as go

# Agregar directorio raíz al path para importar módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from modules.neurosky_data_collector import NeuroSkyDataCollector, validate_signal_type

LIVE_DATA_BUFFER_C1 = deque()
COLLECTOR_C1 = None
THREAD_C1 = None
LIVE_DATA_BUFFER_C2 = deque()
COLLECTOR_C2 = None
THREAD_C2 = None
dash.register_page(__name__, path="/carrera")

SIGS = [
    'raw',
    'attention',
    'meditation',
    'blink',
    'delta',
    'theta',
    'low-alpha',
    'high-alpha',
    'low-beta',
    'high-beta',
    'low-gamma',
    'mid-gamma']


def gc(theme):
    if theme == 'dark':
        return {'bg': '#222', 'paper': '#222', 'font': '#fff',
                'grid': 'rgba(255,255,255,0.08)', 'zero': 'rgba(255,255,255,0.2)', 'trace': '#4DA8DA'}
    return {'bg': '#fff', 'paper': '#fff', 'font': '#212529',
            'grid': 'rgba(0,0,0,0.06)', 'zero': 'rgba(0,0,0,0.15)', 'trace': '#375a7f'}


def empty_fig(st, theme, title="Esperando..."):
    c = gc(theme)
    yr = [0, 100] if st in ['attention', 'meditation'] else (
        [-2048, 2048] if st == 'raw' else None)
    return go.Figure(data=[go.Scatter(y=[], mode='lines', line=dict(color=c['trace'], width=1.5))],
                     layout=go.Layout(title=dict(text=title, font=dict(size=11)),
                                      xaxis=dict(title='Tiempo (s)', gridcolor=c['grid']),
                                      yaxis=dict(
                         title='Amplitud', range=yr, gridcolor=c['grid']),
        paper_bgcolor=c['paper'], plot_bgcolor=c['bg'],
        font=dict(family="Outfit", color=c['font'], size=10), margin=dict(t=30, l=40, r=15, b=30)))


def collect_buf(ci, buf):
    while ci.running:
        try:
            buf.append(ci.get_signal_value(ci.signal_type))
            time.sleep(1.0 / ci.sample_freq)
        except BaseException:
            pass


RACE_HTML = """<!DOCTYPE html><html><head><style>
*{margin:0;padding:0;box-sizing:border-box}
body{overflow:hidden;font-family:'Outfit',sans-serif}
canvas{display:block}
#hud{position:absolute;top:8px;left:8px;right:8px;display:flex;justify-content:space-between;pointer-events:none;z-index:10}
.hi{background:rgba(0,0,0,0.5);backdrop-filter:blur(5px);color:#eee;padding:3px 10px;border-radius:5px;font-size:11px;font-weight:500}
.hi .v{color:#4DA8DA;font-weight:600}.hi .v.w{color:#e74c3c}
#msg{position:absolute;bottom:10px;left:0;right:0;text-align:center;color:rgba(128,128,128,0.5);font-size:10px;z-index:10}
</style></head><body>
<div id="hud">
<div class="hi">Dist <span class="v" id="hd">0m</span></div>
<div class="hi">Atención <span class="v" id="ha">50</span></div>
<div class="hi">Vel <span class="v" id="hv">5.0</span></div>
<div class="hi">Ghost <span class="v" id="hg">0m</span></div>
</div>
<div id="msg">←→ mover · W/S simular atención · Conecta diadema para BCI</div>
<canvas id="c"></canvas>
<script>
var canvas=document.getElementById('c'),ctx=canvas.getContext('2d'),W,H;
var isDark=true;
function resize(){W=canvas.width=window.innerWidth;H=canvas.height=window.innerHeight}
resize();window.addEventListener('resize',resize);

var LC=3,BS=5,AT=50,AS=5,MNA=0,MXA=200,PPM=20,PL=3,PR=1,UT=35,LT=25,CS=2;
var sig=50,att=50,dist=0,lod=0,obs=[],cp=0,pl=1,gd=0,gs=BS+40,lt=0,ro=0;

function lw(){return W/LC}
function lc(l){return l*lw()+lw()/2}
function cw(){return W/7}
function ch(){return W/6}

function spawn(){obs.push({lane:Math.floor(Math.random()*LC),y:-ch(),type:Math.floor(Math.random()*3)})}

function roadBg(){return isDark?'#1e1e1e':'#e0e0e0'}
function roadSurf(){return isDark?'#2a2a2a':'#d0d0d0'}
function laneColor(){return isDark?'rgba(255,255,255,0.12)':'rgba(0,0,0,0.1)'}
function sideColor(){return isDark?'rgba(77,168,218,0.3)':'rgba(77,168,218,0.4)'}

function drawRoad(){
    ctx.fillStyle=roadBg();ctx.fillRect(0,0,W,H);
    ctx.fillStyle=roadSurf();ctx.fillRect(0,0,W,H);
    ctx.strokeStyle=laneColor();ctx.lineWidth=2;ctx.setLineDash([30,20]);
    for(var i=1;i<LC;i++){var x=i*lw();ctx.beginPath();ctx.moveTo(x,-50+(ro%50));ctx.lineTo(x,H+50);ctx.stroke()}
    ctx.setLineDash([]);
    ctx.strokeStyle=sideColor();ctx.lineWidth=3;
    ctx.beginPath();ctx.moveTo(2,0);ctx.lineTo(2,H);ctx.stroke();
    ctx.beginPath();ctx.moveTo(W-2,0);ctx.lineTo(W-2,H);ctx.stroke();
}

function drawCar(x,y,col,ghost){
    var w=cw(),h=ch(),cx=x-w/2;
    if(ghost)ctx.globalAlpha=0.25;
    ctx.fillStyle=col;ctx.beginPath();
    if(ctx.roundRect)ctx.roundRect(cx+w*0.15,y,w*0.7,h,8);
    else ctx.rect(cx+w*0.15,y,w*0.7,h);
    ctx.fill();
    ctx.fillStyle=ghost?'rgba(100,100,100,0.5)':'rgba(77,168,218,0.4)';
    ctx.beginPath();
    if(ctx.roundRect)ctx.roundRect(cx+w*0.22,y+h*0.15,w*0.56,h*0.2,4);
    else ctx.rect(cx+w*0.22,y+h*0.15,w*0.56,h*0.2);
    ctx.fill();
    ctx.fillStyle='#111';
    ctx.fillRect(cx+w*0.05,y+h*0.05,w*0.12,h*0.18);
    ctx.fillRect(cx+w*0.83,y+h*0.05,w*0.12,h*0.18);
    ctx.fillRect(cx+w*0.05,y+h*0.72,w*0.12,h*0.18);
    ctx.fillRect(cx+w*0.83,y+h*0.72,w*0.12,h*0.18);
    if(!ghost){ctx.fillStyle='#ff3333';ctx.beginPath();
        ctx.arc(cx+w*0.25,y+h*0.92,3,0,6.28);ctx.arc(cx+w*0.75,y+h*0.92,3,0,6.28);ctx.fill()}
    ctx.globalAlpha=1;
}

function drawObs(o){
    var w=cw()*0.85,h=ch()*0.7,cx=lc(o.lane)-w/2;
    var cols=['#e74c3c','#ff8c00','#9b59b6'];
    ctx.fillStyle=cols[o.type%3];ctx.beginPath();
    if(ctx.roundRect)ctx.roundRect(cx,o.y,w,h,6);else ctx.rect(cx,o.y,w,h);
    ctx.fill();
    ctx.strokeStyle='rgba(255,255,255,0.3)';ctx.lineWidth=2;ctx.beginPath();
    ctx.moveTo(cx+6,o.y+6);ctx.lineTo(cx+w-6,o.y+h-6);
    ctx.moveTo(cx+w-6,o.y+6);ctx.lineTo(cx+6,o.y+h-6);ctx.stroke();
}

function loop(ts){
    if(!lt)lt=ts;var dt=Math.min((ts-lt)/1000,0.05);lt=ts;
    if(sig>UT)att=Math.min(MXA,att+CS);else if(sig<LT)att=Math.max(MNA,att-CS);
    var es=Math.max(0,att*0.5-AT),spd=BS+es-cp;
    cp=Math.max(0,cp-PR*dt);dist+=spd*dt;gd+=gs*dt;ro+=spd*PPM*dt;
    if(dist-lod>=10){spawn();lod=dist}
    for(var i=obs.length-1;i>=0;i--){var o=obs[i];o.y+=spd*PPM*dt;
        if(o.lane===pl&&Math.abs(o.y-(H-ch()-10))<ch()*0.7){cp+=PL;obs.splice(i,1);continue}
        if(o.y>H+50)obs.splice(i,1)}
    drawRoad();
    drawCar(lc(1),H-ch()-20-(gd-dist)*PPM,'#555',true);
    for(var i=0;i<obs.length;i++)drawObs(obs[i]);
    drawCar(lc(pl),H-ch()-10,'#4DA8DA',false);
    document.getElementById('hd').textContent=dist.toFixed(0)+'m';
    document.getElementById('ha').textContent=att;
    document.getElementById('hv').textContent=spd.toFixed(1);
    var df=(gd-dist).toFixed(0),ge=document.getElementById('hg');
    ge.textContent=(df>0?'+':'')+df+'m';ge.className=df>0?'v w':'v';
    requestAnimationFrame(loop);
}

document.addEventListener('keydown',function(e){
    if(e.key==='ArrowLeft')pl=Math.max(0,pl-1);
    if(e.key==='ArrowRight')pl=Math.min(LC-1,pl+1);
    if(e.key==='w'||e.key==='W')att=Math.min(MXA,att+AS);
    if(e.key==='s'||e.key==='S')att=Math.max(MNA,att-AS);
});
// Auto-focus on click so keyboard works inside iframe
document.addEventListener('click', function(){ window.focus(); });
window.addEventListener('message',function(e){
    if(e.data&&typeof e.data.signalValue==='number')sig=e.data.signalValue;
    if(e.data&&typeof e.data.theme==='string')isDark=e.data.theme==='dark';
    if(e.data&&e.data.keydown){
        var k=e.data.keydown;
        if(k==='ArrowLeft')pl=Math.max(0,pl-1);
        if(k==='ArrowRight')pl=Math.min(LC-1,pl+1);
        if(k==='w'||k==='W')att=Math.min(MXA,att+AS);
        if(k==='s'||k==='S')att=Math.max(MNA,att-AS);
    }
});
requestAnimationFrame(loop);
</script></body></html>"""

# Layout: game tall on left, controls stacked on right
layout = html.Div(className='page-content', children=[
    html.H2("Carrera Neural", className="section-title"),
    dbc.Row([
        # Game (tall, left)
        dbc.Col(width=5, children=[
            html.Div(className="game-canvas-container", style={"height": "78vh"}, children=[
                html.Iframe(id='carrera-game-iframe', srcDoc=RACE_HTML,
                            style={"width": "100%", "height": "100%", "border": "none", "borderRadius": "10px"})
            ]),
        ]),
        # Controls (right, stacked)
        dbc.Col(width=7, children=[
            html.Div(className="edu-panel mb-2", children=[
                html.H6("¿Cómo funciona?"),
                html.P(["La Carrera Neural es un ejercicio de ", html.Em("neurofeedback"),
                        " basado en atención. La señal 'attention' controla la velocidad: mayor concentración = más velocidad. "
                        "← → para esquivar obstáculos. W/S para simular sin diadema."],
                       style={"fontSize": "0.85rem"})
            ]),
            dbc.Row([
                dbc.Col(width=6, children=[
                    dbc.Card(className="mb-2", children=[
                        dbc.CardHeader("Jugador 1 (Control)"),
                        dbc.CardBody([
                            dbc.Label("Puerto:", style={"fontSize": "0.78rem"}),
                            dbc.Input(
                                id="rt-com-port-c1",
                                placeholder="COM3",
                                type="text",
                                size="sm",
                                className="mb-1"),
                            dbc.Label("Señal:", style={"fontSize": "0.78rem"}),
                            dcc.Dropdown(id="rt-signal-type-c1",
                                         options=[{'label': s.capitalize(), 'value': s}
                                                  for s in SIGS],
                                         value='attention', clearable=False, className='mb-2'),
                            dbc.Row([
                                dbc.Col(
                                    dbc.Button(
                                        "Conectar",
                                        id="rt-connect-c1",
                                        className="btn-nd-primary w-100",
                                        size="sm"),
                                    width=6),
                                dbc.Col(
                                    dbc.Button(
                                        "Detener",
                                        id="rt-stop-c1",
                                        className="btn-nd-danger w-100",
                                        size="sm"),
                                    width=6),
                            ]),
                            html.Div(id="rt-status-c1", className="mt-1"),
                            html.Div(className="graph-container mt-1", children=[
                                dcc.Graph(id='rt-graph-c1', style={'height': '180px'})]),
                        ])
                    ])
                ]),
                dbc.Col(width=6, children=[
                    dbc.Card(className="mb-2", children=[
                        dbc.CardHeader("Jugador 2 (Comparación)"),
                        dbc.CardBody([
                            dbc.Label("Puerto:", style={"fontSize": "0.78rem"}),
                            dbc.Input(
                                id="rt-com-port-c2",
                                placeholder="COM4",
                                type="text",
                                size="sm",
                                className="mb-1"),
                            dbc.Label("Señal:", style={"fontSize": "0.78rem"}),
                            dcc.Dropdown(id="rt-signal-type-c2",
                                         options=[{'label': s.capitalize(), 'value': s}
                                                  for s in SIGS],
                                         value='attention', clearable=False, className='mb-2'),
                            dbc.Row([
                                dbc.Col(
                                    dbc.Button(
                                        "Conectar",
                                        id="rt-connect-c2",
                                        className="btn-nd-primary w-100",
                                        size="sm"),
                                    width=6),
                                dbc.Col(
                                    dbc.Button(
                                        "Detener",
                                        id="rt-stop-c2",
                                        className="btn-nd-danger w-100",
                                        size="sm"),
                                    width=6),
                            ]),
                            html.Div(id="rt-status-c2", className="mt-1"),
                            html.Div(className="graph-container mt-1", children=[
                                dcc.Graph(id='rt-graph-c2', style={'height': '180px'})]),
                        ])
                    ])
                ]),
            ]),
            html.Div(className="text-center", children=[
                html.Span(
                    "J1 Señal: ",
                    style={
                        "fontSize": "0.8rem",
                        "color": "var(--nd-text-muted)"}),
                html.Span("--", id='carrera-signal-value',
                          style={"fontSize": "1.1rem", "fontWeight": "600", "color": "var(--nd-accent-blue)"})
            ]),
            # Neuron decoration (right side)
            html.Div(className='neuron-decoration', style={"height": "140px"}),
        ])
    ]),
    dcc.Interval(id='rt-interval-c1', interval=100, disabled=True),
    dcc.Interval(id='rt-interval-c2', interval=100, disabled=True),
    dcc.Store(id='carrera-signal-store', data=50)
])

# --- Callbacks J1 ---


@dash.callback(Output('rt-status-c1', 'children'), Output('rt-interval-c1', 'disabled'), Output('rt-graph-c1', 'figure'),
               Input('rt-connect-c1', 'n_clicks'), Input('rt-stop-c1', 'n_clicks'),
               State('rt-com-port-c1', 'value'), State('rt-signal-type-c1', 'value'), State('theme-store', 'data'), prevent_initial_call=True)
def m_c1(cc, sc, port, st, theme):
    global COLLECTOR_C1, THREAD_C1
    tid = dash.ctx.triggered_id
    if tid == 'rt-connect-c1':
        if not port:
            return html.Span(
                "Puerto.", className="status-badge disconnected"), True, empty_fig(st, theme, "Puerto")
        try:
            validate_signal_type(st)
        except ValueError as e:
            return html.Span(
                str(e), className="status-badge disconnected"), True, empty_fig(st, theme, "Error")
        if COLLECTOR_C1 and COLLECTOR_C1.running:
            COLLECTOR_C1.stop()
            if THREAD_C1 and THREAD_C1.is_alive():
                THREAD_C1.join()
        LIVE_DATA_BUFFER_C1.clear()
        try:
            COLLECTOR_C1 = NeuroSkyDataCollector(port=port, signal_type=st, save_to_csv=False)
            COLLECTOR_C1.connect()
            COLLECTOR_C1.running = True
            THREAD_C1 = threading.Thread(
                target=collect_buf, args=(
                    COLLECTOR_C1, LIVE_DATA_BUFFER_C1), daemon=True)
            THREAD_C1.start()
            return html.Span([html.Span(
                className="dot"), f" {port}"], className="status-badge connected"), False, empty_fig(st, theme, f"J1: {st}")
        except Exception as e:
            if COLLECTOR_C1:
                COLLECTOR_C1.running = False
            return html.Span(
                f"Error: {e}", className="status-badge disconnected"), True, empty_fig(st, theme, "Error")
    elif tid == 'rt-stop-c1':
        if COLLECTOR_C1 and COLLECTOR_C1.running:
            COLLECTOR_C1.stop()
            if THREAD_C1 and THREAD_C1.is_alive():
                THREAD_C1.join()
            LIVE_DATA_BUFFER_C1.clear()
            return html.Span(
                "Stop.", className="status-badge disconnected"), True, empty_fig(st, theme, "J1: Stop")
        return html.Span(
            "Sin conexión.", className="status-badge disconnected"), True, no_update
    return no_update, no_update, no_update


@dash.callback(Output('rt-graph-c1', 'extendData'), Output('carrera-signal-store', 'data'), Output('carrera-signal-value', 'children'),
               Input('rt-interval-c1', 'n_intervals'), prevent_initial_call=True)
def u_c1(n):
    pts = []
    while True:
        try:
            pts.append(LIVE_DATA_BUFFER_C1.popleft())
        except BaseException:
            break
    if not pts:
        return no_update, no_update, no_update
    return ({'y': [pts]}, [0], 512), int(pts[-1]), str(int(pts[-1]))

# --- Callbacks J2 ---


@dash.callback(Output('rt-status-c2', 'children'), Output('rt-interval-c2', 'disabled'), Output('rt-graph-c2', 'figure'),
               Input('rt-connect-c2', 'n_clicks'), Input('rt-stop-c2', 'n_clicks'),
               State('rt-com-port-c2', 'value'), State('rt-signal-type-c2', 'value'), State('theme-store', 'data'), prevent_initial_call=True)
def m_c2(cc, sc, port, st, theme):
    global COLLECTOR_C2, THREAD_C2
    tid = dash.ctx.triggered_id
    if tid == 'rt-connect-c2':
        if not port:
            return html.Span(
                "Puerto.", className="status-badge disconnected"), True, empty_fig(st, theme, "Puerto")
        try:
            validate_signal_type(st)
        except ValueError as e:
            return html.Span(
                str(e), className="status-badge disconnected"), True, empty_fig(st, theme, "Error")
        if COLLECTOR_C2 and COLLECTOR_C2.running:
            COLLECTOR_C2.stop()
            if THREAD_C2 and THREAD_C2.is_alive():
                THREAD_C2.join()
        LIVE_DATA_BUFFER_C2.clear()
        try:
            COLLECTOR_C2 = NeuroSkyDataCollector(port=port, signal_type=st, save_to_csv=False)
            COLLECTOR_C2.connect()
            COLLECTOR_C2.running = True
            THREAD_C2 = threading.Thread(
                target=collect_buf, args=(
                    COLLECTOR_C2, LIVE_DATA_BUFFER_C2), daemon=True)
            THREAD_C2.start()
            return html.Span([html.Span(
                className="dot"), f" {port}"], className="status-badge connected"), False, empty_fig(st, theme, f"J2: {st}")
        except Exception as e:
            if COLLECTOR_C2:
                COLLECTOR_C2.running = False
            return html.Span(
                f"Error: {e}", className="status-badge disconnected"), True, empty_fig(st, theme, "Error")
    elif tid == 'rt-stop-c2':
        if COLLECTOR_C2 and COLLECTOR_C2.running:
            COLLECTOR_C2.stop()
            if THREAD_C2 and THREAD_C2.is_alive():
                THREAD_C2.join()
            LIVE_DATA_BUFFER_C2.clear()
            return html.Span(
                "Stop.", className="status-badge disconnected"), True, empty_fig(st, theme, "J2: Stop")
        return html.Span(
            "Sin conexión.", className="status-badge disconnected"), True, no_update
    return no_update, no_update, no_update


@dash.callback(Output('rt-graph-c2', 'extendData'),
               Input('rt-interval-c2', 'n_intervals'), prevent_initial_call=True)
def u_c2(n):
    pts = []
    while True:
        try:
            pts.append(LIVE_DATA_BUFFER_C2.popleft())
        except BaseException:
            break
    if not pts:
        return no_update
    return ({'y': [pts]}, [0], 512)


# Send signal + theme to iframe, and forward keyboard events
dash.clientside_callback(
    """function(sv, theme) {
        var f = document.getElementById('carrera-game-iframe');
        if(f&&f.contentWindow)f.contentWindow.postMessage({signalValue:sv, theme:theme},'*');
        // Setup keyboard forwarding (once)
        if(!window._carreraKbInit){
            window._carreraKbInit=true;
            document.addEventListener('keydown',function(e){
                var f2=document.getElementById('carrera-game-iframe');
                if(f2&&f2.contentWindow){
                    f2.contentWindow.postMessage({keydown:e.key},'*');
                }
            });
        }
        return '';}""",
    Output('carrera-game-iframe', 'title'),
    Input('carrera-signal-store', 'data'),
    Input('theme-store', 'data')
)

# pages/jardin.py — Jardín Mental v3 (theme-responsive)
# Juego de neurofeedback basado en meditación.
# La señal 'meditation' de NeuroSky controla el crecimiento de flores.
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

LIVE_DATA_BUFFER_JARDIN = deque()
COLLECTOR_JARDIN = None
THREAD_JARDIN = None
dash.register_page(__name__, path="/jardin")

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


def empty_fig(st, theme, title="Esperando datos..."):
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
        except Exception as e:
            if ci.running:
                print(f"Error (Jardín): {e}")


# Game HTML with theme support
GAME_HTML = """<!DOCTYPE html><html><head><style>
*{margin:0;padding:0;box-sizing:border-box}
body{overflow:hidden;font-family:'Outfit',sans-serif}
canvas{display:block}
#hud{position:absolute;top:10px;left:0;right:0;display:flex;justify-content:center;gap:16px;pointer-events:none;z-index:10}
.hi{background:rgba(0,0,0,0.45);backdrop-filter:blur(5px);color:#eee;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:500}
.hi .v{color:#4DA8DA;font-weight:600}
#hbar-bg{position:absolute;top:42px;left:50%;transform:translateX(-50%);width:260px;height:8px;background:rgba(128,128,128,0.3);border-radius:4px;overflow:hidden;z-index:10}
#hbar{height:100%;width:50%;background:linear-gradient(90deg,#4DA8DA,#00bc8c);border-radius:4px;transition:width 0.3s}
#msg{position:absolute;bottom:12px;left:0;right:0;text-align:center;color:rgba(128,128,128,0.6);font-size:11px;z-index:10}
</style></head><body>
<div id="hud">
<div class="hi">Flor <span class="v" id="hf">1/5</span></div>
<div class="hi">Meditación <span class="v" id="hm">50</span></div>
<div class="hi">Etapa <span class="v" id="hs">0/6</span></div>
</div>
<div id="hbar-bg"><div id="hbar"></div></div>
<div id="msg">↑↓ para probar sin diadema · Conecta la diadema en el panel derecho</div>
<canvas id="c"></canvas>
<script>
var canvas=document.getElementById('c'),ctx=canvas.getContext('2d'),W,H;
var isDark=true;
function resize(){W=canvas.width=window.innerWidth;H=canvas.height=window.innerHeight}
resize();window.addEventListener('resize',resize);

var ST=6,MS=150,MF=5,UT=55,LT=45,CS=1;
var PAL=[
{stem:'#55351d',bud:'#ff6347',petal:'#ffb6c1',center:'#ff69b4'},
{stem:'#3c2a14',bud:'#90ee90',petal:'#32cd32',center:'#228b22'},
{stem:'#503214',bud:'#87ceeb',petal:'#87cefa',center:'#4682b4'},
{stem:'#5a3c1e',bud:'#eee8aa',petal:'#eedd82',center:'#cd853f'},
{stem:'#462814',bud:'#dda0dd',petal:'#ee82ee',center:'#c71585'}
];
var sig=50,flowers=[],comp=[],cur=0,gt=0;

function mkF(x,gy,p){return{x:x,gy:gy,att:50,th:60,hp:50,st:0,tk:0,pal:p}}
function initG(){
    var m=80,gy=H*0.65,ps=[];
    for(var i=0;i<MF;i++)ps.push(m+(W-2*m)*(i+0.5)/MF+(Math.random()-0.5)*40);
    flowers=ps.map(function(x,i){return mkF(x,gy,PAL[i%PAL.length])});
    comp=[];cur=0;
}

function bgColor(){return isDark?'#0d1117':'#f0f2f5'}
function groundColors(){return isDark?['#1a2a1a','#0d1117']:['#c8dcc8','#f0f2f5']}

function drawGround(){
    var gy=H*0.65+20,gc=groundColors();
    var g=ctx.createLinearGradient(0,gy,0,H);
    g.addColorStop(0,gc[0]);g.addColorStop(1,gc[1]);
    ctx.fillStyle=g;ctx.beginPath();ctx.moveTo(0,gy);
    for(var x=0;x<=W;x+=50)ctx.lineTo(x,gy+Math.sin(x*0.01+1)*8);
    ctx.lineTo(W,H);ctx.lineTo(0,H);ctx.closePath();ctx.fill();
}

function drawLeaf(x,y,a,col,t){
    ctx.save();ctx.translate(x,y);ctx.rotate(a+0.1*Math.sin(t/800));
    ctx.beginPath();ctx.ellipse(0,0,12,5,0,0,Math.PI*2);
    ctx.fillStyle=col;ctx.globalAlpha=0.6;ctx.fill();ctx.globalAlpha=1;ctx.restore();
}

function drawF(f,active){
    var x=f.x,gy=f.gy,s=f.st,p=f.pal,t=gt;
    var sh=Math.floor((s/ST)*MS);
    if(s>0){ctx.lineWidth=4;ctx.strokeStyle=p.stem;ctx.beginPath();
        for(var i=0;i<sh;i+=3){var o=4*Math.sin(i/15+t/1000),px=x+o,py=gy-i;
        if(i===0)ctx.moveTo(px,py);else ctx.lineTo(px,py)}ctx.stroke();
        if(s>=2){drawLeaf(x-15,gy-sh*0.4,-0.3,p.bud,t);drawLeaf(x+15,gy-sh*0.4+10,0.3,p.bud,t)}}
    if(s===0){var r=6+2*Math.sin(t/300);ctx.beginPath();ctx.arc(x,gy,r,0,Math.PI*2);
        ctx.fillStyle=p.stem;ctx.fill();
        if(active){ctx.beginPath();ctx.arc(x,gy,r+4,0,Math.PI*2);ctx.fillStyle='rgba(77,168,218,0.2)';ctx.fill()}return}
    var tx=x+2*Math.sin(t/800),ty=(gy-sh)+2*Math.cos(t/800);
    if(s>=1&&s<3){var sz=8+s*3+2*Math.sin(t/400);ctx.beginPath();ctx.ellipse(tx,ty,sz*0.7,sz,0,0,Math.PI*2);ctx.fillStyle=p.bud;ctx.fill()}
    if(s>=3&&s<ST){var pc=(s-2)*3,sz2=8+s*2;
        for(var i=0;i<pc;i++){var a=(i*2*Math.PI/pc)+t/1200,pr=sz2+10;
        ctx.beginPath();ctx.arc(tx+pr*Math.cos(a),ty+pr*Math.sin(a),8+2*Math.sin(t/500+i),0,Math.PI*2);
        ctx.fillStyle=p.petal;ctx.globalAlpha=0.75;ctx.fill();ctx.globalAlpha=1}
        ctx.beginPath();ctx.arc(tx,ty,6,0,Math.PI*2);ctx.fillStyle=p.center;ctx.fill()}
    if(s>=ST){var tp=ST+4,sz3=14;
        for(var i=0;i<tp;i++){var a=(i*2*Math.PI/tp)+t/1000,pr=sz3+12;
        ctx.beginPath();ctx.arc(tx+pr*Math.cos(a),ty+pr*Math.sin(a),10+3*Math.sin(t/400+i),0,Math.PI*2);
        ctx.fillStyle=p.petal;ctx.globalAlpha=0.7;ctx.fill();ctx.globalAlpha=1}
        ctx.beginPath();ctx.arc(tx,ty,8+2*Math.sin(t/300),0,Math.PI*2);ctx.fillStyle=p.center;ctx.fill();
        for(var i=0;i<3;i++){var sx=tx+25*Math.cos(t/600+i*2.1),sy=ty-20+15*Math.sin(t/500+i*1.7);
        ctx.beginPath();ctx.arc(sx,sy,2,0,Math.PI*2);ctx.fillStyle='rgba(255,255,255,'+(0.3+0.3*Math.sin(t/300+i))+')';ctx.fill()}}
}

function update(){
    if(!flowers.length)return;var f=flowers[cur];
    if(sig>UT)f.att=Math.min(100,f.att+CS);else if(sig<LT)f.att=Math.max(0,f.att-CS);
    f.tk++;if(f.tk>=60){f.tk=0;
        if(f.att>=f.th&&f.st<ST){f.st++;f.hp=Math.min(100,f.hp+3)}
        else if(f.att<f.th&&f.st>0){f.hp=Math.max(0,f.hp-3);f.st=Math.max(0,f.st-1)}
        else{var d=f.att>=f.th?7:-3;f.hp=Math.max(0,Math.min(100,f.hp+d))}}
    if(f.hp<=0){initG();return}
    if(f.st>=ST){comp.push(Object.assign({},f));var nx=cur+1;
        if(nx<flowers.length){flowers[nx].hp=f.hp;cur=nx}else initG()}
}

function draw(){
    ctx.fillStyle=bgColor();ctx.fillRect(0,0,W,H);
    drawGround();
    for(var i=0;i<comp.length;i++)drawF(comp[i],false);
    if(flowers.length>0&&cur<flowers.length)drawF(flowers[cur],true);
    var f=flowers[cur]||{hp:50,att:50,st:0};
    document.getElementById('hf').textContent=(cur+1)+'/'+MF;
    document.getElementById('hm').textContent=f.att;
    document.getElementById('hs').textContent=f.st+'/'+ST;
    document.getElementById('hbar').style.width=f.hp+'%';
}

function loop(){gt=performance.now();update();draw();requestAnimationFrame(loop)}

window.addEventListener('message',function(e){
    if(e.data&&typeof e.data.signalValue==='number')sig=e.data.signalValue;
    if(e.data&&typeof e.data.theme==='string')isDark=e.data.theme==='dark';
    if(e.data&&e.data.keydown){
        if(e.data.keydown==='ArrowUp')sig=Math.min(100,sig+10);
        if(e.data.keydown==='ArrowDown')sig=Math.max(0,sig-10);
    }
});
document.addEventListener('keydown',function(e){
    if(e.key==='ArrowUp')sig=Math.min(100,sig+10);
    if(e.key==='ArrowDown')sig=Math.max(0,sig-10);
});
initG();loop();
</script></body></html>"""

layout = html.Div(className='page-content', children=[
    html.H2("Jardín Mental", className="section-title"),
    dbc.Row([
        dbc.Col(width=7, children=[
            html.Div(className="game-canvas-container", style={"height": "65vh"}, children=[
                html.Iframe(id='jardin-game-iframe', srcDoc=GAME_HTML,
                            style={"width": "100%", "height": "100%", "border": "none", "borderRadius": "10px"})
            ]),
            html.Div(className="edu-panel mt-2", children=[
                html.H6("¿Cómo funciona?"),
                html.P(["El Jardín Mental es un ejercicio de ", html.Em("neurofeedback"),
                        " basado en meditación. La señal de 'meditation' controla el crecimiento de las flores: "
                        "cuando supera el umbral (>55) crecen; cuando baja (<45) decrecen. "
                        "También puedes usar ↑/↓ para probar sin diadema."],
                       style={"fontSize": "0.88rem"})])
        ]),
        dbc.Col(width=5, children=[
            dbc.Card(className="mb-3", children=[dbc.CardBody([
                dbc.Label("Puerto:", style={"fontSize": "0.8rem", "fontWeight": "500"}),
                dbc.Input(
                    id="rt-com-port-jardin",
                    placeholder="COM3",
                    type="text",
                    className="mb-2"),
                dbc.Label("Señal:", style={"fontSize": "0.8rem", "fontWeight": "500"}),
                dcc.Dropdown(id="rt-signal-type-jardin",
                             options=[{'label': s.capitalize(), 'value': s} for s in SIGS],
                             value='meditation', clearable=False, className='mb-3'),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            "Conectar",
                            id="rt-connect-jardin",
                            className="btn-nd-primary w-100"),
                        width=6),
                    dbc.Col(
                        dbc.Button(
                            "Detener",
                            id="rt-stop-jardin",
                            className="btn-nd-danger w-100"),
                        width=6),
                ]),
                html.Div(id="rt-status-jardin", className="mt-2"),
            ])]),
            html.Div(className="graph-container", children=[
                dcc.Graph(id='rt-graph-jardin', style={'height': '280px'})
            ]),
            html.Div(className="text-center mt-2", children=[
                html.Span(
                    "Señal: ",
                    style={
                        "fontSize": "0.8rem",
                        "color": "var(--nd-text-muted)"}),
                html.Span("--", id='jardin-signal-value',
                          style={"fontSize": "1.1rem", "fontWeight": "600", "color": "var(--nd-accent-blue)"})
            ]),
            # Neuron decoration (right side, next to signal graph)
            html.Div(className='neuron-decoration', style={"height": "160px"}),
        ])
    ]),
    dcc.Interval(id='rt-interval-jardin', interval=100, n_intervals=0, disabled=True),
    dcc.Store(id='jardin-signal-store', data=50)
])


@dash.callback(Output('rt-status-jardin', 'children'), Output('rt-interval-jardin', 'disabled'),
               Output('rt-graph-jardin', 'figure'),
               Input('rt-connect-jardin', 'n_clicks'), Input('rt-stop-jardin', 'n_clicks'),
               State('rt-com-port-jardin', 'value'), State('rt-signal-type-jardin',
                                                           'value'), State('theme-store', 'data'),
               prevent_initial_call=True)
def manage_j(cc, sc, port, st, theme):
    global COLLECTOR_JARDIN, THREAD_JARDIN
    tid = dash.ctx.triggered_id
    if tid == 'rt-connect-jardin':
        if not port:
            return html.Span(
                "Puerto requerido.", className="status-badge disconnected"), True, empty_fig(st, theme, "Puerto requerido")
        try:
            validate_signal_type(st)
        except ValueError as e:
            return html.Span(
                str(e), className="status-badge disconnected"), True, empty_fig(st, theme, "Error")
        if COLLECTOR_JARDIN and COLLECTOR_JARDIN.running:
            COLLECTOR_JARDIN.stop()
            if THREAD_JARDIN and THREAD_JARDIN.is_alive():
                THREAD_JARDIN.join()
        LIVE_DATA_BUFFER_JARDIN.clear()
        try:
            COLLECTOR_JARDIN = NeuroSkyDataCollector(
                port=port, signal_type=st, save_to_csv=False)
            COLLECTOR_JARDIN.connect()
            COLLECTOR_JARDIN.running = True
            THREAD_JARDIN = threading.Thread(target=collect_buf, args=(
                COLLECTOR_JARDIN, LIVE_DATA_BUFFER_JARDIN), daemon=True)
            THREAD_JARDIN.start()
            return html.Span([html.Span(
                className="dot"), f" {port}"], className="status-badge connected"), False, empty_fig(st, theme, st.capitalize())
        except Exception as e:
            if COLLECTOR_JARDIN:
                COLLECTOR_JARDIN.running = False
            return html.Span(
                f"Error: {e}", className="status-badge disconnected"), True, empty_fig(st, theme, f"Error")
    elif tid == 'rt-stop-jardin':
        if COLLECTOR_JARDIN and COLLECTOR_JARDIN.running:
            COLLECTOR_JARDIN.stop()
            if THREAD_JARDIN and THREAD_JARDIN.is_alive():
                THREAD_JARDIN.join()
            LIVE_DATA_BUFFER_JARDIN.clear()
            return html.Span(
                "Detenido.", className="status-badge disconnected"), True, empty_fig(st, theme, "Detenido")
        return html.Span(
            "Sin conexión.", className="status-badge disconnected"), True, no_update
    return no_update, no_update, no_update


@dash.callback(Output('rt-graph-jardin', 'extendData'), Output('jardin-signal-store', 'data'),
               Output('jardin-signal-value', 'children'),
               Input('rt-interval-jardin', 'n_intervals'), prevent_initial_call=True)
def upd_j(n):
    pts = []
    while True:
        try:
            pts.append(LIVE_DATA_BUFFER_JARDIN.popleft())
        except IndexError:
            break
    if not pts:
        return no_update, no_update, no_update
    lat = int(pts[-1])
    return ({'y': [pts]}, [0], 512), lat, str(lat)


# Send signal + theme to iframe
dash.clientside_callback(
    """function(sv, theme) {
        var f = document.getElementById('jardin-game-iframe');
        if(f&&f.contentWindow){
            f.contentWindow.postMessage({signalValue:sv, theme:theme},'*');
        }
        if(!window._jardinKbInit){
            window._jardinKbInit=true;
            document.addEventListener('keydown',function(e){
                var f2=document.getElementById('jardin-game-iframe');
                if(f2&&f2.contentWindow){
                    f2.contentWindow.postMessage({keydown:e.key},'*');
                }
            });
        }
        return '';}""",
    Output('jardin-game-iframe', 'title'),
    Input('jardin-signal-store', 'data'),
    Input('theme-store', 'data')
)

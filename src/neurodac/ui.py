"""Componentes compartidos por las paginas que hablan con la diadema.

La traduccion de estado a lo que ve el operador vive aqui y no en cada pagina,
porque es la pieza que decide si una demostracion se puede rescatar en vivo.
Esta separada en dos mitades: funciones puras, que se prueban sin Dash, y
constructores de componentes, que solo arman el arbol.
"""

from __future__ import annotations

from dataclasses import dataclass

import dash_bootstrap_components as dbc
from dash import dcc, html

from .acquisition import SIGNAL_TYPES, Quality, SignalState

__all__ = [
    "STATE_STYLES",
    "PanelIds",
    "StateStyle",
    "connection_panel",
    "describe",
    "format_age",
    "format_rate",
    "gate_children",
    "render_quality",
]


@dataclass(frozen=True)
class StateStyle:
    """Como se presenta un estado.

    Attributes
    ----------
    label : str
        Texto corto del distintivo.
    css_class : str
        Sufijo de clase; se combina con `status-badge`.
    hint : str
        Que debe hacer el operador. Es lo que convierte un diagnostico en una
        accion, y sin esto el indicador solo informa que algo anda mal.
    """

    label: str
    css_class: str
    hint: str


STATE_STYLES: dict[SignalState, StateStyle] = {
    SignalState.DISCONNECTED: StateStyle(
        "Desconectada",
        "disconnected",
        "Elige la fuente y presiona Conectar.",
    ),
    SignalState.NO_DATA: StateStyle(
        "Sin datos",
        "danger",
        "El puerto esta abierto pero no llegan tramas. "
        "Revisa que la diadema siga encendida y emparejada.",
    ),
    SignalState.NO_CONTACT: StateStyle(
        "Sin contacto",
        "danger",
        "El electrodo frontal no toca la piel. Acomoda la diadema en la frente "
        "y verifica el clip de la oreja.",
    ),
    SignalState.POOR_CONTACT: StateStyle(
        "Contacto pobre",
        "warning",
        "Hay contacto pero con ruido. Aparta el cabello de la frente y "
        "revisa que el clip haga contacto con el lobulo.",
    ),
    SignalState.CALIBRATING: StateStyle(
        "Calibrando",
        "info",
        "La diadema esta estableciendo su linea base. Pide al visitante que "
        "se quede quieto unos segundos.",
    ),
    SignalState.READY: StateStyle(
        "Lista",
        "connected",
        "Senal estable.",
    ),
}


def describe(quality: Quality) -> StateStyle:
    """Traduce un estado a etiqueta, clase y accion sugerida."""
    return STATE_STYLES[quality.state]


def format_rate(hz: float) -> str:
    """Formatea la tasa de tramas."""
    if hz <= 0:
        return "0 Hz"
    if hz < 10:
        return f"{hz:.1f} Hz"
    return f"{hz:.0f} Hz"


def format_age(seconds: float | None) -> str:
    """Formatea la antiguedad de la ultima trama."""
    if seconds is None:
        return "nunca"
    if seconds < 1:
        return "ahora"
    if seconds < 60:
        return f"hace {seconds:.0f} s"
    return f"hace {seconds / 60:.0f} min"


@dataclass(frozen=True)
class PanelIds:
    """Identificadores derivados de un prefijo, uno por pagina.

    Dash exige identificadores unicos en toda la aplicacion, asi que cada
    pagina construye los suyos a partir de un prefijo en lugar de escribirlos
    a mano y arriesgar colisiones.
    """

    prefix: str

    @property
    def source(self) -> str:
        return f"{self.prefix}-source"

    @property
    def port(self) -> str:
        return f"{self.prefix}-port"

    @property
    def signal(self) -> str:
        return f"{self.prefix}-signal"

    @property
    def connect(self) -> str:
        return f"{self.prefix}-connect"

    @property
    def stop(self) -> str:
        return f"{self.prefix}-stop"

    @property
    def status(self) -> str:
        return f"{self.prefix}-status"

    @property
    def quality(self) -> str:
        return f"{self.prefix}-quality"

    @property
    def interval(self) -> str:
        return f"{self.prefix}-interval"

    @property
    def store(self) -> str:
        return f"{self.prefix}-store"


def connection_panel(
    ids: PanelIds,
    *,
    default_signal: str = "raw",
    title: str | None = None,
) -> dbc.Card:
    """Arma el panel de conexion con su selector de fuente.

    La opcion de diadema simulada es visible desde la interfaz, no un modo
    escondido: sirve para ensayar la demostracion sin hardware y para mostrar
    los juegos cuando la diadema no esta disponible.
    """
    body = [
        dbc.Label("Fuente:", className="nd-label"),
        dbc.RadioItems(
            id=ids.source,
            options=[
                {"label": " Diadema", "value": "real"},
                {"label": " Simulada", "value": "sim"},
            ],
            value="real",
            inline=True,
            className="mb-2",
        ),
        dbc.Label("Puerto serial:", className="nd-label"),
        dbc.Input(
            id=ids.port,
            placeholder="COM3",
            type="text",
            className="mb-2",
        ),
        dbc.Label("Tipo de senal:", className="nd-label"),
        dcc.Dropdown(
            id=ids.signal,
            options=[{"label": s.capitalize(), "value": s} for s in SIGNAL_TYPES],
            value=default_signal,
            clearable=False,
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        "Conectar", id=ids.connect, className="btn-nd-primary w-100"
                    ),
                    width=6,
                ),
                dbc.Col(
                    dbc.Button("Detener", id=ids.stop, className="btn-nd-danger w-100"),
                    width=6,
                ),
            ]
        ),
        html.Div(id=ids.status, className="mt-2"),
        html.Div(id=ids.quality, className="nd-quality mt-2"),
    ]

    children = [dbc.CardBody(body)]
    if title:
        children.insert(0, dbc.CardHeader(title))
    return dbc.Card(children, className="mb-3")


def render_quality(quality: Quality) -> list:
    """Construye el bloque de calidad que ve el operador.

    Muestra las tres cosas que vuelven inequivoco el estado del enlace:
    contacto, tasa de tramas y antiguedad de la ultima.
    """
    style = describe(quality)

    rows = [
        html.Div(
            [
                html.Span(className="dot"),
                html.Span(style.label),
            ],
            className=f"status-badge {style.css_class}",
        ),
        html.Div(style.hint, className="nd-hint"),
    ]

    if quality.state is SignalState.CALIBRATING:
        rows.append(
            html.Div(
                html.Div(
                    className="nd-progress-fill",
                    style={"width": f"{quality.calibration_progress * 100:.0f}%"},
                ),
                className="nd-progress",
            )
        )

    metrics = [("Tramas", format_rate(quality.packet_rate_hz))]
    if quality.poor_signal is not None:
        metrics.append(("Contacto", str(quality.poor_signal)))
    metrics.append(("Ultima", format_age(quality.seconds_since_last_packet)))
    if quality.packets_bad_checksum:
        metrics.append(("Descartadas", str(quality.packets_bad_checksum)))

    rows.append(
        html.Div(
            [
                html.Span([html.Span(f"{name} ", className="nd-metric-name"), value])
                for name, value in metrics
            ],
            className="nd-metrics",
        )
    )

    if quality.error:
        rows.append(html.Div(quality.error, className="nd-error"))

    return rows


def gate_children(quality: Quality) -> list | None:
    """Contenido de la compuerta de arranque, o None si la senal ya sirve.

    Jardin y Carrera la comparten. Mientras devuelva algo, el juego no debe
    correr: es lo que impide que la flor se muera o que el fantasma se despegue
    antes de que el visitante haya hecho nada.
    """
    if quality.state is SignalState.READY:
        return None

    style = describe(quality)
    children = [
        html.Div(style.label, className="nd-gate-title"),
        html.Div(style.hint, className="nd-gate-hint"),
    ]
    if quality.state is SignalState.CALIBRATING:
        children.append(
            html.Div(
                html.Div(
                    className="nd-progress-fill",
                    style={"width": f"{quality.calibration_progress * 100:.0f}%"},
                ),
                className="nd-progress",
                style={"maxWidth": "220px"},
            )
        )
    return children

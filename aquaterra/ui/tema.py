"""Sistema de Diseño Dual (*Obsidian Bio-Tech* / *Field Daylight*) para AquaTerra Matrix v5.0.

Registra dos definiciones de tema personalizadas en ``ttkbootstrap`` 2.x, provee
la paleta semántica activa para widgets y figuras ``Matplotlib`` orientadas a
objetos, y centraliza tarjetas KPI y diálogos reutilizables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ttkbootstrap as ttk
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from ttkbootstrap.constants import BOTH, W, X
from ttkbootstrap.style.theme import Colors, ThemeDefinition

TEMA_OSCURO = "aquaterra-dark"
TEMA_CLARO = "aquaterra-light"

_PALETA_OSCURA_DEF = Colors(
    primary="#3b82f6",
    secondary="#64748b",
    success="#10b981",
    info="#06b6d4",
    warning="#f59e0b",
    danger="#ef4444",
    light="#1e293b",
    dark="#070a0e",
    bg="#0b0f14",
    fg="#f1f5f9",
    selectbg="#10b981",
    selectfg="#05130e",
    border="#263241",
    inputfg="#f1f5f9",
    inputbg="#131a22",
    active="#1c2633",
)

_PALETA_CLARA_DEF = Colors(
    primary="#2563eb",
    secondary="#64748b",
    success="#059669",
    info="#0284c7",
    warning="#d97706",
    danger="#dc2626",
    light="#e2e8f0",
    dark="#0f172a",
    bg="#f4f7f9",
    fg="#0f172a",
    selectbg="#059669",
    selectfg="#ffffff",
    border="#cbd5e1",
    inputfg="#0f172a",
    inputbg="#ffffff",
    active="#e2e8f0",
)


@dataclass(frozen=True, slots=True)
class PaletaUI:
    """Tokens cromáticos activos sincronizados entre Tkinter y Matplotlib."""

    nombre: str
    es_oscuro: bool
    bg: str
    card: str
    sidebar: str
    fg: str
    muted: str
    border: str
    primary: str
    success: str
    info: str
    warning: str
    danger: str


def registrar_temas_aquaterra(style: ttk.Style) -> None:
    """Registra ``aquaterra-dark`` y ``aquaterra-light`` en el motor de ``ttkbootstrap``."""
    registrados = set(style.theme_names())
    if TEMA_OSCURO not in registrados:
        style.register_theme(ThemeDefinition(TEMA_OSCURO, _PALETA_OSCURA_DEF, mode="dark"))
    if TEMA_CLARO not in registrados:
        style.register_theme(ThemeDefinition(TEMA_CLARO, _PALETA_CLARA_DEF, mode="light"))
    style.set_theme_modes(light=TEMA_CLARO, dark=TEMA_OSCURO)
    configurar_estilos_shell(style)


def configurar_estilos_shell(style: ttk.Style) -> None:
    """Ajusta tipografía limpia y jerarquía visual del *App Shell*."""
    tema = style.theme_use()
    es_oscuro = tema != TEMA_CLARO
    sidebar_bg = "#080b0f" if es_oscuro else "#e8eef3"
    card_bg = "#131a22" if es_oscuro else "#ffffff"
    fg = "#f1f5f9" if es_oscuro else "#0f172a"
    muted = "#94a3b8" if es_oscuro else "#475569"

    style.configure("Sidebar.TFrame", background=sidebar_bg)
    style.configure("SidebarBrand.TLabel", background=sidebar_bg, foreground="#10b981" if es_oscuro else "#059669")
    style.configure("SidebarMuted.TLabel", background=sidebar_bg, foreground=muted)
    style.configure("Card.TFrame", background=card_bg)
    style.configure("CardTitle.TLabel", background=card_bg, foreground=muted)
    style.configure("CardValue.TLabel", background=card_bg, foreground=fg)
    style.configure("ShellStatus.TLabel", foreground=muted)


def paleta_activa(style: ttk.Style) -> PaletaUI:
    """Devuelve la ``PaletaUI`` correspondiente al tema cargado."""
    tema = style.theme_use()
    if tema == TEMA_CLARO:
        return PaletaUI(
            nombre=TEMA_CLARO,
            es_oscuro=False,
            bg="#f4f7f9",
            card="#ffffff",
            sidebar="#e8eef3",
            fg="#0f172a",
            muted="#475569",
            border="#cbd5e1",
            primary="#2563eb",
            success="#059669",
            info="#0284c7",
            warning="#d97706",
            danger="#dc2626",
        )
    return PaletaUI(
        nombre=TEMA_OSCURO,
        es_oscuro=True,
        bg="#0b0f14",
        card="#131a22",
        sidebar="#080b0f",
        fg="#f1f5f9",
        muted="#94a3b8",
        border="#263241",
        primary="#3b82f6",
        success="#10b981",
        info="#06b6d4",
        warning="#f59e0b",
        danger="#ef4444",
    )


def estilizar_figura(fig: Figure, ejes: Axes | list[Axes], paleta: PaletaUI) -> None:
    """Aplica fondo, retícula, ticks y tipografía acorde a la paleta Bio-IoT activa."""
    lista_ejes = [ejes] if isinstance(ejes, Axes) else list(ejes)
    fig.patch.set_facecolor(paleta.card)
    for ax in lista_ejes:
        ax.set_facecolor(paleta.bg)
        ax.tick_params(colors=paleta.muted, labelsize=8)
        ax.xaxis.label.set_color(paleta.fg)
        ax.yaxis.label.set_color(paleta.fg)
        ax.title.set_color(paleta.fg)
        ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.45, color=paleta.border)
        for spine in ax.spines.values():
            spine.set_color(paleta.border)


def crear_tarjeta_kpi(
    parent: Any,
    titulo: str,
    valor_inicial: str = "—",
    subtitulo: str = "",
    *,
    bootstyle: str = "info",
) -> tuple[ttk.Frame, ttk.Label, ttk.Label]:
    """Construye una tarjeta KPI compacta y devuelve ``(frame, lbl_valor, lbl_subtitulo)``."""
    marco = ttk.Labelframe(parent, text=f" {titulo} ", padding=(12, 8), bootstyle=bootstyle)
    lbl_valor = ttk.Label(marco, text=valor_inicial, font=("Segoe UI", 18, "bold"), bootstyle=bootstyle)
    lbl_valor.pack(anchor=W, fill=X)
    lbl_sub = ttk.Label(marco, text=subtitulo, font=("Segoe UI", 9), bootstyle="secondary")
    lbl_sub.pack(anchor=W, fill=BOTH, pady=(2, 0))
    return marco, lbl_valor, lbl_sub

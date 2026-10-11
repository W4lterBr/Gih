# -*- coding: utf-8 -*-
"""Folhas de estilo (QSS) dos temas.

Todos os temas são gerados a partir do mesmo modelo (`build_qss`) e diferem só na
paleta de cores (`PALETTES`). Para criar um tema novo basta adicionar uma paleta;
para mudar o visual de todos os temas, edite o modelo uma única vez.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, asdict
from typing import Callable


@dataclass(frozen=True)
class Palette:
    bg: str            # fundo da janela
    surface: str       # cartões, tabelas, campos
    surface_alt: str   # linhas alternadas, cabeçalhos de tabela
    sidebar: str       # menu lateral
    border: str        # bordas suaves
    border_strong: str # bordas de campos
    text: str          # texto principal
    muted: str         # texto secundário
    accent: str        # cor da marca (botões primários, seleção)
    accent_hover: str
    accent_soft: str   # fundo de item selecionado / hover
    accent_text: str   # texto sobre o accent
    scroll: str        # alça das barras de rolagem
    scroll_hover: str


PALETTES: dict[str, Palette] = {
    "light": Palette(
        bg="#f4f5f9", surface="#ffffff", surface_alt="#f8f9fc", sidebar="#ffffff",
        border="#e7e9f0", border_strong="#d5d9e3", text="#1d2130", muted="#6b7183",
        accent="#6366f1", accent_hover="#4f46e5", accent_soft="#eef0ff", accent_text="#ffffff",
        scroll="#cfd3dd", scroll_hover="#a9afbd",
    ),
    "dark": Palette(
        bg="#0e1016", surface="#171a22", surface_alt="#1c2029", sidebar="#12141b",
        border="#252a35", border_strong="#323846", text="#e6e8ee", muted="#9097a8",
        accent="#8b7cf6", accent_hover="#9d90f8", accent_soft="#262243", accent_text="#ffffff",
        scroll="#363c4a", scroll_hover="#4a5162",
    ),
    "pink": Palette(
        bg="#fbf5f8", surface="#ffffff", surface_alt="#fdf8fb", sidebar="#ffffff",
        border="#f3e3ec", border_strong="#e9cfdd", text="#2a1b24", muted="#86687a",
        accent="#db2777", accent_hover="#be185d", accent_soft="#fdebf4", accent_text="#ffffff",
        scroll="#e6c9d8", scroll_hover="#cfa3ba",
    ),
    "purple": Palette(
        bg="#f7f5fc", surface="#ffffff", surface_alt="#faf8fe", sidebar="#ffffff",
        border="#ebe5f7", border_strong="#dbd1ef", text="#221a33", muted="#76698f",
        accent="#7c3aed", accent_hover="#6d28d9", accent_soft="#f3edff", accent_text="#ffffff",
        scroll="#d6cbec", scroll_hover="#b4a3d8",
    ),
    "blue": Palette(
        bg="#f3f7fc", surface="#ffffff", surface_alt="#f7fafe", sidebar="#ffffff",
        border="#e2eaf5", border_strong="#cfdbec", text="#15233a", muted="#62728c",
        accent="#2563eb", accent_hover="#1d4ed8", accent_soft="#eaf1fe", accent_text="#ffffff",
        scroll="#c7d5ea", scroll_hover="#9fb4d6",
    ),
}

THEME_NAMES = tuple(PALETTES)


def palette(theme: str) -> Palette:
    """Paleta do tema (temas desconhecidos caem no claro)."""
    return PALETTES.get(theme, PALETTES["light"])


_TEMPLATE = """
* { font-family: 'Segoe UI', 'Segoe UI Variable', Arial; font-size: 14px; color: %(text)s; outline: none; }
QMainWindow, QWidget#Root { background: %(bg)s; }
QLabel { color: %(text)s; background: transparent; }
QToolTip { background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s; border-radius: 6px; padding: 6px 8px; }

/* ---------- Menu lateral ---------- */
QFrame#SidebarPanel { background: %(sidebar)s; border: none; border-right: 1px solid %(border)s; }
QLabel#BrandName { font-size: 15px; font-weight: 700; color: %(text)s; }
QLabel#BrandCaption { font-size: 12px; color: %(muted)s; }
QListWidget#Sidebar { background: transparent; border: none; color: %(muted)s; }
QListWidget#Sidebar::item { padding: 10px 12px; margin: 2px 0px; border-radius: 10px; color: %(muted)s; }
QListWidget#Sidebar::item:hover { background: %(surface_alt)s; color: %(text)s; }
QListWidget#Sidebar::item:selected { background: %(accent_soft)s; color: %(accent)s; font-weight: 600; }

/* ---------- Cabeçalho ---------- */
QWidget#RightArea { background: %(bg)s; }
QWidget#RightArea .QWidget, QWidget#RightArea .QStackedWidget { background: transparent; }
QWidget#Header { background: transparent; border-bottom: 1px solid %(border)s; }
QLabel#AppTitle { color: %(text)s; font-size: 18px; font-weight: 700; }
QLabel#WebAccessBanner {
    background: %(accent_soft)s; color: %(accent)s; border: 1px solid %(accent_soft)s;
    border-radius: 16px; padding: 6px 14px; font-size: 12px; font-weight: 600;
}
QLabel#WebAccessBanner:hover { border: 1px solid %(accent)s; }
QLabel#Footer { color: %(muted)s; font-size: 11px; padding: 4px; }

/* ---------- Páginas ---------- */
QLabel#PageTitle { font-size: 22px; font-weight: 700; color: %(text)s; }
QLabel#subtitle { color: %(muted)s; font-size: 13px; }

/* Cartões / grupos */
QFrame#SettingsGroup, QFrame#Card {
    background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px; padding: 14px;
}
QGroupBox {
    background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px;
    margin-top: 0px; padding: 40px 14px 14px 14px; font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: padding; subcontrol-position: top left;
    left: 16px; top: 12px; padding: 0px; color: %(text)s; font-size: 14px; font-weight: 700;
}
QLabel#DbPathLabel {
    background: %(surface_alt)s; border: 1px solid %(border)s; border-radius: 8px; padding: 8px; color: %(muted)s;
}

/* Cards de indicadores */
QFrame#StatCard { background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px; }
QLabel#CardTitle { color: %(muted)s; font-size: 12px; font-weight: 600; }
QLabel#CardValue { color: %(text)s; font-size: 22px; font-weight: 700; }

/* ---------- Botões ---------- */
QPushButton {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s;
    border-radius: 9px; padding: 7px 14px; min-height: 20px; font-weight: 500;
}
QPushButton:hover { background: %(accent_soft)s; border-color: %(accent)s; color: %(accent)s; }
QPushButton:pressed { background: %(accent_soft)s; border-color: %(accent_hover)s; }
QPushButton:disabled { color: %(muted)s; background: %(surface_alt)s; border-color: %(border)s; }
QPushButton:default, QPushButton[primary="true"] {
    background: %(accent)s; color: %(accent_text)s; border: 1px solid %(accent)s;
}
QPushButton:default:hover, QPushButton[primary="true"]:hover { background: %(accent_hover)s; border-color: %(accent_hover)s; color: %(accent_text)s; }
QPushButton:checked { background: %(accent_soft)s; color: %(accent)s; border-color: %(accent)s; }
QPushButton[chip="true"] { border-radius: 15px; padding: 5px 14px; }
QPushButton[chip="true"]:checked { background: %(accent)s; color: %(accent_text)s; border-color: %(accent)s; font-weight: 600; }
QPushButton#IconButton {
    padding: 0px; min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
    border-radius: 14px; background: %(surface_alt)s; border: 1px solid %(border)s;
}
QPushButton#IconButton:hover { background: %(accent_soft)s; border-color: %(accent)s; }

/* ---------- Campos ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QComboBox {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s;
    border-radius: 9px; padding: 6px 10px; min-height: 20px;
    selection-background-color: %(accent)s; selection-color: %(accent_text)s;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus, QComboBox:focus { border: 1px solid %(accent)s; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QDateEdit:disabled {
    background: %(surface_alt)s; color: %(muted)s;
}
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 22px; }
QComboBox::down-arrow, QDateEdit::down-arrow { image: url(%(chevron)s); width: 12px; height: 12px; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: none; width: 16px; background: transparent;
}
QComboBox QAbstractItemView {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s; border-radius: 8px;
    padding: 4px; selection-background-color: %(accent_soft)s; selection-color: %(accent)s;
}
QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px; border: 1px solid %(border_strong)s; background: %(surface)s;
}
QCheckBox::indicator { border-radius: 5px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: %(accent)s; border-color: %(accent)s; }

/* ---------- Tabelas ---------- */
QTableWidget, QTableView, QListWidget, QTreeWidget, QTreeView {
    background: %(surface)s; alternate-background-color: %(surface_alt)s; color: %(text)s;
    gridline-color: %(border)s; border: 1px solid %(border)s; border-radius: 12px;
    selection-background-color: %(accent_soft)s; selection-color: %(text)s;
}
QTableWidget::item, QTableView::item { padding: 6px 8px; border: none; }
QTableWidget::item:selected, QTableView::item:selected, QListWidget::item:selected {
    background: %(accent_soft)s; color: %(text)s;
}
QTableWidget::item:hover, QTableView::item:hover { background: %(surface_alt)s; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: %(surface_alt)s; color: %(muted)s; padding: 8px 8px; border: none;
    border-bottom: 1px solid %(border)s; font-size: 12px; font-weight: 600;
}
QHeaderView::section:vertical { border-bottom: none; border-right: 1px solid %(border)s; padding: 4px 6px; }
QTableCornerButton::section { background: %(surface_alt)s; border: none; }

/* ---------- Abas ---------- */
QTabWidget::pane { border: 1px solid %(border)s; border-radius: 12px; background: %(surface)s; top: -1px; }
QTabBar::tab {
    background: transparent; color: %(muted)s; padding: 8px 16px; margin-right: 4px;
    border: none; border-bottom: 2px solid transparent;
}
QTabBar::tab:hover { color: %(text)s; }
QTabBar::tab:selected { color: %(accent)s; border-bottom: 2px solid %(accent)s; font-weight: 600; }

/* ---------- Barras de rolagem ---------- */
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; border: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; border: none; }
QScrollBar::handle:vertical { background: %(scroll)s; min-height: 28px; border-radius: 3px; }
QScrollBar::handle:horizontal { background: %(scroll)s; min-width: 28px; border-radius: 3px; }
QScrollBar::handle:hover { background: %(scroll_hover)s; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; background: none; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ---------- Progresso ---------- */
QProgressBar {
    background: %(surface_alt)s; border: 1px solid %(border)s; border-radius: 7px;
    text-align: center; color: %(text)s; min-height: 14px;
}
QProgressBar::chunk { background: %(accent)s; border-radius: 6px; }

/* ---------- Calendário (popup do QDateEdit) ---------- */
QCalendarWidget QWidget { background: %(surface)s; color: %(text)s; alternate-background-color: %(surface_alt)s; }
QCalendarWidget QToolButton {
    background: transparent; color: %(text)s; border: none; border-radius: 6px; padding: 4px 8px; font-weight: 600;
}
QCalendarWidget QToolButton:hover { background: %(accent_soft)s; color: %(accent)s; }
QCalendarWidget QAbstractItemView {
    background: %(surface)s; color: %(text)s; border: none;
    selection-background-color: %(accent)s; selection-color: %(accent_text)s;
}
QCalendarWidget QAbstractItemView:disabled { color: %(muted)s; }

/* ---------- Menus ---------- */
QMenuBar { background: %(bg)s; color: %(muted)s; padding: 2px 6px; border-bottom: 1px solid %(border)s; }
QMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 6px; }
QMenuBar::item:selected { background: %(accent_soft)s; color: %(accent)s; }
QMenu { background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; }
QMenu::item:selected { background: %(accent_soft)s; color: %(accent)s; }
QMenu::item:disabled { color: %(muted)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 4px 8px; }

/* ---------- Diálogos ---------- */
QDialog, QMessageBox { background: %(bg)s; color: %(text)s; }
QDialog QLabel, QMessageBox QLabel { color: %(text)s; }

/* ---------- Relatórios ---------- */
QLabel[report="true"] { color: %(muted)s; font-size: 13px; }
QLabel[total="true"] { color: %(accent)s; font-weight: 700; }

/* ---------- Toast ---------- */
#Toast { background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s; border-radius: 12px; }
"""


def _chevron_icon(color: str) -> str:
    """Seta (SVG) na cor do tema para combos/datas. O QSS só aceita imagem por arquivo,
    então o SVG é gravado uma vez numa pasta temporária."""
    folder = os.path.join(tempfile.gettempdir(), "confeitaria_theme")
    path = os.path.join(folder, f"chevron_{color.lstrip('#')}.svg")
    if not os.path.exists(path):
        try:
            os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
                    f'<path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="{color}" stroke-width="1.6" '
                    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
                )
        except OSError:
            return ""
    return path.replace("\\", "/")


def build_qss(theme: str) -> str:
    """Gera a folha de estilo completa do tema."""
    pal = palette(theme)
    return _TEMPLATE % {**asdict(pal), "chevron": _chevron_icon(pal.muted)}


_theme_listeners: list[Callable[[str], None]] = []
_current_theme = "light"


def on_theme_changed(callback: Callable[[str], None]) -> None:
    """Registra um callback chamado com o nome do tema sempre que ele mudar
    (para widgets que pintam cores fora do QSS: ícones, gráficos)."""
    _theme_listeners.append(callback)


def current_theme() -> str:
    return _current_theme


def apply_theme(app, theme: str) -> None:
    """Aplica o tema na aplicação inteira e avisa os widgets registrados."""
    global _current_theme
    _current_theme = theme if theme in PALETTES else "light"
    app.setStyleSheet(build_qss(_current_theme))
    for cb in list(_theme_listeners):
        try:
            cb(_current_theme)
        except RuntimeError:
            # widget já destruído
            _theme_listeners.remove(cb)


# Funções mantidas por compatibilidade com o restante do código
def qss_light() -> str:
    return build_qss("light")


def qss_dark() -> str:
    return build_qss("dark")


def qss_pink() -> str:
    return build_qss("pink")


def qss_purple() -> str:
    return build_qss("purple")


def qss_blue() -> str:
    return build_qss("blue")

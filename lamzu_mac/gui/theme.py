"""Colors and the application style sheet."""
from __future__ import annotations

import sys
from pathlib import Path

CHEVRON = (Path(__file__).parent / "assets" / "chevron-down.svg").as_posix()

BG = "#0d0f13"
SIDEBAR = "#12151a"
CARD = "#171b21"
CARD_HOVER = "#1c2128"
BORDER = "#242a33"
BORDER_STRONG = "#2f3742"
TEXT = "#e9ecf1"
TEXT_DIM = "#9aa3af"
TEXT_FAINT = "#5f6874"
ACCENT = "#4c8dff"
ACCENT_HOVER = "#6aa1ff"
ACCENT_SOFT = "#1b2a44"
SUCCESS = "#3ecf8e"
WARNING = "#f5a524"
DANGER = "#f2555a"

FONT = ".AppleSystemUIFont" if sys.platform == "darwin" else "Segoe UI"

STYLE = f"""
* {{
    font-family: "{FONT}";
    color: {TEXT};
    outline: 0;
}}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget#content {{ background: {BG}; }}
QToolTip {{
    background: {CARD_HOVER}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
    padding: 6px 8px; border-radius: 6px;
}}

/* ---- sidebar ------------------------------------------------------- */
QFrame#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QLabel#brand {{ font-size: 15px; font-weight: 600; letter-spacing: 0.3px; }}
QLabel#brandSub {{ color: {TEXT_FAINT}; font-size: 11px; }}
QPushButton#nav {{
    text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
    font-size: 13px; color: {TEXT_DIM}; background: transparent;
}}
QPushButton#nav:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {ACCENT_SOFT}; color: {TEXT}; font-weight: 600; }}
QFrame#deviceCard {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QLabel#deviceName {{ font-size: 13px; font-weight: 600; }}
QLabel#deviceMeta {{ color: {TEXT_DIM}; font-size: 11px; }}

/* ---- page chrome --------------------------------------------------- */
QLabel#pageTitle {{ font-size: 22px; font-weight: 600; }}
QLabel#pageSubtitle {{ color: {TEXT_DIM}; font-size: 13px; }}
QFrame#card {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px;
}}
QLabel#cardTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#cardHint, QLabel#hint {{ color: {TEXT_DIM}; font-size: 12px; }}
QLabel#rowLabel {{ font-size: 13px; }}
QLabel#rowHint {{ color: {TEXT_FAINT}; font-size: 11px; }}
QLabel#value {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
QLabel#bigValue {{ font-size: 26px; font-weight: 600; }}
QLabel#warning {{
    color: {WARNING}; font-size: 12px; background: #2a2210; border: 1px solid #4a3a14;
    border-radius: 8px; padding: 8px 10px;
}}
QFrame#banner {{
    background: #2a2210; border: 1px solid #4a3a14; border-radius: 10px;
}}
QFrame#separator {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}

/* ---- inputs -------------------------------------------------------- */
QPushButton {{
    background: {CARD_HOVER}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 8px 14px; font-size: 13px;
}}
QPushButton:hover {{ border-color: {TEXT_FAINT}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#danger {{ color: {DANGER}; border-color: #4a2427; background: #24171a; }}
QPushButton#danger:hover {{ border-color: {DANGER}; }}
QPushButton#segment {{
    background: transparent; border: none; border-radius: 7px; padding: 7px 12px;
    color: {TEXT_DIM}; font-size: 12px; font-weight: 600;
}}
QPushButton#segment:hover {{ color: {TEXT}; }}
QPushButton#segment:checked {{ background: {ACCENT}; color: white; }}
QFrame#segmented {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 9px; }}

QComboBox, QSpinBox, QLineEdit {{
    background: {BG}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 7px 10px; font-size: 13px; min-height: 18px;
    selection-background-color: {ACCENT};
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: {TEXT_FAINT}; }}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url("{CHEVRON}"); width: 12px; height: 12px; margin-right: 10px; }}
QComboBox::down-arrow:disabled {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {CARD_HOVER}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 4px; selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT};
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
QSpinBox:disabled, QComboBox:disabled, QLineEdit:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER}; }}
QLineEdit#capture {{ font-size: 15px; font-weight: 600; padding: 10px 12px; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER_STRONG}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::sub-page:horizontal:disabled {{ background: {TEXT_FAINT}; }}
QSlider::handle:horizontal {{
    background: white; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
}}
QSlider::handle:horizontal:disabled {{ background: {TEXT_FAINT}; }}

QRadioButton {{ spacing: 0; }}
QRadioButton::indicator {{
    width: 14px; height: 14px; border-radius: 8px; border: 2px solid {TEXT_FAINT};
}}
QRadioButton::indicator:checked {{ border: 2px solid {ACCENT}; background: qradialgradient(
    cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {ACCENT}, stop:0.45 {ACCENT},
    stop:0.5 transparent); }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QListWidget {{ background: transparent; border: none; }}
QListWidget::item {{ border-radius: 8px; padding: 0; margin: 2px 0; }}
QListWidget::item:selected {{ background: {ACCENT_SOFT}; }}
QListWidget::item:hover:!selected {{ background: {CARD_HOVER}; }}

QLabel#toast {{
    background: {CARD_HOVER}; border: 1px solid {BORDER_STRONG}; border-radius: 10px;
    padding: 10px 16px; font-size: 13px;
}}
QMessageBox {{ background: {CARD}; }}
"""

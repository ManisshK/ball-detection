"""
theme.py - Centralised dark theme colours, fonts, and stylesheet for the
           Ball Detection & Tracking System UI.
"""

# ── Palette ──────────────────────────────────────────────────────────────────
BG_DARK       = "#0d0d0d"
BG_PANEL      = "#141414"
BG_CARD       = "#1a1a1a"
BG_HOVER      = "#222222"
ACCENT        = "#39ff14"          # neon green
ACCENT_DIM    = "#1a7a09"
TEXT_PRIMARY  = "#e8e8e8"
TEXT_SECONDARY= "#7a7a7a"
BORDER        = "#2a2a2a"
RED           = "#ff3b3b"
YELLOW        = "#ffcc00"
BTN_START     = "#1db954"
BTN_START_H   = "#17a347"
BTN_STOP      = "#e03131"
BTN_STOP_H    = "#c92a2a"
BTN_ACTION    = "#1e1e1e"
BTN_ACTION_H  = "#2d2d2d"

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_FAMILY   = "Segoe UI"
FONT_MONO     = "Consolas"

# ── Stylesheet ────────────────────────────────────────────────────────────────
STYLESHEET = f"""
/* ── Global ── */
* {{
    font-family: '{FONT_FAMILY}', sans-serif;
    color: {TEXT_PRIMARY};
    outline: none;
}}
QMainWindow, QWidget#centralWidget {{
    background: {BG_DARK};
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── Top bar ── */
QWidget#topBar {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}

/* ── Sidebar ── */
QWidget#sidebar {{
    background: {BG_PANEL};
    border-right: 1px solid {BORDER};
}}
QPushButton#navBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}
QPushButton#navBtn:hover {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}
QPushButton#navBtn[active="true"] {{
    background: {BG_HOVER};
    color: {ACCENT};
    border-left: 3px solid {ACCENT};
}}

/* ── Right panel ── */
QWidget#rightPanel {{
    background: {BG_PANEL};
    border-left: 1px solid {BORDER};
}}

/* ── Stat card ── */
QWidget#statCard {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* ── Bottom bar ── */
QWidget#bottomBar {{
    background: {BG_PANEL};
    border-top: 1px solid {BORDER};
}}

/* ── Action buttons ── */
QPushButton#actionBtn {{
    background: {BTN_ACTION};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 12px;
    color: {TEXT_PRIMARY};
}}
QPushButton#actionBtn:hover {{
    background: {BTN_ACTION_H};
    border-color: {ACCENT};
    color: {ACCENT};
}}

/* ── Start / Stop ── */
QPushButton#startBtn {{
    background: {BTN_START};
    border: none;
    border-radius: 8px;
    padding: 7px 20px;
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
}}
QPushButton#startBtn:hover {{ background: {BTN_START_H}; }}

QPushButton#stopBtn {{
    background: {BTN_STOP};
    border: none;
    border-radius: 8px;
    padding: 7px 20px;
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
}}
QPushButton#stopBtn:hover {{ background: {BTN_STOP_H}; }}

/* ── Window control buttons ── */
QPushButton#winBtn {{
    background: transparent;
    border: none;
    border-radius: 5px;
    font-size: 14px;
    padding: 4px 10px;
    color: {TEXT_SECONDARY};
}}
QPushButton#winBtn:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}
QPushButton#winBtn#closeBtn:hover {{ background: {BTN_STOP}; color: #fff; }}

/* ── Camera feed placeholder ── */
QLabel#feedPlaceholder {{
    background: #0a0a0a;
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_SECONDARY};
    font-size: 15px;
}}

/* ── Dividers ── */
QFrame#divider {{
    background: {BORDER};
    max-height: 1px;
}}
"""

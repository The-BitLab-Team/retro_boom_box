"""Temas visuais do Retro Boom Box.

Cada tema é só um conjunto de cores e estilos. No passo 3 do plano isso vira
"skins" carregadas de pastas; por enquanto os dois temas ficam aqui dentro.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    font: str
    mono: str
    button_style: str          # "round" (vidro) ou "rect" (metal)
    viz_style: str             # "glass" ou "lcd"
    margins: tuple             # margens internas da janela (esq, topo, dir, base)
    radius: int                # arredondamento do corpo do player
    text: str
    text_dim: str
    glyph: str
    accent: str
    lcd_top: str
    lcd_bottom: str
    lcd_border: str
    lcd_text: str
    lcd_dim: str
    list_bg: str
    list_text: str
    list_dim: str
    list_sel_top: str
    list_sel_bottom: str
    list_sel_text: str
    list_border: str
    dialog_bg: str
    dialog_text: str
    field_bg: str
    field_border: str
    viz_colors: tuple          # (graves, médios, agudos)
    viz_bg: str
    # botões e barras deslizantes (valores do visual "Aero"; o metal troca todos)
    btn_top: str = "#ffffff"
    btn_mid: str = "#d4eefc"
    btn_low: str = "#a6d6f2"
    btn_end: str = "#d2edfb"
    btn_border: str = "#6fb0da"
    play_light: str = "#c9ffbd"     # esfera do botão play
    play_mid: str = "#57d65a"
    play_dark: str = "#138a2c"
    groove_a: str = "#7fb6d8"
    groove_b: str = "#c9e9fa"
    fill_a: str = "#a8f59a"
    fill_b: str = "#2fb84a"
    knob_a: str = "#ffffff"
    knob_b: str = "#6aaedb"


AERO = Theme(
    key="aero", label="Frutiger Aero",
    font="Segoe UI", mono="Consolas",
    button_style="round", viz_style="glass",
    margins=(50, 30, 50, 34), radius=120,
    text="#08365c", text_dim="#2a6c9c", glyph="#0b4a7d", accent="#2fb84a",
    lcd_top="#e9fbff", lcd_bottom="#8fdcf7", lcd_border="#ffffff",
    lcd_text="#06395f", lcd_dim="#3a7aa8",
    list_bg="#eaf7fe", list_text="#08365c", list_dim="#2a6c9c",
    list_sel_top="#ffffff", list_sel_bottom="#c8ecff", list_sel_text="#04304f",
    list_border="#9fd0ee",
    dialog_bg="#dff2fd", dialog_text="#08365c", field_bg="#ffffff", field_border="#7fb9dd",
    viz_colors=("#2fd35a", "#19a8e8", "#0b6fbf"), viz_bg="#00000000",
)

METAL = Theme(
    key="metal", label="Metal escovado",
    font="Tahoma", mono="Consolas",
    button_style="rect", viz_style="lcd",
    margins=(30, 22, 30, 26), radius=18,
    text="#1d2a36", text_dim="#4b5560", glyph="#1d2a36", accent="#3fae2f",
    lcd_top="#0c160d", lcd_bottom="#081008", lcd_border="#5b6168",
    lcd_text="#8dff76", lcd_dim="#4fae41",
    list_bg="#101418", list_text="#6fe35c", list_dim="#3f9a33",
    list_sel_top="#1d3a1d", list_sel_bottom="#142914", list_sel_text="#b6ff9f",
    list_border="#5b6168",
    dialog_bg="#c9ced4", dialog_text="#1d2a36", field_bg="#f1f3f5", field_border="#6f767e",
    viz_colors=("#8dff76", "#6fe35c", "#3f9a33"), viz_bg="#00000000",
    btn_top="#fbfcfd", btn_mid="#d3d7dc", btn_low="#b5bbc2", btn_end="#dfe2e6", btn_border="#5f666e",
    groove_a="#1a1f24", groove_b="#2a2f35", fill_a="#a6ff92", fill_b="#3fae2f", knob_a="#ffffff", knob_b="#a9afb6",
)

THEMES = {AERO.key: AERO, METAL.key: METAL}


def make_qss(t: Theme) -> str:
    """Folha de estilo global (menus, listas, janelas de diálogo...)."""
    if t.button_style == "rect":   # botões de metal
        b_top, b_mid, b_bot, b_text, tab_bg = "#fbfcfd", "#d3d7dc", "#b5bbc2", "#1d2a36", "#b5bbc2"
    else:                          # botões de vidro
        b_top, b_mid, b_bot, b_text, tab_bg = "#ffffff", t.list_sel_bottom, "#a6d6f2", t.glyph, t.list_sel_bottom
    return f"""
    QWidget {{ font-family: "{t.font}", "Segoe UI", Tahoma, sans-serif; font-size: 13px; }}
    QDialog, QMessageBox, QInputDialog {{ background: {t.dialog_bg}; color: {t.dialog_text}; }}
    QDialog QLabel, QMessageBox QLabel, QCheckBox, QRadioButton {{ color: {t.dialog_text}; background: transparent; }}
    QTabWidget::pane {{ border: 1px solid {t.field_border}; background: {t.field_bg}; top: -1px; }}
    QTabBar::tab {{ padding: 7px 16px; margin-right: 3px; color: {t.dialog_text};
        border: 1px solid {t.field_border}; border-bottom: 0; border-top-left-radius: 8px; border-top-right-radius: 8px;
        background: {tab_bg}; }}
    QTabBar::tab:selected {{ background: {t.field_bg}; font-weight: 600; }}
    QLineEdit, QComboBox, QSpinBox {{ background: {t.field_bg}; color: {t.dialog_text};
        border: 1px solid {t.field_border}; border-radius: 6px; padding: 5px 8px; selection-background-color: {t.accent}; }}
    QComboBox QAbstractItemView {{ background: {t.field_bg}; color: {t.dialog_text}; selection-background-color: {t.list_sel_bottom};
        selection-color: {t.list_sel_text}; border: 1px solid {t.field_border}; }}
    QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {b_top}, stop:0.5 {b_mid}, stop:1 {b_bot});
        color: {b_text}; border: 1px solid {t.field_border}; border-radius: 8px; padding: 6px 16px; font-weight: 600; }}
    QPushButton:hover {{ border-color: {t.accent}; }}
    QPushButton:pressed {{ background: {b_bot}; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t.field_border}; border-radius: 4px; background: {t.field_bg}; }}
    QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.glyph}; }}
    QRadioButton::indicator {{ width: 16px; height: 16px; border: 1px solid {t.field_border}; border-radius: 9px; background: {t.field_bg}; }}
    QRadioButton::indicator:checked {{ background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {t.accent}, stop:0.55 {t.accent}, stop:0.62 {t.field_bg}, stop:1 {t.field_bg}); border-color: {t.glyph}; }}
    QListWidget {{ background: {t.list_bg}; color: {t.list_text}; border: 1px solid {t.list_border}; border-radius: 10px; outline: 0; padding: 3px; }}
    QListWidget::item:selected {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {t.list_sel_top}, stop:1 {t.list_sel_bottom});
        color: {t.list_sel_text}; border-radius: 6px; }}
    QMenu {{ background: {t.field_bg}; color: {t.dialog_text}; border: 1px solid {t.field_border}; padding: 4px; }}
    QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {t.list_sel_bottom}; color: {t.list_sel_text}; }}
    QMenu::separator {{ height: 1px; background: {t.field_border}; margin: 4px 8px; }}
    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t.field_border}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QToolTip {{ background: {t.field_bg}; color: {t.dialog_text}; border: 1px solid {t.field_border}; padding: 4px; }}
    """

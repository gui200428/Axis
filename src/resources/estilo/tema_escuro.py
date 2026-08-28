"""
Módulo de definição do tema visual escuro moderno para o AXIS Plotter.

Utiliza uma paleta profissional de cinza-azulado neutro com tipografia
hierárquica, bordas sutis e design limpo — sem neon ou efeitos extravagantes.
"""

PALETA_CORES = {
    "fundo_app": "#1b1b2f",
    "fundo_elevado": "#252540",
    "fundo_elevado_2": "#2c2c48",
    "fundo_input": "#1e1e35",
    "borda_suave": "#33334d",
    "borda_foco": "#5b7fff",
    "texto_principal": "#e8e8f0",
    "texto_secundario": "#9090a8",
    "texto_suave": "#6a6a82",
    "azul_primario": "#5b7fff",
    "azul_hover": "#4a6ae0",
    "azul_ativo": "#3d5bc7",
    "verde_sucesso": "#4ade80",
    "verde_hover": "#36c76c",
    "amarelo_aviso": "#fbbf24",
    "amarelo_hover": "#e0a820",
    "vermelho_perigo": "#f87171",
    "vermelho_hover": "#e05555",
    "roxo_acento": "#a78bfa",
}

ESTILO_GLOBAL = """
/* ============================================================ */
/*  AXIS Plotter — Tema Limpo Profissional                      */
/* ============================================================ */

/* --- Base Global --- */
QWidget {
    background-color: #1b1b2f;
    color: #e8e8f0;
    font-family: 'Segoe UI', 'Ubuntu', 'Roboto', sans-serif;
    font-size: 12px;
    selection-background-color: #5b7fff;
    selection-color: #ffffff;
}

QMainWindow {
    background-color: #1b1b2f;
}

/* --- Tabs — Flat com indicador inferior --- */
QTabWidget::pane {
    border: none;
    background-color: #1b1b2f;
    top: 0px;
}

QTabBar::tab {
    background-color: transparent;
    color: #9090a8;
    padding: 9px 18px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
    font-size: 12px;
    min-width: 90px;
}

QTabBar::tab:hover {
    color: #e8e8f0;
    border-bottom: 2px solid #44446a;
}

QTabBar::tab:selected {
    color: #e8e8f0;
    border-bottom: 2px solid #5b7fff;
    font-weight: 700;
}

/* --- Botões Padrão --- */
QPushButton {
    background-color: #2c2c48;
    color: #e8e8f0;
    border: 1px solid #3a3a58;
    border-radius: 6px;
    padding: 5px 14px;
    font-weight: 500;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #363658;
    border-color: #5b7fff;
}

QPushButton:pressed {
    background-color: #252540;
    border-color: #4a6ae0;
}

QPushButton:checked {
    background-color: #5b7fff;
    color: #ffffff;
    font-weight: 700;
    border: 1px solid #7090ff;
}

QPushButton:disabled {
    background-color: #222238;
    color: #55556e;
    border-color: #2c2c45;
}

/* --- Inputs, SpinBoxes, ComboBoxes --- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1e1e35;
    color: #e8e8f0;
    border: 1px solid #33334d;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #5b7fff;
    background-color: #222240;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #252540;
    color: #e8e8f0;
    border: 1px solid #3a3a58;
    selection-background-color: #5b7fff;
    border-radius: 4px;
    padding: 3px;
}

/* --- GroupBox (Cards) — Fundo elevado, borda sutil --- */
QGroupBox {
    font-weight: 600;
    font-size: 12px;
    color: #9090a8;
    background-color: #222240;
    border: 1px solid #2e2e4a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    left: 12px;
    color: #c0c0d0;
    font-weight: 700;
}

/* --- Listas --- */
QListWidget, QTableWidget {
    background-color: #1e1e35;
    border: 1px solid #2e2e4a;
    border-radius: 6px;
    color: #e8e8f0;
    outline: none;
}

QListWidget::item {
    padding: 7px 10px;
    border-radius: 4px;
    margin: 1px 3px;
}

QListWidget::item:hover {
    background-color: #2c2c48;
}

QListWidget::item:selected {
    background-color: #3a3a6a;
    color: #e8e8f0;
    border: none;
}

/* --- Scroll Bars — Finas e discretas --- */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    border-radius: 3px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #3a3a58;
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #5b7fff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 6px;
    border-radius: 3px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: #3a3a58;
    min-width: 24px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #5b7fff;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* --- Splitter --- */
QSplitter::handle {
    background-color: #2a2a45;
    width: 3px;
    height: 3px;
}

QSplitter::handle:hover {
    background-color: #5b7fff;
}

/* --- ProgressBar --- */
QProgressBar {
    background-color: #1e1e35;
    border: 1px solid #2e2e4a;
    border-radius: 5px;
    text-align: center;
    color: #e8e8f0;
    font-size: 10px;
    font-weight: 600;
}

QProgressBar::chunk {
    background-color: #4ade80;
    border-radius: 4px;
}

/* --- TextEdit (Console / Editor genérico) --- */
QTextEdit {
    background-color: #1a1a30;
    color: #d0d0e0;
    border: 1px solid #2e2e4a;
    border-radius: 6px;
    font-family: 'Consolas', 'Ubuntu Mono', monospace;
    font-size: 12px;
}

QTextEdit:focus {
    border: 1px solid #5b7fff;
}

/* --- PlainTextEdit (Editor G-code) --- */
QPlainTextEdit {
    background-color: #1a1a30;
    color: #dcdcec;
    border: 1px solid #2e2e4a;
    border-radius: 6px;
    font-family: 'Consolas', 'Ubuntu Mono', monospace;
    font-size: 12px;
    selection-background-color: #5b7fff;
}

QPlainTextEdit:focus {
    border: 1px solid #5b7fff;
}

/* --- QMessageBox --- */
QMessageBox {
    background-color: #252540;
}

QMessageBox QPushButton {
    min-width: 70px;
    padding: 6px 16px;
}

/* --- Tooltip --- */
QToolTip {
    background-color: #2c2c48;
    color: #e8e8f0;
    border: 1px solid #3a3a58;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 11px;
}
"""

ESTILO_CARD_PADRAO = (
    "QGroupBox {"
    "  font-weight: 600;"
    "  font-size: 12px;"
    "  color: #9090a8;"
    "  background-color: #222240;"
    "  border: 1px solid #2e2e4a;"
    "  border-radius: 8px;"
    "  margin-top: 12px;"
    "  padding-top: 14px;"
    "}"
    "QGroupBox::title {"
    "  subcontrol-origin: margin;"
    "  subcontrol-position: top left;"
    "  padding: 0 10px;"
    "  left: 12px;"
    "  color: #c0c0d0;"
    "  font-weight: 700;"
    "}"
)

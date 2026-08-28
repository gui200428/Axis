"""
Módulo de interface gráfica para a aba de Controle da Máquina (Plotter AXIS).

Fornece a interface visual completa para controle de máquinas CNC/Plotter via GRBL,
incluindo leitura digital de coordenadas (DRO), controlador jog com diagonais,
área de status e troca rápida de canetas (10 cores), botões de macros rápidas integrados,
visualizador 2D da mesa em tempo real, editor de G-code, console serial e gerenciador de arquivos.
"""

import os
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QTextEdit, QListWidget, QFrame,
    QGroupBox, QDoubleSpinBox, QSpinBox,
    QFileDialog, QSplitter, QSizePolicy,
    QProgressBar, QButtonGroup, QMessageBox, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtGui import QFont, QColor

from resources.controle_da_maquina.logica_controle_da_maquina import ControladorGrbl
from resources.controle_da_maquina.editor_gcode import EditorGcode
from resources.controle_da_maquina.gerenciador_canetas import GerenciadorCanetas
from resources.controle_da_maquina.gerenciador_area_desenho import GerenciadorAreaDesenho
from resources.controle_da_maquina.gerenciador_nivelamento import GerenciadorNivelamento
from resources.controle_da_maquina.visualizador_2d import Visualizador2DMaquina
from resources.macros.logica_macros import GerenciadorMacros
from resources.estilo.tema_escuro import ESTILO_CARD_PADRAO


class SpinBoxPassoAdaptativo(QDoubleSpinBox):
    """
    SpinBox especializado para passo CNC com incremento adaptativo.
    - Quando o valor for <= 1.0 (ex: 0.9, 0.8...), varia de 0.1 em 0.1.
    - Quando o valor for > 1.0 (ex: 2.0, 3.0...), varia de 1.0 em 1.0.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setRange(0.01, 500.0)
        self.setDecimals(2)
        self.setValue(1.0)
        self.setSingleStep(0.1)

    def stepBy(self, steps: int) -> None:
        valor_atual = self.value()
        if steps > 0:
            for _ in range(steps):
                if valor_atual < 0.95:
                    valor_atual = round(valor_atual + 0.1, 2)
                else:
                    valor_atual = round(valor_atual + 1.0, 2)
        elif steps < 0:
            for _ in range(abs(steps)):
                if valor_atual <= 1.05:
                    valor_atual = max(0.01, round(valor_atual - 0.1, 2))
                else:
                    valor_atual = round(valor_atual - 1.0, 2)

        valor_limitado = min(self.maximum(), max(self.minimum(), valor_atual))
        self.setValue(valor_limitado)


class AbaControleDaMaquina(QWidget):
    """
    Widget principal da aba de Controle da Máquina.
    """

    def __init__(
        self,
        controlador_grbl: Optional[ControladorGrbl] = None,
        gerenciador_canetas: Optional[GerenciadorCanetas] = None,
        gerenciador_macros: Optional[GerenciadorMacros] = None,
        gerenciador_area: Optional[GerenciadorAreaDesenho] = None,
        gerenciador_nivelamento: Optional[GerenciadorNivelamento] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controlador_grbl = controlador_grbl or ControladorGrbl()
        self.gerenciador_canetas = gerenciador_canetas or GerenciadorCanetas()
        self.gerenciador_macros = gerenciador_macros or GerenciadorMacros()
        self.gerenciador_area = gerenciador_area or GerenciadorAreaDesenho()
        self.gerenciador_nivelamento = gerenciador_nivelamento or GerenciadorNivelamento(
            gerenciador_area=self.gerenciador_area,
            gerenciador_canetas=self.gerenciador_canetas
        )

        # Injetar gerenciador de macros no controlador para expansão no G-code
        self.controlador_grbl.definir_gerenciador_macros(self.gerenciador_macros)
        # Injetar gerenciador de canetas para expansão de TROCAR_CANETA_X no G-code
        self.controlador_grbl.definir_gerenciador_canetas(self.gerenciador_canetas)
        # Injetar gerenciador de nivelamento para compensação Z-offset no G-code
        self.controlador_grbl.definir_gerenciador_nivelamento(self.gerenciador_nivelamento)

        self._diretorio_arquivos_atual: str = ""
        self._caminho_arquivo_carregado: str = ""
        self._nome_arquivo_carregado: str = ""
        self._conteudo_original_salvo: str = ""
        self._arquivo_modificado: bool = False

        self._configurar_layout_principal()
        self._conectar_sinais()

    # ------------------------------------------------------------------ #
    #                      MONTAGEM DO LAYOUT                             #
    # ------------------------------------------------------------------ #

    def _configurar_layout_principal(self) -> None:
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(8, 8, 8, 8)
        layout_principal.setSpacing(8)

        # Barra superior: Conexão Serial + Controles de Trabalho
        layout_principal.addWidget(self._criar_barra_superior())

        # Divisor horizontal de 3 painéis (Esquerdo: DRO+Caneta+Jog+Macros | Centro: 2D View + Editor | Direito: Arquivos)
        self.divisor_horizontal = QSplitter(Qt.Orientation.Horizontal)
        self.divisor_horizontal.addWidget(self._criar_painel_esquerdo())
        self.divisor_horizontal.addWidget(self._criar_painel_central())
        self.divisor_horizontal.addWidget(self._criar_painel_direito())

        self.divisor_horizontal.setStretchFactor(0, 0)
        self.divisor_horizontal.setStretchFactor(1, 4)
        self.divisor_horizontal.setStretchFactor(2, 1)

        # Proporção inicial calibrada para manter o menu esquerdo espaçoso e sem truncamento
        self.divisor_horizontal.setSizes([330, 720, 230])

        layout_principal.addWidget(self.divisor_horizontal, 1)

    # ------------------------------------------------------------------ #
    #                     BARRA SUPERIOR (CONEXÃO + JOB)                  #
    # ------------------------------------------------------------------ #

    def _criar_barra_superior(self) -> QFrame:
        frame_superior = QFrame()
        frame_superior.setStyleSheet(
            "QFrame { background-color: #222240; border: 1px solid #2e2e4a; border-radius: 8px; }"
            "QLabel { color: #9090a8; font-size: 11px; font-weight: 600; }"
        )
        layout_superior = QHBoxLayout(frame_superior)
        layout_superior.setContentsMargins(10, 6, 10, 6)
        layout_superior.setSpacing(6)

        # -- Seção 1: Conexão Serial --
        rotulo_porta = QLabel("Porta:")
        self.combo_portas = QComboBox()
        self.combo_portas.setMinimumWidth(125)
        self.combo_portas.setMaximumWidth(160)

        self.botao_atualizar_portas = QPushButton("🔄")
        self.botao_atualizar_portas.setFixedSize(28, 28)
        self.botao_atualizar_portas.setStyleSheet(
            "QPushButton { padding: 0px; font-size: 13px; font-weight: bold; border-radius: 4px; }"
        )
        self.botao_atualizar_portas.setToolTip("Atualizar portas seriais")
        self.botao_atualizar_portas.clicked.connect(self._atualizar_lista_portas)

        rotulo_baud = QLabel("Baud:")
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200", "250000"])
        self.combo_baud.setCurrentText("115200")
        self.combo_baud.setFixedWidth(92)

        self.botao_conectar = QPushButton("Conectar")
        self.botao_conectar.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; padding: 5px 12px; border: 1px solid #7090ff; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
        )
        self.botao_conectar.clicked.connect(self._alternar_conexao)

        self.rotulo_indicador_led = QLabel("●")
        self.rotulo_indicador_led.setStyleSheet("color: #f87171; font-size: 15px;")
        self.rotulo_indicador_led.setToolTip("Status da comunicação serial")

        layout_superior.addWidget(rotulo_porta)
        layout_superior.addWidget(self.combo_portas)
        layout_superior.addWidget(self.botao_atualizar_portas)
        layout_superior.addWidget(rotulo_baud)
        layout_superior.addWidget(self.combo_baud)
        layout_superior.addWidget(self.botao_conectar)
        layout_superior.addWidget(self.rotulo_indicador_led)

        # Separador vertical
        layout_superior.addWidget(self._criar_separador_vertical())

        # -- Seção 2: Controles de Execução de Trabalho --
        self.botao_iniciar_trabalho = QPushButton("▶ Iniciar")
        self.botao_iniciar_trabalho.setToolTip("Iniciar o envio do G-code atual")
        self.botao_iniciar_trabalho.setStyleSheet(
            "QPushButton { background-color: #22c55e; color: white; font-weight: bold; padding: 5px 12px; border: 1px solid #4ade80; }"
            "QPushButton:hover { background-color: #16a34a; }"
            "QPushButton:disabled { background-color: #1a2a22; color: #406050; border-color: #253530; }"
        )
        self.botao_iniciar_trabalho.clicked.connect(self._iniciar_execucao_trabalho)

        self.botao_pausar_trabalho = QPushButton("⏸ Pausar")
        self.botao_pausar_trabalho.setToolTip("Pausar a execução (Feed Hold) ou retomar")
        self.botao_pausar_trabalho.setStyleSheet(
            "QPushButton { background-color: #eab308; color: white; font-weight: bold; padding: 5px 12px; border: 1px solid #fbbf24; }"
            "QPushButton:hover { background-color: #ca8a04; }"
            "QPushButton:disabled { background-color: #2a2518; color: #6a5530; border-color: #3a3020; }"
        )
        self.botao_pausar_trabalho.setEnabled(False)
        self.botao_pausar_trabalho.clicked.connect(self._alternar_pausa_trabalho)

        self.botao_parar_trabalho = QPushButton("⏹ Parar")
        self.botao_parar_trabalho.setToolTip("Cancelar execução e abortar (Soft Reset)")
        self.botao_parar_trabalho.setStyleSheet(
            "QPushButton { background-color: #ef4444; color: white; font-weight: bold; padding: 5px 12px; border: 1px solid #f87171; }"
            "QPushButton:hover { background-color: #dc2626; }"
            "QPushButton:disabled { background-color: #2a1a1a; color: #6a4040; border-color: #3a2020; }"
        )
        self.botao_parar_trabalho.setEnabled(False)
        self.botao_parar_trabalho.clicked.connect(self._parar_execucao_trabalho)

        layout_superior.addWidget(self.botao_iniciar_trabalho)
        layout_superior.addWidget(self.botao_pausar_trabalho)
        layout_superior.addWidget(self.botao_parar_trabalho)

        # Separador vertical
        layout_superior.addWidget(self._criar_separador_vertical())

        # -- Seção 3: Ações Rápidas de Máquina --
        self.botao_auto_home = QPushButton("🏠 Home")
        self.botao_auto_home.setToolTip("Executar ciclo de homing ($H)")
        self.botao_auto_home.setStyleSheet("QPushButton { padding: 5px 8px; font-size: 11px; }")
        self.botao_auto_home.clicked.connect(self._executar_auto_home)

        self.botao_desbloquear = QPushButton("🔓 Desbloquear")
        self.botao_desbloquear.setToolTip("Desbloquear GRBL de alarme ($X)")
        self.botao_desbloquear.setStyleSheet("QPushButton { padding: 5px 8px; font-size: 11px; }")
        self.botao_desbloquear.clicked.connect(self._desbloquear_grbl)

        self.botao_reset_grbl = QPushButton("🔄 Reset")
        self.botao_reset_grbl.setToolTip("Enviar Soft-Reset (Ctrl+X)")
        self.botao_reset_grbl.setStyleSheet("QPushButton { padding: 5px 8px; font-size: 11px; }")
        self.botao_reset_grbl.clicked.connect(self._reiniciar_grbl)

        layout_superior.addWidget(self.botao_auto_home)
        layout_superior.addWidget(self.botao_desbloquear)
        layout_superior.addWidget(self.botao_reset_grbl)

        layout_superior.addStretch()

        # -- Seção 4: Progresso de Envio --
        self.rotulo_progresso_status = QLabel("Pronto")
        self.rotulo_progresso_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #9090a8;")

        self.barra_progresso = QProgressBar()
        self.barra_progresso.setFixedSize(110, 16)
        self.barra_progresso.setRange(0, 100)
        self.barra_progresso.setValue(0)
        self.barra_progresso.setTextVisible(False)

        layout_superior.addWidget(self.rotulo_progresso_status)
        layout_superior.addWidget(self.barra_progresso)

        self._atualizar_lista_portas()
        return frame_superior

    # ------------------------------------------------------------------ #
    #                    PAINEL ESQUERDO: DRO + CANETA + JOG + MACROS    #
    # ------------------------------------------------------------------ #

    def _criar_painel_esquerdo(self) -> QWidget:
        widget_painel = QWidget()
        widget_painel.setMinimumWidth(300)
        widget_painel.setMaximumWidth(400)

        # Scroll vertical para acomodar todos os controles em telas menores sem rolagem horizontal
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        conteudo = QWidget()
        conteudo.setObjectName("conteudo_painel_esquerdo")
        conteudo.setStyleSheet("QWidget#conteudo_painel_esquerdo { background: transparent; }")
        layout_conteudo = QVBoxLayout(conteudo)
        layout_conteudo.setContentsMargins(4, 4, 8, 8)
        layout_conteudo.setSpacing(10)

        # 1. Painel DRO (Digital Read Out)
        layout_conteudo.addWidget(self._criar_painel_dro())

        # 2. Painel Indicador de Caneta Ativa & Troca Rápida
        layout_conteudo.addWidget(self._criar_painel_caneta_ativa())

        # 3. Painel Jog Controller
        layout_conteudo.addWidget(self._criar_painel_jog())

        # 4. Painel de Macros Rápidas na Interface de Controle (Ponto 2)
        layout_conteudo.addWidget(self._criar_painel_macros_rapidas())

        layout_conteudo.addStretch()
        scroll.setWidget(conteudo)

        layout_externo = QVBoxLayout(widget_painel)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.addWidget(scroll)

        return widget_painel

    def _criar_painel_dro(self) -> QGroupBox:
        grupo_dro = QGroupBox("Coordenadas de Trabalho (DRO)")
        grupo_dro.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_dro = QVBoxLayout(grupo_dro)
        layout_dro.setContentsMargins(10, 14, 10, 10)
        layout_dro.setSpacing(6)

        self.rotulo_estado_dro = QLabel("DESCONECTADO")
        self.rotulo_estado_dro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_estado_dro.setFixedHeight(28)
        self.rotulo_estado_dro.setStyleSheet(
            "QLabel {"
            "  background-color: #1e1e35;"
            "  color: #6a6a82;"
            "  font-size: 12px;"
            "  font-weight: 800;"
            "  letter-spacing: 1.5px;"
            "  border: 1px solid #2e2e4a;"
            "  border-radius: 5px;"
            "}"
        )
        layout_dro.addWidget(self.rotulo_estado_dro)

        self.rotulo_posicao_x = QLabel("0.000")
        self.rotulo_posicao_y = QLabel("0.000")
        self.rotulo_posicao_z = QLabel("0.000")

        layout_dro.addWidget(self._criar_linha_eixo_dro("X", self.rotulo_posicao_x, "#f87171"))
        layout_dro.addWidget(self._criar_linha_eixo_dro("Y", self.rotulo_posicao_y, "#4ade80"))
        layout_dro.addWidget(self._criar_linha_eixo_dro("Z", self.rotulo_posicao_z, "#5b7fff"))

        layout_rodape = QHBoxLayout()
        layout_rodape.setSpacing(6)

        self.botao_zerar_tudo = QPushButton("Zerar XYZ")
        self.botao_zerar_tudo.setToolTip("Zerar todos os eixos (G10 L20 P1 X0 Y0 Z0)")
        self.botao_zerar_tudo.setStyleSheet("QPushButton { padding: 4px 10px; font-size: 11px; font-weight: 600; }")
        self.botao_zerar_tudo.clicked.connect(self._zerar_todos_eixos)

        self.rotulo_area_trabalho = QLabel("Mesa: 300 × 200 mm")
        self.rotulo_area_trabalho.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.rotulo_area_trabalho.setStyleSheet("font-size: 10px; color: #6a6a82;")

        layout_rodape.addWidget(self.botao_zerar_tudo)
        layout_rodape.addWidget(self.rotulo_area_trabalho, 1)

        layout_dro.addLayout(layout_rodape)
        return grupo_dro

    def _criar_linha_eixo_dro(self, nome_eixo: str, label_valor: QLabel, cor_eixo: str) -> QFrame:
        frame_eixo = QFrame()
        frame_eixo.setStyleSheet(
            "QFrame {"
            "  background-color: #1a1a30;"
            "  border: 1px solid #2e2e4a;"
            "  border-radius: 6px;"
            "}"
        )
        layout_eixo = QHBoxLayout(frame_eixo)
        layout_eixo.setContentsMargins(6, 4, 8, 4)
        layout_eixo.setSpacing(6)

        botao_zerar = QPushButton(f"{nome_eixo}₀")
        botao_zerar.setFixedSize(36, 28)
        botao_zerar.setToolTip(f"Zerar eixo {nome_eixo}")
        botao_zerar.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: #252540;"
            f"  color: {cor_eixo};"
            f"  font-size: 12px;"
            f"  font-weight: 800;"
            f"  border: 1px solid #33334d;"
            f"  border-radius: 5px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {cor_eixo}; color: white; }}"
        )
        botao_zerar.clicked.connect(lambda: self._zerar_eixo_individual(nome_eixo))

        label_valor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_valor.setStyleSheet(
            "QLabel {"
            "  font-family: 'Consolas', 'Ubuntu Mono', monospace;"
            "  font-size: 19px;"
            "  font-weight: 700;"
            "  color: #e8e8f0;"
            "  background-color: transparent;"
            "  border: none;"
            "}"
        )

        rotulo_unidade = QLabel("mm")
        rotulo_unidade.setStyleSheet("font-size: 10px; color: #6a6a82; border: none;")

        layout_eixo.addWidget(botao_zerar)
        layout_eixo.addWidget(label_valor, 1)
        layout_eixo.addWidget(rotulo_unidade)

        return frame_eixo

    def _criar_painel_caneta_ativa(self) -> QGroupBox:
        grupo_caneta = QGroupBox("Ferramenta / Caneta Ativa")
        grupo_caneta.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_caneta = QVBoxLayout(grupo_caneta)
        layout_caneta.setContentsMargins(10, 14, 10, 10)
        layout_caneta.setSpacing(8)

        # Linha 1: Status da caneta acoplada
        layout_status = QHBoxLayout()
        layout_status.setSpacing(8)

        self.indicador_cor_caneta = QLabel("  ●  ")
        self.indicador_cor_caneta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.indicador_cor_caneta.setFixedHeight(24)
        self.indicador_cor_caneta.setStyleSheet(
            "background-color: #3a3a58; color: white; border-radius: 4px; font-weight: bold; border: 1px solid #55556e;"
        )

        self.rotulo_nome_caneta = QLabel("Nenhuma Caneta Acoplada")
        self.rotulo_nome_caneta.setStyleSheet("font-weight: 700; font-size: 12px; color: #9090a8;")

        layout_status.addWidget(self.indicador_cor_caneta)
        layout_status.addWidget(self.rotulo_nome_caneta, 1)
        layout_caneta.addLayout(layout_status)

        # Linha 2: Dropdown de seleção de caneta ocupando toda a largura
        self.combo_selecao_caneta = QComboBox()
        self._atualizar_combo_canetas()
        layout_caneta.addWidget(self.combo_selecao_caneta)

        # Linha 3: Botões de ação distribuídos proporcionalmente
        layout_botoes = QHBoxLayout()
        layout_botoes.setSpacing(4)

        self.botao_definir_caneta_rapido = QPushButton("Definir")
        self.botao_definir_caneta_rapido.setToolTip("Define a caneta ativa manualmente sem mover a máquina")
        self.botao_definir_caneta_rapido.setStyleSheet("QPushButton { padding: 5px 6px; font-size: 11px; font-weight: 600; }")
        self.botao_definir_caneta_rapido.clicked.connect(self._ao_clicar_definir_caneta)

        self.botao_trocar_caneta_rapido = QPushButton("⚡ Trocar")
        self.botao_trocar_caneta_rapido.setToolTip("Executa a rotina G-code automática de troca para este slot")
        self.botao_trocar_caneta_rapido.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; padding: 5px 6px; font-size: 11px; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
        )
        self.botao_trocar_caneta_rapido.clicked.connect(self._ao_clicar_trocar_caneta_combo)

        self.botao_soltar_caneta_rapido = QPushButton("⏏ Devolver")
        self.botao_soltar_caneta_rapido.setToolTip("Devolver caneta ativa na baia")
        self.botao_soltar_caneta_rapido.setStyleSheet("QPushButton { padding: 5px 6px; font-size: 11px; font-weight: 600; }")
        self.botao_soltar_caneta_rapido.clicked.connect(self._ao_clicar_devolver_caneta)

        layout_botoes.addWidget(self.botao_definir_caneta_rapido, 1)
        layout_botoes.addWidget(self.botao_trocar_caneta_rapido, 1)
        layout_botoes.addWidget(self.botao_soltar_caneta_rapido, 1)

        layout_caneta.addLayout(layout_botoes)
        return grupo_caneta

    def _criar_painel_jog(self) -> QGroupBox:
        grupo_jog = QGroupBox("Controle Manual (Jog V0.13)")
        grupo_jog.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_jog = QVBoxLayout(grupo_jog)
        layout_jog.setContentsMargins(10, 14, 10, 10)
        layout_jog.setSpacing(6)

        grid_jog = QGridLayout()
        grid_jog.setSpacing(4)

        largura_botao = 50
        altura_botao = 32

        estilo_direcional = (
            "QPushButton { background-color: #2c2c48; color: #e8e8f0; font-weight: 700; font-size: 12px; border: 1px solid #3a3a58; border-radius: 6px; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; border-color: #7090ff; }"
            "QPushButton:pressed { background-color: #4a6ae0; }"
        )
        estilo_diagonal = (
            "QPushButton { background-color: #252540; color: #9090a8; font-weight: 700; font-size: 12px; border: 1px solid #33334d; border-radius: 6px; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; border-color: #7090ff; }"
        )
        estilo_eixo_z = (
            "QPushButton { background-color: #222248; color: #7da4ff; font-weight: 700; font-size: 12px; border: 1px solid #3a3a68; border-radius: 6px; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; }"
        )

        self.botao_jog_diag_no = QPushButton("↖")
        self.botao_jog_x_mais = QPushButton("X+")
        self.botao_jog_diag_ne = QPushButton("↗")
        self.botao_jog_z_menos = QPushButton("Z-")

        self.botao_jog_y_mais = QPushButton("Y+")
        self.botao_jog_centro = QPushButton("●")
        self.botao_jog_y_menos = QPushButton("Y-")
        self.botao_jog_z_mais = QPushButton("Z+")

        self.botao_jog_diag_so = QPushButton("↙")
        self.botao_jog_x_menos = QPushButton("X-")
        self.botao_jog_diag_se = QPushButton("↘")
        self.botao_jog_z_zero = QPushButton("Z₀")

        botoes = [
            (self.botao_jog_diag_no, 0, 0, estilo_diagonal, "Noroeste (X+ Y+)"),
            (self.botao_jog_x_mais, 0, 1, estilo_direcional, "Mover X+ (Fundo)"),
            (self.botao_jog_diag_ne, 0, 2, estilo_diagonal, "Nordeste (X+ Y-)"),
            (self.botao_jog_z_menos, 0, 3, estilo_eixo_z, "Subir Z- (Levantar)"),

            (self.botao_jog_y_mais, 1, 0, estilo_direcional, "Mover Y+ (Esquerda)"),
            (self.botao_jog_centro, 1, 1, estilo_diagonal, "Origem (0, 0)"),
            (self.botao_jog_y_menos, 1, 2, estilo_direcional, "Mover Y- (Direita)"),
            (self.botao_jog_z_mais, 1, 3, estilo_eixo_z, "Descer Z+ (Abaixar)"),

            (self.botao_jog_diag_so, 2, 0, estilo_diagonal, "Sudoeste (X- Y+)"),
            (self.botao_jog_x_menos, 2, 1, estilo_direcional, "Mover X- (Frente)"),
            (self.botao_jog_diag_se, 2, 2, estilo_diagonal, "Sudeste (X- Y-)"),
            (self.botao_jog_z_zero, 2, 3, estilo_eixo_z, "Zerar Eixo Z"),
        ]

        for b, linha, col, estilo, dica in botoes:
            b.setFixedSize(largura_botao, altura_botao)
            b.setStyleSheet(estilo)
            b.setToolTip(dica)
            grid_jog.addWidget(b, linha, col)

        layout_jog.addLayout(grid_jog)

        # Seletores de Passo Rápido
        layout_passos_rapidos = QHBoxLayout()
        layout_passos_rapidos.setSpacing(3)
        self.grupo_botoes_passo = QButtonGroup(self)

        valores_passo = [0.1, 1.0, 10.0, 50.0, 100.0]
        for valor in valores_passo:
            botao_passo = QPushButton(f"{valor:g}")
            botao_passo.setCheckable(True)
            botao_passo.setStyleSheet(
                "QPushButton { padding: 4px 2px; font-size: 11px; font-weight: 600; }"
                "QPushButton:checked { background-color: #5b7fff; color: white; border-color: #7090ff; }"
            )
            if valor == 1.0:
                botao_passo.setChecked(True)
            self.grupo_botoes_passo.addButton(botao_passo)
            layout_passos_rapidos.addWidget(botao_passo)
            botao_passo.clicked.connect(lambda _, v=valor: self.input_passo_xy.setValue(v))

        layout_jog.addLayout(layout_passos_rapidos)

        # Inputs Customizados
        layout_parametros = QGridLayout()
        layout_parametros.setSpacing(4)

        self.input_passo_xy = SpinBoxPassoAdaptativo()
        self.input_passo_xy.setValue(1.0)

        self.input_passo_z = SpinBoxPassoAdaptativo()
        self.input_passo_z.setValue(0.5)

        self.input_feed_rate = QSpinBox()
        self.input_feed_rate.setRange(1, 15000)
        self.input_feed_rate.setValue(2500)
        self.input_feed_rate.setSingleStep(100)

        layout_parametros.addWidget(QLabel("Passo XY:"), 0, 0)
        layout_parametros.addWidget(self.input_passo_xy, 0, 1)
        layout_parametros.addWidget(QLabel("Passo Z:"), 1, 0)
        layout_parametros.addWidget(self.input_passo_z, 1, 1)
        layout_parametros.addWidget(QLabel("Feed (mm/min):"), 2, 0)
        layout_parametros.addWidget(self.input_feed_rate, 2, 1)

        layout_jog.addLayout(layout_parametros)

        # Seção de Ações Rápidas de Caneta (Pen Down / Pen Up)
        layout_pen_acoes = QVBoxLayout()
        layout_pen_acoes.setSpacing(4)

        layout_pen_header = QHBoxLayout()
        layout_pen_header.setSpacing(4)
        lbl_pen_titulo = QLabel("Ações da Caneta:")
        lbl_pen_titulo.setStyleSheet("font-size: 11px; font-weight: 700; color: #9090a8;")

        self.badge_estado_caneta = QLabel("○ No Ar")
        self.badge_estado_caneta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_estado_caneta.setStyleSheet(
            "QLabel { background-color: #1e2640; color: #7da4ff; font-size: 10px; font-weight: 800; "
            "border: 1px solid #3b5998; border-radius: 4px; padding: 2px 6px; }"
        )
        layout_pen_header.addWidget(lbl_pen_titulo)
        layout_pen_header.addStretch()
        layout_pen_header.addWidget(self.badge_estado_caneta)
        layout_pen_acoes.addLayout(layout_pen_header)

        layout_pen_botoes = QHBoxLayout()
        layout_pen_botoes.setSpacing(4)

        self.botao_abaixar_caneta = QPushButton("⬇ Abaixar Caneta")
        self.botao_abaixar_caneta.setToolTip(
            "Abaixa a caneta suavemente até a altura calibrada (PEN_DOWN) com compensação de malha Z no ponto atual"
        )
        self.botao_abaixar_caneta.setFixedHeight(30)
        self.botao_abaixar_caneta.setStyleSheet(
            "QPushButton {"
            "  background-color: #1a3a2a; color: #4ade80; font-weight: 700; font-size: 11px;"
            "  border: 1px solid #22c55e; border-radius: 5px; padding: 3px 6px;"
            "}"
            "QPushButton:hover { background-color: #22c55e; color: white; }"
            "QPushButton:pressed { background-color: #16a34a; }"
        )
        self.botao_abaixar_caneta.clicked.connect(self._ao_clicar_abaixar_caneta)

        self.botao_hop_caneta = QPushButton("⇪ Salto / Hop")
        self.botao_hop_caneta.setToolTip(
            "Eleva a caneta apenas 2mm (PEN_HOP) para troca rápida de traço na escrita sem subir o caminho todo"
        )
        self.botao_hop_caneta.setFixedHeight(30)
        self.botao_hop_caneta.setStyleSheet(
            "QPushButton {"
            "  background-color: #24223d; color: #c084fc; font-weight: 700; font-size: 11px;"
            "  border: 1px solid #7c3aed; border-radius: 5px; padding: 3px 6px;"
            "}"
            "QPushButton:hover { background-color: #7c3aed; color: white; }"
            "QPushButton:pressed { background-color: #6d28d9; }"
        )
        self.botao_hop_caneta.clicked.connect(self._ao_clicar_hop_caneta)

        self.botao_levantar_caneta = QPushButton("⬆ Levantar Caneta")
        self.botao_levantar_caneta.setToolTip(
            "Eleva a caneta imediatamente para a altura segura no ar (PEN_UP / Z-Up seguro)"
        )
        self.botao_levantar_caneta.setFixedHeight(30)
        self.botao_levantar_caneta.setStyleSheet(
            "QPushButton {"
            "  background-color: #1a2238; color: #7da4ff; font-weight: 700; font-size: 11px;"
            "  border: 1px solid #3b5998; border-radius: 5px; padding: 3px 6px;"
            "}"
            "QPushButton:hover { background-color: #5b7fff; color: white; border-color: #7090ff; }"
            "QPushButton:pressed { background-color: #4a6ae0; }"
        )
        self.botao_levantar_caneta.clicked.connect(self._ao_clicar_levantar_caneta)

        layout_pen_botoes.addWidget(self.botao_abaixar_caneta, 1)
        layout_pen_botoes.addWidget(self.botao_hop_caneta, 1)
        layout_pen_botoes.addWidget(self.botao_levantar_caneta, 1)
        layout_pen_acoes.addLayout(layout_pen_botoes)

        layout_jog.addLayout(layout_pen_acoes)
        return grupo_jog

    def _criar_painel_macros_rapidas(self) -> QGroupBox:
        """
        Cria a seção de botões de macros rápidas de 1 clique na interface de controle.
        """
        grupo_macros = QGroupBox("⚡ Macros Rápidas")
        grupo_macros.setStyleSheet(ESTILO_CARD_PADRAO)
        self.layout_grid_macros = QGridLayout(grupo_macros)
        self.layout_grid_macros.setContentsMargins(8, 14, 8, 8)
        self.layout_grid_macros.setSpacing(4)

        self._atualizar_botoes_macros_rapidas()
        return grupo_macros

    def _atualizar_botoes_macros_rapidas(self) -> None:
        """Popula os botões da grade de macros rápidas."""
        # Limpa layout anterior se houver
        while self.layout_grid_macros.count():
            item = self.layout_grid_macros.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        macros = self.gerenciador_macros.obter_todas_macros()
        colunas = 2
        for i, macro in enumerate(macros):
            linha = i // colunas
            coluna = i % colunas
            botao = QPushButton(macro.nome)
            botao.setToolTip(macro.descricao)
            botao.setFixedHeight(30)
            botao.setStyleSheet(
                "QPushButton {"
                "  background-color: #252540; color: #e8e8f0; font-weight: 600; font-size: 11px;"
                "  border: 1px solid #33334d; border-radius: 5px; text-align: left; padding: 3px 6px;"
                "}"
                "QPushButton:hover { background-color: #5b7fff; color: white; border-color: #7090ff; }"
            )
            botao.clicked.connect(lambda _, m_id=macro.id: self._executar_macro_rapida(m_id))
            self.layout_grid_macros.addWidget(botao, linha, coluna)

    def _executar_macro_rapida(self, id_macro: str) -> None:
        """Executa a macro diretamente no controlador conectado."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de executar macros.")
            return

        sucesso = self.gerenciador_macros.executar_macro(id_macro, self.controlador_grbl)
        if sucesso:
            macro = self.gerenciador_macros.obter_macro(id_macro)
            nome = macro.nome if macro else id_macro
            self._adicionar_resposta_console(f"[SISTEMA] Macro '{nome}' enviada para execução.")

    # ------------------------------------------------------------------ #
    #            PAINEL CENTRAL: VISUALIZADOR 2D + EDITOR + CONSOLE      #
    # ------------------------------------------------------------------ #

    def _criar_painel_central(self) -> QWidget:
        widget_painel = QWidget()
        layout_painel = QVBoxLayout(widget_painel)
        layout_painel.setContentsMargins(0, 0, 0, 0)
        layout_painel.setSpacing(6)

        divisor_vertical = QSplitter(Qt.Orientation.Vertical)

        # 1. Visualizador 2D da Máquina
        self.visualizador_2d = Visualizador2DMaquina(
            gerenciador_canetas=self.gerenciador_canetas,
            gerenciador_macros=self.gerenciador_macros,
            gerenciador_area=self.gerenciador_area,
            parent=self
        )
        divisor_vertical.addWidget(self.visualizador_2d)

        # 2. Abas inferiores: Editor G-code e Console Serial
        abas_inferiores = QTabWidget()
        abas_inferiores.addTab(self._criar_secao_editor(), "📝 Editor G-code")
        abas_inferiores.addTab(self._criar_secao_console(), "💻 Console Serial")

        divisor_vertical.addWidget(abas_inferiores)

        divisor_vertical.setStretchFactor(0, 3)
        divisor_vertical.setStretchFactor(1, 2)

        layout_painel.addWidget(divisor_vertical)
        return widget_painel

    def _criar_secao_editor(self) -> QWidget:
        widget_editor = QWidget()
        layout_editor = QVBoxLayout(widget_editor)
        layout_editor.setContentsMargins(4, 4, 4, 4)
        layout_editor.setSpacing(4)

        layout_cabecalho = QHBoxLayout()
        layout_cabecalho.setContentsMargins(2, 2, 2, 2)
        layout_cabecalho.setSpacing(6)

        self.rotulo_arquivo_editor = QLabel("Nenhum arquivo carregado")
        self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #9090a8; font-weight: 500;")

        self.botao_salvar_editor = QPushButton("💾 Salvar")
        self.botao_salvar_editor.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
            "QPushButton:disabled { background-color: #222238; color: #55556e; border-color: #2e2e4a; }"
        )
        self.botao_salvar_editor.setEnabled(False)
        self.botao_salvar_editor.clicked.connect(self._salvar_gcode_editor)

        self.botao_limpar_editor = QPushButton("Limpar")
        self.botao_limpar_editor.clicked.connect(self._limpar_editor_gcode)

        layout_cabecalho.addWidget(self.rotulo_arquivo_editor)
        layout_cabecalho.addStretch()
        layout_cabecalho.addWidget(self.botao_salvar_editor)
        layout_cabecalho.addWidget(self.botao_limpar_editor)

        layout_editor.addLayout(layout_cabecalho)

        self.editor_gcode = EditorGcode()
        self.editor_gcode.setPlaceholderText(
            "Digite ou carregue o programa G-code aqui...\n\n"
            "Comandos de troca de caneta por slot:\n"
            "  TROCA_CANETA_01  ; troca inteligente (solta atual + pega slot 1)\n"
            "  TROCA_CANETA_02  ; troca inteligente para slot 2\n"
            "  SOLTAR_CANETA    ; devolve a caneta atual na baia\n\n"
            "Macros customizadas:\n"
            "  HOME\n"
            "  PARK\n"
        )
        self.editor_gcode.textChanged.connect(self._ao_alterar_texto_editor)
        layout_editor.addWidget(self.editor_gcode, 1)

        return widget_editor

    def _criar_secao_console(self) -> QWidget:
        widget_console = QWidget()
        layout_console = QVBoxLayout(widget_console)
        layout_console.setContentsMargins(4, 4, 4, 4)
        layout_console.setSpacing(4)

        layout_cabecalho = QHBoxLayout()
        self.botao_limpar_console = QPushButton("Limpar Console")
        self.botao_limpar_console.clicked.connect(self._limpar_console)
        layout_cabecalho.addStretch()
        layout_cabecalho.addWidget(self.botao_limpar_console)
        layout_console.addLayout(layout_cabecalho)

        self.area_console = QTextEdit()
        self.area_console.setReadOnly(True)
        # Estilo herdado do tema global (QTextEdit)
        layout_console.addWidget(self.area_console, 1)

        layout_entrada = QHBoxLayout()
        layout_entrada.setSpacing(4)

        self.input_comando = QLineEdit()
        self.input_comando.setPlaceholderText("Comando GRBL manual (ex: $$, $G, G0 X10, ?)...")
        self.input_comando.returnPressed.connect(self._enviar_comando_console)

        self.botao_enviar_comando = QPushButton("Enviar")
        self.botao_enviar_comando.setFixedWidth(65)
        self.botao_enviar_comando.clicked.connect(self._enviar_comando_console)

        layout_entrada.addWidget(self.input_comando)
        layout_entrada.addWidget(self.botao_enviar_comando)

        layout_console.addLayout(layout_entrada)
        return widget_console

    # ------------------------------------------------------------------ #
    #            PAINEL DIREITO: GERENCIADOR DE ARQUIVOS G-CODE          #
    # ------------------------------------------------------------------ #

    def _criar_painel_direito(self) -> QWidget:
        widget_painel = QWidget()
        widget_painel.setMinimumWidth(210)
        widget_painel.setMaximumWidth(280)
        layout_painel = QVBoxLayout(widget_painel)
        layout_painel.setContentsMargins(0, 0, 0, 0)
        layout_painel.setSpacing(6)

        grupo_arquivos = QGroupBox("Arquivos G-code")
        grupo_arquivos.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_grupo = QVBoxLayout(grupo_arquivos)
        layout_grupo.setContentsMargins(10, 12, 10, 10)
        layout_grupo.setSpacing(6)

        self.rotulo_diretorio_atual = QLabel("Nenhuma pasta selecionada")
        self.rotulo_diretorio_atual.setWordWrap(True)
        self.rotulo_diretorio_atual.setStyleSheet("font-size: 10px; color: #6a6a82;")

        self.botao_abrir_pasta = QPushButton("📁 Abrir Pasta...")
        self.botao_abrir_pasta.clicked.connect(self._abrir_pasta_arquivos)

        rotulo_dica = QLabel("Duplo clique para carregar:")
        rotulo_dica.setStyleSheet("font-size: 10px; color: #5b7fff;")

        self.lista_arquivos = QListWidget()
        self.lista_arquivos.itemDoubleClicked.connect(self._carregar_arquivo_selecionado_no_editor)

        layout_grupo.addWidget(self.rotulo_diretorio_atual)
        layout_grupo.addWidget(self.botao_abrir_pasta)
        layout_grupo.addWidget(rotulo_dica)
        layout_grupo.addWidget(self.lista_arquivos, 1)

        layout_painel.addWidget(grupo_arquivos)
        return widget_painel

    def _criar_separador_vertical(self) -> QFrame:
        separador = QFrame()
        separador.setFrameShape(QFrame.Shape.VLine)
        separador.setStyleSheet("color: #33334d;")
        return separador

    # ------------------------------------------------------------------ #
    #                      CONEXÃO DE SINAIS                              #
    # ------------------------------------------------------------------ #

    def _conectar_sinais(self) -> None:
        self.controlador_grbl.sinal_posicao_atualizada.connect(self._atualizar_posicao_dro)
        self.controlador_grbl.sinal_posicao_atualizada.connect(self.visualizador_2d.canvas.atualizar_posicao)
        self.controlador_grbl.sinal_status_atualizado.connect(self._atualizar_status_dro)
        self.controlador_grbl.sinal_conexao_alterada.connect(self._atualizar_estado_conexao)
        self.controlador_grbl.sinal_resposta_recebida.connect(self._adicionar_resposta_console)
        self.controlador_grbl.sinal_erro.connect(self._adicionar_erro_console)
        self.controlador_grbl.sinal_configuracao_recebida.connect(self._atualizar_area_trabalho)
        self.controlador_grbl.sinal_configuracao_recebida.connect(self.visualizador_2d.canvas.atualizar_limites_mesa)
        self.controlador_grbl.sinal_envio_arquivo_concluido.connect(self._ao_concluir_envio_trabalho)
        self.controlador_grbl.sinal_progresso_envio.connect(self._atualizar_progresso_trabalho)
        self.controlador_grbl.sinal_linha_enviada.connect(self.editor_gcode.definir_linha_enviando)
        self.controlador_grbl.sinal_pausa_alterada.connect(self._atualizar_estado_pausa)

        # Sinais Canetas, Macros e Área de Desenho
        self.gerenciador_canetas.sinal_caneta_alterada.connect(self._ao_alterar_caneta_ativa)
        self.gerenciador_canetas.sinal_caneta_alterada.connect(self.visualizador_2d.canvas.atualizar_caneta_ativa)
        self.gerenciador_canetas.sinal_slots_atualizados.connect(self._atualizar_combo_canetas)
        self.gerenciador_canetas.sinal_slots_atualizados.connect(self.visualizador_2d.canvas.update)
        self.gerenciador_macros.sinal_macros_atualizadas.connect(self._atualizar_botoes_macros_rapidas)
        self.gerenciador_area.sinal_area_alterada.connect(self.visualizador_2d.canvas.atualizar_area_desenho)

        # Jog Ortogonal
        self.botao_jog_x_mais.clicked.connect(lambda: self._mover_eixo("X", 1))
        self.botao_jog_x_menos.clicked.connect(lambda: self._mover_eixo("X", -1))
        self.botao_jog_y_mais.clicked.connect(lambda: self._mover_eixo("Y", 1))
        self.botao_jog_y_menos.clicked.connect(lambda: self._mover_eixo("Y", -1))
        self.botao_jog_z_menos.clicked.connect(lambda: self._mover_eixo("Z", -1))
        self.botao_jog_z_mais.clicked.connect(lambda: self._mover_eixo("Z", 1))
        self.botao_jog_z_zero.clicked.connect(lambda: self._zerar_eixo_individual("Z"))

        # Jog Diagonal
        self.botao_jog_diag_no.clicked.connect(lambda: self._mover_diagonal(1, 1))
        self.botao_jog_diag_ne.clicked.connect(lambda: self._mover_diagonal(1, -1))
        self.botao_jog_diag_so.clicked.connect(lambda: self._mover_diagonal(-1, 1))
        self.botao_jog_diag_se.clicked.connect(lambda: self._mover_diagonal(-1, -1))
        self.botao_jog_centro.clicked.connect(self._mover_para_origem_rapida)

    # ------------------------------------------------------------------ #
    #                         AÇÕES / SLOTS                               #
    # ------------------------------------------------------------------ #

    def _atualizar_lista_portas(self) -> None:
        self.combo_portas.clear()
        portas = self.controlador_grbl.listar_portas_disponiveis()
        if portas:
            self.combo_portas.addItems(portas)
        else:
            self.combo_portas.addItem("Nenhuma porta")

    def _alternar_conexao(self) -> None:
        if self.controlador_grbl.esta_conectado():
            self.controlador_grbl.desconectar()
        else:
            porta = self.combo_portas.currentText()
            if porta and porta != "Nenhuma porta":
                baud_rate = int(self.combo_baud.currentText())
                self.controlador_grbl.conectar(porta, baud_rate)

    def _mover_eixo(self, eixo: str, direcao: int) -> None:
        if eixo.upper() == "Z":
            passo = self.input_passo_z.value()
        else:
            passo = self.input_passo_xy.value()

        feed_rate = self.input_feed_rate.value()
        self.controlador_grbl.mover_eixo(eixo, direcao, passo, feed_rate)

    def _mover_diagonal(self, direcao_x: int, direcao_y: int) -> None:
        passo = self.input_passo_xy.value()
        feed_rate = self.input_feed_rate.value()
        self.controlador_grbl.mover_eixos_diagonais(direcao_x, direcao_y, passo, feed_rate)

    def _mover_para_origem_rapida(self) -> None:
        if self.controlador_grbl.esta_conectado():
            gcode_origem = "G90\nG0 Z10 F2000\nG0 X0 Y0 F3000"
            self.controlador_grbl.enviar_script_gcode(gcode_origem, nome="Mover para Origem Rápida")

    def _executar_auto_home(self) -> None:
        self.controlador_grbl.executar_auto_home()

    def _desbloquear_grbl(self) -> None:
        self.controlador_grbl.desbloquear_maquina()

    def _reiniciar_grbl(self) -> None:
        self.controlador_grbl.reiniciar_grbl()
        self._ao_concluir_envio_trabalho()
        self.rotulo_progresso_status.setText("Resetado")
        self.barra_progresso.setValue(0)

    def _zerar_eixo_individual(self, eixo: str) -> None:
        self.controlador_grbl.zerar_eixo(eixo)

    def _zerar_todos_eixos(self) -> None:
        self.controlador_grbl.zerar_coordenadas()

    def _ao_clicar_abaixar_caneta(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover a caneta.")
            return
        self.controlador_grbl.abaixar_caneta()

    def _ao_clicar_hop_caneta(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover a caneta.")
            return
        self.controlador_grbl.hop_caneta()

    def _ao_clicar_levantar_caneta(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover a caneta.")
            return
        self.controlador_grbl.levantar_caneta()

    def _atualizar_combo_canetas(self) -> None:
        self.combo_selecao_caneta.clear()
        slots = self.gerenciador_canetas.obter_todos_slots()
        for slot in slots:
            self.combo_selecao_caneta.addItem(f"[{slot.id:02d}] {slot.nome}", slot.id)

    def _ao_clicar_definir_caneta(self) -> None:
        id_caneta = self.combo_selecao_caneta.currentData()
        if not id_caneta:
            return
        self.gerenciador_canetas.definir_caneta_ativa(id_caneta)

    def _ao_clicar_trocar_caneta_combo(self) -> None:
        id_caneta = self.combo_selecao_caneta.currentData()
        if not id_caneta:
            return

        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de trocar de caneta.")
            return

        ativa_id = self.gerenciador_canetas.obter_caneta_ativa_id()
        gcode_troca = self.gerenciador_canetas.gerar_gcode_troca_completa(id_caneta)

        # Verificação crítica de segurança: se houver caneta acoplada e Z estiver baixo, elevar para Z seguro
        if ativa_id and ativa_id != id_caneta:
            slot_ativo = self.gerenciador_canetas.obter_slot(ativa_id)
            z_seguro = slot_ativo.z_seguro if slot_ativo else -4.0
            velocidade = slot_ativo.velocidade if slot_ativo else 3000
            if not self.controlador_grbl.caneta_esta_alta(z_seguro):
                z_atual = self.controlador_grbl.obter_posicao_z()
                self._adicionar_resposta_console(
                    f"[SEGURANÇA] Caneta baixa detectada (Z={z_atual:.2f}mm). "
                    f"Elevando para Z seguro ({z_seguro:.2f}mm) antes da troca..."
                )
                gcode_troca = f"G90\nG21\nG0 Z{z_seguro:.2f} F{velocidade}\n" + gcode_troca

        self.controlador_grbl.enviar_script_gcode(
            gcode_troca,
            nome=f"Trocar Caneta → [{id_caneta:02d}]",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(id_caneta)
        )

    def _ao_clicar_devolver_caneta(self) -> None:
        ativa_id = self.gerenciador_canetas.obter_caneta_ativa_id()
        if not ativa_id:
            # Fallback inteligente: se não houver caneta explicitamente ativa no estado, usar a selecionada no combo
            ativa_id = self.combo_selecao_caneta.currentData()
            if not ativa_id:
                QMessageBox.information(self, "Aviso", "Nenhuma caneta selecionada ou acoplada no cabeçote.")
                return

        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de soltar a caneta.")
            return

        slot = self.gerenciador_canetas.obter_slot(ativa_id)
        z_seguro = slot.z_seguro if slot else -4.0
        velocidade = slot.velocidade if slot else 3000

        gcode = self.gerenciador_canetas.gerar_gcode_soltar_caneta(ativa_id)

        # Verificação crítica de segurança: garantir que a caneta esteja no ar antes de mover para a baia
        if self.controlador_grbl.caneta_esta_abaixada():
            z_atual = self.controlador_grbl.obter_posicao_z()
            self._adicionar_resposta_console(
                f"[SEGURANÇA] Caneta baixa detectada (Z={z_atual:.2f}mm). "
                f"Elevando para Z seguro ({z_seguro:.2f}mm) antes de devolver..."
            )
            gcode = f"G90\nG21\nG0 Z{z_seguro:.2f} F{velocidade}\n" + gcode

        self.controlador_grbl.enviar_script_gcode(
            gcode,
            nome=f"Devolver Caneta [{ativa_id:02d}]",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(None)
        )

    @Slot(int, str, str)
    def _ao_alterar_caneta_ativa(self, id_caneta: int, nome: str, cor_hex: str) -> None:
        if id_caneta > 0:
            self.indicador_cor_caneta.setStyleSheet(
                f"background-color: {cor_hex}; color: #ffffff; border-radius: 4px; font-weight: bold; border: 1px solid #ffffff33;"
            )
            self.indicador_cor_caneta.setText(f"  {id_caneta}  ")
            self.rotulo_nome_caneta.setText(f"Caneta {id_caneta} - {nome}")
            self.rotulo_nome_caneta.setStyleSheet(f"font-weight: 800; font-size: 12px; color: {cor_hex};")
            # Sincroniza a seleção do combo caso o engate tenha vindo de outra aba ou script
            idx = self.combo_selecao_caneta.findData(id_caneta)
            if idx >= 0 and self.combo_selecao_caneta.currentIndex() != idx:
                self.combo_selecao_caneta.setCurrentIndex(idx)
        else:
            self.indicador_cor_caneta.setStyleSheet(
                "background-color: #3a3a58; color: white; border-radius: 4px; font-weight: bold; border: 1px solid #55556e;"
            )
            self.indicador_cor_caneta.setText("  ●  ")
            self.rotulo_nome_caneta.setText("Nenhuma Caneta Acoplada")
            self.rotulo_nome_caneta.setStyleSheet("font-weight: 700; font-size: 12px; color: #9090a8;")

        # Atualizar badge de estado Z com os novos limites da caneta
        self._atualizar_posicao_dro(*self.controlador_grbl.obter_posicao_atual())

    def _iniciar_execucao_trabalho(self) -> None:
        if self.controlador_grbl.esta_em_pausa():
            self.controlador_grbl.retomar_envio_arquivo()
            return

        conteudo = self.editor_gcode.toPlainText().strip()
        if not conteudo:
            self._adicionar_erro_console("Nenhum código G-code no editor para executar.")
            return

        if self._arquivo_modificado:
            self._adicionar_erro_console(
                "O código G-code foi modificado! Clique em '💾 Salvar' antes de enviar para a máquina."
            )
            self.rotulo_progresso_status.setText("Salve o arquivo!")
            return

        if not self.controlador_grbl.esta_conectado():
            self._adicionar_erro_console("A máquina não está conectada à porta serial.")
            return

        self.editor_gcode.setReadOnly(True)
        self.botao_iniciar_trabalho.setEnabled(False)
        self.botao_pausar_trabalho.setEnabled(True)
        self.botao_pausar_trabalho.setText("⏸ Pausar")
        self.botao_parar_trabalho.setEnabled(True)
        self.rotulo_progresso_status.setText("Executando...")
        self.barra_progresso.setValue(0)

        self.controlador_grbl.enviar_gcode_arquivo(conteudo)

    def _alternar_pausa_trabalho(self) -> None:
        self.controlador_grbl.alternar_pausa()

    def _parar_execucao_trabalho(self) -> None:
        self.controlador_grbl.cancelar_envio_arquivo()
        self._ao_concluir_envio_trabalho()
        self.rotulo_progresso_status.setText("Cancelado")
        self.barra_progresso.setValue(0)

    def _ao_alterar_texto_editor(self) -> None:
        conteudo_atual = self.editor_gcode.toPlainText()
        self.visualizador_2d.canvas.carregar_gcode_preview(conteudo_atual)

        if conteudo_atual != self._conteudo_original_salvo:
            self._arquivo_modificado = True
            nome = self._nome_arquivo_carregado if self._nome_arquivo_carregado else "Novo Arquivo"
            self.rotulo_arquivo_editor.setText(f"{nome} ● [Não salvo]")
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #fbbf24; font-weight: bold;")
            self.botao_salvar_editor.setEnabled(True)
        else:
            self._arquivo_modificado = False
            nome = self._nome_arquivo_carregado if self._nome_arquivo_carregado else "Editor"
            total_linhas = len(conteudo_atual.splitlines())
            self.rotulo_arquivo_editor.setText(f"{nome} ({total_linhas} linhas) ✔")
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #9090a8;")
            self.botao_salvar_editor.setEnabled(False)

    def _salvar_gcode_editor(self) -> None:
        conteudo = self.editor_gcode.toPlainText()

        if not self._caminho_arquivo_carregado:
            caminho_arquivo, _ = QFileDialog.getSaveFileName(
                self, "Salvar Arquivo G-code",
                os.path.join(self._diretorio_arquivos_atual or os.path.expanduser("~"), "desenho.gcode"),
                "Arquivos G-code (*.gcode *.nc *.ngc *.tap *.txt);;Todos os arquivos (*)"
            )
            if not caminho_arquivo:
                return
            self._caminho_arquivo_carregado = caminho_arquivo
            self._nome_arquivo_carregado = os.path.basename(caminho_arquivo)

        try:
            with open(self._caminho_arquivo_carregado, "w", encoding="utf-8") as arquivo:
                arquivo.write(conteudo)

            self._conteudo_original_salvo = conteudo
            self._arquivo_modificado = False
            total_linhas = len(conteudo.splitlines())
            self.rotulo_arquivo_editor.setText(f"{self._nome_arquivo_carregado} ({total_linhas} linhas) ✔ Salvo")
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #4ade80; font-weight: bold;")
            self.botao_salvar_editor.setEnabled(False)
            self._adicionar_resposta_console(f"[SISTEMA] Arquivo salvo: {self._nome_arquivo_carregado}")

            if self._diretorio_arquivos_atual:
                self._listar_arquivos_gcode(self._diretorio_arquivos_atual)

        except OSError as erro:
            self._adicionar_erro_console(f"Erro ao salvar arquivo: {str(erro)}")

    def _limpar_editor_gcode(self) -> None:
        self.editor_gcode.clear()
        self._caminho_arquivo_carregado = ""
        self._nome_arquivo_carregado = ""
        self._conteudo_original_salvo = ""
        self._arquivo_modificado = False
        self.rotulo_arquivo_editor.setText("Nenhum arquivo carregado")
        self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #9090a8;")
        self.botao_salvar_editor.setEnabled(False)
        self.visualizador_2d.canvas.carregar_gcode_preview("")

    def _limpar_console(self) -> None:
        self.area_console.clear()

    def _enviar_comando_console(self) -> None:
        comando = self.input_comando.text().strip()
        if comando:
            self.controlador_grbl.enviar_comando(comando)
            self.input_comando.clear()

    def _abrir_pasta_arquivos(self) -> None:
        diretorio = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Arquivos G-code")
        if diretorio:
            self._diretorio_arquivos_atual = diretorio
            nome_pasta = os.path.basename(diretorio)
            self.rotulo_diretorio_atual.setText(f"📂 {nome_pasta}")
            self._listar_arquivos_gcode(diretorio)

    def _listar_arquivos_gcode(self, diretorio: str) -> None:
        self.lista_arquivos.clear()
        extensoes_validas = (".gcode", ".nc", ".ngc", ".gc", ".tap", ".txt")
        try:
            arquivos = sorted(os.listdir(diretorio))
            for nome_arquivo in arquivos:
                if nome_arquivo.lower().endswith(extensoes_validas):
                    self.lista_arquivos.addItem(nome_arquivo)
        except OSError as erro:
            self._adicionar_erro_console(f"Erro ao listar pasta: {str(erro)}")

    def _carregar_arquivo_selecionado_no_editor(self) -> None:
        item_selecionado = self.lista_arquivos.currentItem()
        if item_selecionado is None:
            return

        caminho_completo = os.path.join(self._diretorio_arquivos_atual, item_selecionado.text())
        try:
            with open(caminho_completo, "r", encoding="utf-8", errors="replace") as arquivo:
                conteudo = arquivo.read()

            self._caminho_arquivo_carregado = caminho_completo
            self._nome_arquivo_carregado = item_selecionado.text()
            self._conteudo_original_salvo = conteudo
            self._arquivo_modificado = False

            self.editor_gcode.setPlainText(conteudo)
            total_linhas = len(conteudo.splitlines())
            self.rotulo_arquivo_editor.setText(f"{item_selecionado.text()} ({total_linhas} linhas) ✔")
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #9090a8;")
            self.botao_salvar_editor.setEnabled(False)
            self._adicionar_resposta_console(f"[SISTEMA] Arquivo carregado: {item_selecionado.text()}")
        except OSError as erro:
            self._adicionar_erro_console(f"Erro ao ler arquivo: {str(erro)}")

    @Slot(float, float, float)
    def _atualizar_posicao_dro(self, x: float, y: float, z: float) -> None:
        self.rotulo_posicao_x.setText(f"{x:.3f}")
        self.rotulo_posicao_y.setText(f"{y:.3f}")
        self.rotulo_posicao_z.setText(f"{z:.3f}")

        # Atualizar badge de estado da caneta (No Papel / No Ar)
        if hasattr(self, "badge_estado_caneta"):
            if self.controlador_grbl.caneta_esta_abaixada(z):
                self.badge_estado_caneta.setText(f"● No Papel ({z:+.2f}mm)")
                self.badge_estado_caneta.setStyleSheet(
                    "QLabel { background-color: #1a3a2a; color: #4ade80; font-size: 10px; font-weight: 800; "
                    "border: 1px solid #22c55e; border-radius: 4px; padding: 2px 6px; }"
                )
            else:
                self.badge_estado_caneta.setText(f"○ No Ar ({z:+.2f}mm)")
                self.badge_estado_caneta.setStyleSheet(
                    "QLabel { background-color: #1e2640; color: #7da4ff; font-size: 10px; font-weight: 800; "
                    "border: 1px solid #3b5998; border-radius: 4px; padding: 2px 6px; }"
                )

    @Slot(str)
    def _atualizar_status_dro(self, status: str) -> None:
        status_limpo = status.strip().upper()
        self.rotulo_estado_dro.setText(status_limpo)

        estilos_por_status = {
            "IDLE": "background-color: #1a3a2a; color: #4ade80; border: 1px solid #22c55e;",
            "RUN": "background-color: #1a2a55; color: #7da4ff; border: 1px solid #5b7fff;",
            "HOLD": "background-color: #3a2a1a; color: #fbbf24; border: 1px solid #eab308;",
            "ALARM": "background-color: #3a1a1a; color: #f87171; border: 1px solid #ef4444;",
            "CHECK": "background-color: #2a1a3a; color: #c084fc; border: 1px solid #a855f7;",
            "HOME": "background-color: #1a2a55; color: #7da4ff; border: 1px solid #5b7fff;",
        }

        estilo = estilos_por_status.get(
            status_limpo,
            "background-color: #1e1e35; color: #6a6a82; border: 1px solid #2e2e4a;"
        )
        self.rotulo_estado_dro.setStyleSheet(
            f"QLabel {{ {estilo} font-size: 12px; font-weight: 800; letter-spacing: 1.5px; border-radius: 5px; }}"
        )

    @Slot(bool)
    def _atualizar_estado_conexao(self, conectado: bool) -> None:
        if conectado:
            self.rotulo_indicador_led.setStyleSheet("color: #4ade80; font-size: 16px;")
            self.botao_conectar.setText("Desconectar")
            self.botao_conectar.setStyleSheet(
                "QPushButton { background-color: #3a3a58; color: white; border: 1px solid #55556e; }"
                "QPushButton:hover { background-color: #55556e; }"
            )
            self._atualizar_status_dro("IDLE")
        else:
            self.rotulo_indicador_led.setStyleSheet("color: #f87171; font-size: 16px;")
            self.botao_conectar.setText("Conectar")
            self.botao_conectar.setStyleSheet(
                "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; }"
                "QPushButton:hover { background-color: #4a6ae0; }"
            )
            self._atualizar_status_dro("DESCONECTADO")
            self._ao_concluir_envio_trabalho()

    @Slot(bool)
    def _atualizar_estado_pausa(self, em_pausa: bool) -> None:
        if em_pausa:
            self.botao_pausar_trabalho.setText("▶ Continuar")
            self.botao_pausar_trabalho.setStyleSheet(
                "QPushButton { background-color: #22c55e; color: white; font-weight: bold; padding: 5px 14px; border: 1px solid #4ade80; }"
            )
            self.rotulo_progresso_status.setText("Pausado")
        else:
            self.botao_pausar_trabalho.setText("⏸ Pausar")
            self.botao_pausar_trabalho.setStyleSheet(
                "QPushButton { background-color: #eab308; color: white; font-weight: bold; padding: 5px 14px; border: 1px solid #fbbf24; }"
            )
            if self.controlador_grbl.esta_enviando():
                self.rotulo_progresso_status.setText("Executando...")

    @Slot(int, int)
    def _atualizar_progresso_trabalho(self, linha_atual: int, total_linhas: int) -> None:
        if total_linhas > 0:
            percentual = int((linha_atual / total_linhas) * 100)
            self.barra_progresso.setValue(percentual)
            self.rotulo_progresso_status.setText(f"{linha_atual}/{total_linhas} ({percentual}%)")

    @Slot()
    def _ao_concluir_envio_trabalho(self) -> None:
        self.editor_gcode.setReadOnly(False)
        self.editor_gcode.definir_linha_enviando(-1)
        self.botao_iniciar_trabalho.setEnabled(True)
        self.botao_pausar_trabalho.setEnabled(False)
        self.botao_pausar_trabalho.setText("⏸ Pausar")
        self.botao_parar_trabalho.setEnabled(False)
        self.rotulo_progresso_status.setText("Concluído")
        self.barra_progresso.setValue(100)

    @Slot(str)
    def _adicionar_resposta_console(self, texto: str) -> None:
        if texto.startswith(">"):
            self.area_console.append(f'<span style="color: #7da4ff;">{texto}</span>')
        elif texto.startswith("[SISTEMA]"):
            self.area_console.append(f'<span style="color: #a78bfa;">{texto}</span>')
        elif texto == "ok":
            self.area_console.append(f'<span style="color: #4ade80;">{texto}</span>')
        else:
            self.area_console.append(f'<span style="color: #d0d0e0;">{texto}</span>')

    @Slot(str)
    def _adicionar_erro_console(self, mensagem_erro: str) -> None:
        self.area_console.append(f'<span style="color: #f87171; font-weight: bold;">[ERRO] {mensagem_erro}</span>')

    @Slot(float, float, float)
    def _atualizar_area_trabalho(self, limite_x: float, limite_y: float, limite_z: float) -> None:
        self.rotulo_area_trabalho.setText(f"Mesa: [{limite_x:.0f} × {limite_y:.0f} mm]")

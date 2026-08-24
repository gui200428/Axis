"""
Módulo de interface gráfica para a aba de Controle da Máquina.

Fornece a interface visual completa para controle de máquinas CNC/Laser via GRBL,
incluindo leitura digital de coordenadas (DRO), controlador jog com diagonais,
passos independentes para XY e Z com ajuste adaptativo, barra de ferramentas de execução
unificada (Play, Pause, Stop, Home, Unlock, Reset), editor de G-code com detecção e
bloqueio de alterações não salvas, console serial e gerenciador de arquivos.
"""

import os
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QTextEdit, QListWidget, QFrame,
    QGroupBox, QDoubleSpinBox, QSpinBox,
    QFileDialog, QSplitter, QSizePolicy,
    QProgressBar, QButtonGroup, QMessageBox
)
from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtGui import QFont, QColor

from resources.controle_da_maquina.logica_controle_da_maquina import ControladorGrbl
from resources.controle_da_maquina.editor_gcode import EditorGcode


class SpinBoxPassoAdaptativo(QDoubleSpinBox):
    """
    SpinBox especializado para passo CNC com incremento adaptativo.

    Ao navegar com as setas do teclado ou botões de passo:
    - Quando o valor for menor ou igual a 1.0 (ex: 0.9, 0.8...), varia de 0.1 em 0.1.
    - Quando o valor for superior a 1.0 (ex: 2.0, 3.0...), varia de 1.0 em 1.0.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Inicializa o SpinBox adaptativo com limites de passo CNC.

        Args:
            parent (QWidget, opcional): Widget pai.
        """
        super().__init__(parent)
        self.setRange(0.01, 500.0)
        self.setDecimals(2)
        self.setValue(1.0)
        self.setSingleStep(0.1)

    def stepBy(self, steps: int) -> None:
        """
        Aplica passos adaptativos ao alterar o valor via teclado ou setas.

        Args:
            steps (int): Quantidade e direção de passos (positivo ou negativo).
        """
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

    Responsável pela interface gráfica de controle e comunicação
    com a máquina CNC através do protocolo GRBL.
    """

    # Estilos CSS reutilizáveis
    ESTILO_PAINEL_CARD = (
        "QGroupBox {"
        "  font-weight: bold;"
        "  font-size: 11px;"
        "  color: #a1a1aa;"
        "  background-color: #1e1e24;"
        "  border: 1px solid #2e2e38;"
        "  border-radius: 6px;"
        "  margin-top: 10px;"
        "  padding-top: 10px;"
        "}"
        "QGroupBox::title {"
        "  subcontrol-origin: margin;"
        "  subcontrol-position: top left;"
        "  padding: 0 6px;"
        "  left: 10px;"
        "  color: #00f0ff;"
        "}"
    )

    def __init__(self) -> None:
        """
        Inicializa o widget da aba de Controle da Máquina,
        instancia o controlador GRBL e monta a interface.
        """
        super().__init__()
        self.controlador_grbl = ControladorGrbl()
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
        """
        Configura o layout raiz da aba com a barra superior de conexão/execução
        e a divisão horizontal dos 3 painéis de operação.
        """
        self.setStyleSheet(
            "QWidget { background-color: #16161a; color: #e4e4e7; font-family: 'Segoe UI', sans-serif; }"
            "QPushButton { background-color: #272730; color: #e4e4e7; border: 1px solid #3f3f4e; border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
            "QPushButton:hover { background-color: #383846; border-color: #525266; }"
            "QPushButton:pressed { background-color: #1f1f28; }"
            "QPushButton:disabled { background-color: #1a1a20; color: #555562; border-color: #282832; }"
            "QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {"
            "  background-color: #1f1f26; color: #f4f4f5; border: 1px solid #3f3f4e; border-radius: 4px; padding: 3px 6px; font-size: 11px;"
            "}"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView { background-color: #1f1f26; color: #f4f4f5; selection-background-color: #0284c7; }"
            "QSplitter::handle { background-color: #262630; width: 3px; height: 3px; }"
        )

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(6, 6, 6, 6)
        layout_principal.setSpacing(6)

        # Barra superior: Conexão + Barra de Ferramentas de Trabalho
        layout_principal.addWidget(self._criar_barra_superior())

        # Divisor horizontal de 3 painéis
        divisor_horizontal = QSplitter(Qt.Orientation.Horizontal)
        divisor_horizontal.addWidget(self._criar_painel_esquerdo())
        divisor_horizontal.addWidget(self._criar_painel_central())
        divisor_horizontal.addWidget(self._criar_painel_direito())

        # Proporções dos painéis: Esquerdo (~270px), Central (~600px), Direito (~220px)
        divisor_horizontal.setStretchFactor(0, 0)
        divisor_horizontal.setStretchFactor(1, 3)
        divisor_horizontal.setStretchFactor(2, 1)

        layout_principal.addWidget(divisor_horizontal, 1)

    # ------------------------------------------------------------------ #
    #                     BARRA SUPERIOR (CONEXÃO + JOB)                  #
    # ------------------------------------------------------------------ #

    def _criar_barra_superior(self) -> QFrame:
        """
        Cria a barra superior unificada de conexão serial e controle de execução.

        Returns:
            QFrame: Frame contendo conexão e barra de ferramentas de execução.
        """
        frame_superior = QFrame()
        frame_superior.setFrameShape(QFrame.Shape.StyledPanel)
        frame_superior.setStyleSheet(
            "QFrame { background-color: #1e1e24; border: 1px solid #2e2e38; border-radius: 6px; }"
            "QLabel { color: #a1a1aa; font-size: 11px; }"
        )
        layout_superior = QHBoxLayout(frame_superior)
        layout_superior.setContentsMargins(8, 6, 8, 6)
        layout_superior.setSpacing(6)

        # -- Seção 1: Conexão Serial --
        rotulo_porta = QLabel("Porta:")
        self.combo_portas = QComboBox()
        self.combo_portas.setMinimumWidth(110)
        self.combo_portas.setMaximumWidth(150)

        self.botao_atualizar_portas = QPushButton("⟳")
        self.botao_atualizar_portas.setFixedSize(26, 26)
        self.botao_atualizar_portas.setToolTip("Atualizar lista de portas seriais")
        self.botao_atualizar_portas.clicked.connect(self._atualizar_lista_portas)

        rotulo_baud = QLabel("Baud:")
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200", "250000"])
        self.combo_baud.setCurrentText("115200")
        self.combo_baud.setFixedWidth(75)

        self.botao_conectar = QPushButton("Conectar")
        self.botao_conectar.setMinimumWidth(80)
        self.botao_conectar.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; font-weight: bold; border: none; }"
            "QPushButton:hover { background-color: #0369a1; }"
        )
        self.botao_conectar.clicked.connect(self._alternar_conexao)

        self.rotulo_indicador_led = QLabel("●")
        self.rotulo_indicador_led.setStyleSheet("color: #ef4444; font-size: 14px;")
        self.rotulo_indicador_led.setToolTip("Status da comunicação serial")

        layout_superior.addWidget(rotulo_porta)
        layout_superior.addWidget(self.combo_portas)
        layout_superior.addWidget(self.botao_atualizar_portas)
        layout_superior.addWidget(rotulo_baud)
        layout_superior.addWidget(self.combo_baud)
        layout_superior.addWidget(self.botao_conectar)
        layout_superior.addWidget(self.rotulo_indicador_led)

        # Separador vertical
        separador_1 = self._criar_separador_vertical()
        layout_superior.addWidget(separador_1)

        # -- Seção 2: Controles de Execução de Trabalho (Play, Pause, Stop) --
        self.botao_iniciar_trabalho = QPushButton("▶ Iniciar")
        self.botao_iniciar_trabalho.setToolTip("Iniciar o envio do código G-code atual (requer arquivo salvo)")
        self.botao_iniciar_trabalho.setStyleSheet(
            "QPushButton { background-color: #10b981; color: white; font-weight: bold; padding: 5px 14px; }"
            "QPushButton:hover { background-color: #059669; }"
            "QPushButton:disabled { background-color: #1e3a2f; color: #557567; }"
        )
        self.botao_iniciar_trabalho.clicked.connect(self._iniciar_execucao_trabalho)

        self.botao_pausar_trabalho = QPushButton("⏸ Pausar")
        self.botao_pausar_trabalho.setToolTip("Pausar a execução (Feed Hold) ou retomar")
        self.botao_pausar_trabalho.setStyleSheet(
            "QPushButton { background-color: #f59e0b; color: white; font-weight: bold; padding: 5px 14px; }"
            "QPushButton:hover { background-color: #d97706; }"
            "QPushButton:disabled { background-color: #382c16; color: #6b5c3b; }"
        )
        self.botao_pausar_trabalho.setEnabled(False)
        self.botao_pausar_trabalho.clicked.connect(self._alternar_pausa_trabalho)

        self.botao_parar_trabalho = QPushButton("⏹ Parar")
        self.botao_parar_trabalho.setToolTip("Cancelar execução e abortar movimento (Soft Reset)")
        self.botao_parar_trabalho.setStyleSheet(
            "QPushButton { background-color: #ef4444; color: white; font-weight: bold; padding: 5px 14px; }"
            "QPushButton:hover { background-color: #dc2626; }"
            "QPushButton:disabled { background-color: #3d1c1c; color: #704444; }"
        )
        self.botao_parar_trabalho.setEnabled(False)
        self.botao_parar_trabalho.clicked.connect(self._parar_execucao_trabalho)

        layout_superior.addWidget(self.botao_iniciar_trabalho)
        layout_superior.addWidget(self.botao_pausar_trabalho)
        layout_superior.addWidget(self.botao_parar_trabalho)

        # Separador vertical
        separador_2 = self._criar_separador_vertical()
        layout_superior.addWidget(separador_2)

        # -- Seção 3: Ações de Máquina --
        self.botao_auto_home = QPushButton("🏠 Home ($H)")
        self.botao_auto_home.setToolTip("Executar ciclo de homing em todos os eixos")
        self.botao_auto_home.clicked.connect(self._executar_auto_home)

        self.botao_desbloquear = QPushButton("🔓 Desbloquear ($X)")
        self.botao_desbloquear.setToolTip("Desbloquear GRBL em estado de Alarme")
        self.botao_desbloquear.clicked.connect(self._desbloquear_grbl)

        self.botao_reset_grbl = QPushButton("🔄 Reset")
        self.botao_reset_grbl.setToolTip("Enviar Soft-Reset (Ctrl+X)")
        self.botao_reset_grbl.clicked.connect(self._reiniciar_grbl)

        layout_superior.addWidget(self.botao_auto_home)
        layout_superior.addWidget(self.botao_desbloquear)
        layout_superior.addWidget(self.botao_reset_grbl)

        layout_superior.addStretch()

        # -- Seção 4: Progresso de Envio --
        self.rotulo_progresso_status = QLabel("Pronto")
        self.rotulo_progresso_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa;")

        self.barra_progresso = QProgressBar()
        self.barra_progresso.setFixedSize(120, 14)
        self.barra_progresso.setRange(0, 100)
        self.barra_progresso.setValue(0)
        self.barra_progresso.setTextVisible(False)
        self.barra_progresso.setStyleSheet(
            "QProgressBar { background-color: #141418; border: 1px solid #333340; border-radius: 3px; }"
            "QProgressBar::chunk { background-color: #10b981; border-radius: 2px; }"
        )

        layout_superior.addWidget(self.rotulo_progresso_status)
        layout_superior.addWidget(self.barra_progresso)

        self._atualizar_lista_portas()
        return frame_superior

    # ------------------------------------------------------------------ #
    #                    PAINEL ESQUERDO: DRO + JOG                       #
    # ------------------------------------------------------------------ #

    def _criar_painel_esquerdo(self) -> QWidget:
        """
        Cria o painel esquerdo contendo o DRO (Digital Read Out)
        e o Joystick (Jog Controller) alinhado com passos independentes XY e Z.

        Returns:
            QWidget: Widget do painel esquerdo.
        """
        widget_painel = QWidget()
        widget_painel.setMinimumWidth(265)
        widget_painel.setMaximumWidth(325)
        layout_painel = QVBoxLayout(widget_painel)
        layout_painel.setContentsMargins(0, 0, 0, 0)
        layout_painel.setSpacing(6)

        # 1. Painel DRO (Digital Read Out)
        layout_painel.addWidget(self._criar_painel_dro())

        # 2. Painel Jog Controller
        layout_painel.addWidget(self._criar_painel_jog())

        layout_painel.addStretch()
        return widget_painel

    def _criar_painel_dro(self) -> QGroupBox:
        """
        Cria o painel DRO (Digital Read Out) com display de alta visibilidade
        para as coordenadas X, Y, Z e o estado atual do controlador GRBL.

        Returns:
            QGroupBox: Grupo formatado com o visor digital de coordenadas.
        """
        grupo_dro = QGroupBox("Controller State (DRO)")
        grupo_dro.setStyleSheet(self.ESTILO_PAINEL_CARD)
        layout_dro = QVBoxLayout(grupo_dro)
        layout_dro.setContentsMargins(8, 10, 8, 8)
        layout_dro.setSpacing(6)

        # Banner de Estado da Máquina (ex: IDLE, RUN, ALARM)
        self.rotulo_estado_dro = QLabel("DESCONECTADO")
        self.rotulo_estado_dro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_estado_dro.setFixedHeight(28)
        self.rotulo_estado_dro.setStyleSheet(
            "QLabel {"
            "  background-color: #18181b;"
            "  color: #71717a;"
            "  font-size: 13px;"
            "  font-weight: 900;"
            "  letter-spacing: 1px;"
            "  border: 1px solid #27272a;"
            "  border-radius: 4px;"
            "}"
        )
        layout_dro.addWidget(self.rotulo_estado_dro)

        # Display LCD de Coordenadas X, Y, Z
        self.rotulo_posicao_x = QLabel("0.000")
        self.rotulo_posicao_y = QLabel("0.000")
        self.rotulo_posicao_z = QLabel("0.000")

        # Montagem das linhas individuais para X, Y e Z
        layout_dro.addWidget(self._criar_linha_eixo_dro("X", self.rotulo_posicao_x))
        layout_dro.addWidget(self._criar_linha_eixo_dro("Y", self.rotulo_posicao_y))
        layout_dro.addWidget(self._criar_linha_eixo_dro("Z", self.rotulo_posicao_z))

        # Rodapé do DRO com informações de limite de trabalho
        self.rotulo_area_trabalho = QLabel("Área: Não calibrada")
        self.rotulo_area_trabalho.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_area_trabalho.setStyleSheet("font-size: 10px; color: #71717a; margin-top: 2px;")
        layout_dro.addWidget(self.rotulo_area_trabalho)

        return grupo_dro

    def _criar_linha_eixo_dro(self, nome_eixo: str, label_valor: QLabel) -> QFrame:
        """
        Cria a linha de exibição digital para um eixo no painel DRO,
        contendo o botão de zeramento rápido e a caixa digital com número ciano.

        Args:
            nome_eixo (str): Nome do eixo ('X', 'Y' ou 'Z').
            label_valor (QLabel): Label onde a coordenada será atualizada.

        Returns:
            QFrame: Frame formatado para a linha do eixo.
        """
        frame_eixo = QFrame()
        frame_eixo.setStyleSheet(
            "QFrame {"
            "  background-color: #121217;"
            "  border: 1px solid #22222d;"
            "  border-radius: 5px;"
            "}"
        )
        layout_eixo = QHBoxLayout(frame_eixo)
        layout_eixo.setContentsMargins(4, 3, 6, 3)
        layout_eixo.setSpacing(6)

        # Botão de zerar eixo específico (ex: X0, Y0, Z0)
        botao_zerar = QPushButton(f"{nome_eixo}₀")
        botao_zerar.setFixedSize(36, 30)
        botao_zerar.setToolTip(f"Zerar coordenada de trabalho do eixo {nome_eixo} (G10 L20 P1 {nome_eixo}0)")
        botao_zerar.setStyleSheet(
            "QPushButton {"
            "  background-color: #1e293b;"
            "  color: #38bdf8;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  border: 1px solid #0284c7;"
            "  border-radius: 4px;"
            "}"
            "QPushButton:hover { background-color: #0369a1; color: white; }"
        )
        botao_zerar.clicked.connect(lambda: self._zerar_eixo_individual(nome_eixo))

        # Configuração do Label de Coordenada com estilo Digital
        label_valor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_valor.setStyleSheet(
            "QLabel {"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 20px;"
            "  font-weight: bold;"
            "  color: #00f0ff;"
            "  background-color: transparent;"
            "  border: none;"
            "  padding-right: 4px;"
            "}"
        )

        rotulo_unidade = QLabel("mm")
        rotulo_unidade.setStyleSheet("font-size: 10px; color: #52525b; border: none;")

        layout_eixo.addWidget(botao_zerar)
        layout_eixo.addWidget(label_valor, 1)
        layout_eixo.addWidget(rotulo_unidade)

        return frame_eixo

    def _criar_painel_jog(self) -> QGroupBox:
        """
        Cria o painel Jog Controller com matriz de botões 4x3 perfeitamente alinhada,
        passos diferenciados para XY e Z com ajuste adaptativo e velocidade (feed rate).

        Returns:
            QGroupBox: Grupo formatado do Jog Controller.
        """
        grupo_jog = QGroupBox("Jog Controller")
        grupo_jog.setStyleSheet(self.ESTILO_PAINEL_CARD)
        layout_jog = QVBoxLayout(grupo_jog)
        layout_jog.setContentsMargins(8, 10, 8, 8)
        layout_jog.setSpacing(6)

        # -- Matriz 4x3 de Movimentação --
        grid_jog = QGridLayout()
        grid_jog.setSpacing(3)

        largura_botao = 54
        altura_botao = 38

        # Estilos dos botões de Jog
        estilo_botao_direcional = (
            "QPushButton {"
            "  background-color: #272732;"
            "  color: #f4f4f5;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  border: 1px solid #3e3e4f;"
            "  border-radius: 4px;"
            "}"
            "QPushButton:hover { background-color: #0284c7; color: white; border-color: #38bdf8; }"
            "QPushButton:pressed { background-color: #0369a1; }"
        )

        estilo_botao_diagonal = (
            "QPushButton {"
            "  background-color: #20202a;"
            "  color: #a1a1aa;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  border: 1px solid #333342;"
            "  border-radius: 4px;"
            "}"
            "QPushButton:hover { background-color: #0284c7; color: white; border-color: #38bdf8; }"
        )

        estilo_botao_eixo_z = (
            "QPushButton {"
            "  background-color: #2b2b3a;"
            "  color: #38bdf8;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  border: 1px solid #0284c7;"
            "  border-radius: 4px;"
            "}"
            "QPushButton:hover { background-color: #0284c7; color: white; }"
        )

        # Criação dos botões da matriz
        self.botao_jog_diag_no = QPushButton("↖")  # X- Y+
        self.botao_jog_y_mais = QPushButton("Y+")
        self.botao_jog_diag_ne = QPushButton("↗")  # X+ Y+
        self.botao_jog_z_mais = QPushButton("Z+")

        self.botao_jog_x_menos = QPushButton("X-")
        self.botao_jog_centro = QPushButton("●")
        self.botao_jog_x_mais = QPushButton("X+")
        self.botao_jog_z_menos = QPushButton("Z-")

        self.botao_jog_diag_so = QPushButton("↙")  # X- Y-
        self.botao_jog_y_menos = QPushButton("Y-")
        self.botao_jog_diag_se = QPushButton("↘")  # X+ Y-
        self.botao_jog_z_zero = QPushButton("Z₀")

        botoes_matriz = [
            (self.botao_jog_diag_no, 0, 0, estilo_botao_diagonal, "Mover Noroeste (X- Y+)"),
            (self.botao_jog_y_mais, 0, 1, estilo_botao_direcional, "Mover Y+"),
            (self.botao_jog_diag_ne, 0, 2, estilo_botao_diagonal, "Mover Nordeste (X+ Y+)"),
            (self.botao_jog_z_mais, 0, 3, estilo_botao_eixo_z, "Subir Z+"),

            (self.botao_jog_x_menos, 1, 0, estilo_botao_direcional, "Mover X-"),
            (self.botao_jog_centro, 1, 1, estilo_botao_diagonal, "Referência / Centro"),
            (self.botao_jog_x_mais, 1, 2, estilo_botao_direcional, "Mover X+"),
            (self.botao_jog_z_menos, 1, 3, estilo_botao_eixo_z, "Descer Z-"),

            (self.botao_jog_diag_so, 2, 0, estilo_botao_diagonal, "Mover Sudoeste (X- Y-)"),
            (self.botao_jog_y_menos, 2, 1, estilo_botao_direcional, "Mover Y-"),
            (self.botao_jog_diag_se, 2, 2, estilo_botao_diagonal, "Mover Sudeste (X+ Y-)"),
            (self.botao_jog_z_zero, 2, 3, estilo_botao_eixo_z, "Zerar Eixo Z"),
        ]

        for botao, linha, coluna, estilo, dica in botoes_matriz:
            botao.setFixedSize(largura_botao, altura_botao)
            botao.setStyleSheet(estilo)
            botao.setToolTip(dica)
            grid_jog.addWidget(botao, linha, coluna)

        layout_jog.addLayout(grid_jog)

        # -- Parâmetros de Passo Diferenciados (XY e Z) com Incremento Adaptativo --
        rotulo_passo_header = QLabel("Passos de Movimento (Adaptativo):")
        rotulo_passo_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa; margin-top: 4px;")
        layout_jog.addWidget(rotulo_passo_header)

        # Botões de passo rápido para XY
        layout_botoes_passo = QHBoxLayout()
        layout_botoes_passo.setSpacing(3)
        self.grupo_botoes_passo = QButtonGroup(self)

        valores_passo = [0.1, 1.0, 10.0, 50.0, 100.0]
        for valor in valores_passo:
            texto = f"{valor:g}"
            botao_passo = QPushButton(texto)
            botao_passo.setCheckable(True)
            botao_passo.setStyleSheet(
                "QPushButton { padding: 3px 2px; font-size: 10px; }"
                "QPushButton:checked { background-color: #0284c7; color: white; font-weight: bold; border-color: #38bdf8; }"
            )
            if valor == 1.0:
                botao_passo.setChecked(True)
            self.grupo_botoes_passo.addButton(botao_passo)
            layout_botoes_passo.addWidget(botao_passo)
            botao_passo.clicked.connect(lambda _, v=valor: self.input_passo_xy.setValue(v))

        layout_jog.addLayout(layout_botoes_passo)

        # Inputs de Passo Customizado (XY e Z) e Velocidade (Feed Rate)
        layout_parametros = QGridLayout()
        layout_parametros.setSpacing(4)

        rotulo_passo_xy = QLabel("Passo XY (mm):")
        rotulo_passo_xy.setToolTip("Distância de cada clique no plano XY (variação de 0.1 abaixo de 1.0)")
        self.input_passo_xy = SpinBoxPassoAdaptativo()
        self.input_passo_xy.setValue(1.0)

        rotulo_passo_z = QLabel("Passo Z (mm):")
        rotulo_passo_z.setToolTip("Distância de cada clique no eixo Z (variação de 0.1 abaixo de 1.0)")
        self.input_passo_z = SpinBoxPassoAdaptativo()
        self.input_passo_z.setValue(0.5)

        rotulo_feed = QLabel("Feed (mm/min):")
        self.input_feed_rate = QSpinBox()
        self.input_feed_rate.setRange(1, 15000)
        self.input_feed_rate.setValue(1000)
        self.input_feed_rate.setSingleStep(100)

        layout_parametros.addWidget(rotulo_passo_xy, 0, 0)
        layout_parametros.addWidget(self.input_passo_xy, 0, 1)
        layout_parametros.addWidget(rotulo_passo_z, 1, 0)
        layout_parametros.addWidget(self.input_passo_z, 1, 1)
        layout_parametros.addWidget(rotulo_feed, 2, 0)
        layout_parametros.addWidget(self.input_feed_rate, 2, 1)

        layout_jog.addLayout(layout_parametros)

        return grupo_jog

    # ------------------------------------------------------------------ #
    #                PAINEL CENTRAL: EDITOR G-CODE + CONSOLE             #
    # ------------------------------------------------------------------ #

    def _criar_painel_central(self) -> QWidget:
        """
        Cria o painel central com o editor de G-code e o console serial GRBL
        separados por um divisor vertical redimensionável.

        Returns:
            QWidget: Widget do painel central.
        """
        widget_painel = QWidget()
        layout_painel = QVBoxLayout(widget_painel)
        layout_painel.setContentsMargins(0, 0, 0, 0)
        layout_painel.setSpacing(0)

        divisor_vertical = QSplitter(Qt.Orientation.Vertical)

        # 1. Seção do Editor G-code
        divisor_vertical.addWidget(self._criar_secao_editor())

        # 2. Seção do Console Serial
        divisor_vertical.addWidget(self._criar_secao_console())

        divisor_vertical.setStretchFactor(0, 3)
        divisor_vertical.setStretchFactor(1, 1)

        layout_painel.addWidget(divisor_vertical)
        return widget_painel

    def _criar_secao_editor(self) -> QFrame:
        """
        Cria o container do Editor de G-code com cabeçalho de status,
        indicativo de alterações pendentes de salvamento e botões de ação.

        Returns:
            QFrame: Frame contendo o editor e controles associados.
        """
        frame_editor = QFrame()
        frame_editor.setStyleSheet(
            "QFrame { background-color: #18181d; border: 1px solid #2e2e38; border-radius: 6px; }"
        )
        layout_editor = QVBoxLayout(frame_editor)
        layout_editor.setContentsMargins(6, 6, 6, 6)
        layout_editor.setSpacing(4)

        # Cabeçalho do Editor
        layout_cabecalho = QHBoxLayout()
        layout_cabecalho.setContentsMargins(2, 2, 2, 2)
        layout_cabecalho.setSpacing(6)

        rotulo_titulo = QLabel("📝 Editor G-code")
        rotulo_titulo.setStyleSheet("font-weight: bold; font-size: 12px; color: #00f0ff;")

        self.rotulo_arquivo_editor = QLabel("Nenhum arquivo carregado")
        self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #71717a;")

        # Botão de Salvar G-code
        self.botao_salvar_editor = QPushButton("💾 Salvar")
        self.botao_salvar_editor.setToolTip("Salvar alterações no arquivo G-code atual")
        self.botao_salvar_editor.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; font-weight: bold; border: none; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #0369a1; }"
            "QPushButton:disabled { background-color: #1f2937; color: #4b5563; }"
        )
        self.botao_salvar_editor.setEnabled(False)
        self.botao_salvar_editor.clicked.connect(self._salvar_gcode_editor)

        self.botao_limpar_editor = QPushButton("Limpar")
        self.botao_limpar_editor.setToolTip("Limpar conteúdo do editor")
        self.botao_limpar_editor.clicked.connect(self._limpar_editor_gcode)

        layout_cabecalho.addWidget(rotulo_titulo)
        layout_cabecalho.addWidget(self.rotulo_arquivo_editor)
        layout_cabecalho.addStretch()
        layout_cabecalho.addWidget(self.botao_salvar_editor)
        layout_cabecalho.addWidget(self.botao_limpar_editor)

        layout_editor.addLayout(layout_cabecalho)

        # Instância do Editor G-code com linhas e realce
        self.editor_gcode = EditorGcode()
        self.editor_gcode.setPlaceholderText(
            "Digite ou carregue o programa G-code aqui...\n"
            "Exemplo:\n"
            "G21 ; milímetros\n"
            "G90 ; coordenadas absolutas\n"
            "G0 Z5 ; mover altura de segurança\n"
            "G0 X0 Y0 ; mover para a origem\n"
            "M3 S1000 ; ligar spindle/laser\n"
        )
        self.editor_gcode.textChanged.connect(self._ao_alterar_texto_editor)
        layout_editor.addWidget(self.editor_gcode, 1)

        return frame_editor

    def _criar_secao_console(self) -> QFrame:
        """
        Cria o container do Console Serial para monitoramento bidirecional do GRBL.

        Returns:
            QFrame: Frame contendo o console serial e linha de entrada de comando.
        """
        frame_console = QFrame()
        frame_console.setStyleSheet(
            "QFrame { background-color: #18181d; border: 1px solid #2e2e38; border-radius: 6px; }"
        )
        layout_console = QVBoxLayout(frame_console)
        layout_console.setContentsMargins(6, 6, 6, 6)
        layout_console.setSpacing(4)

        # Cabeçalho do Console
        layout_cabecalho = QHBoxLayout()
        layout_cabecalho.setContentsMargins(2, 2, 2, 2)

        rotulo_titulo = QLabel("💻 Console Serial")
        rotulo_titulo.setStyleSheet("font-weight: bold; font-size: 12px; color: #00f0ff;")

        self.botao_limpar_console = QPushButton("Limpar")
        self.botao_limpar_console.setToolTip("Limpar histórico do console serial")
        self.botao_limpar_console.clicked.connect(self._limpar_console)

        layout_cabecalho.addWidget(rotulo_titulo)
        layout_cabecalho.addStretch()
        layout_cabecalho.addWidget(self.botao_limpar_console)

        layout_console.addLayout(layout_cabecalho)

        # Área de texto do console
        self.area_console = QTextEdit()
        self.area_console.setReadOnly(True)
        self.area_console.setStyleSheet(
            "QTextEdit {"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 11px;"
            "  background-color: #121216;"
            "  color: #b0b0bc;"
            "  border: 1px solid #2c2c38;"
            "  border-radius: 4px;"
            "}"
        )
        self.area_console.setMaximumHeight(180)
        layout_console.addWidget(self.area_console, 1)

        # Linha de entrada para comandos manuais
        layout_entrada = QHBoxLayout()
        layout_entrada.setSpacing(4)

        self.input_comando = QLineEdit()
        self.input_comando.setPlaceholderText("Comando GRBL manual (ex: $$, $G, G0 X10, ?)...")
        self.input_comando.setStyleSheet(
            "QLineEdit {"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 11px;"
            "  background-color: #121216;"
            "  color: #f4f4f5;"
            "  border: 1px solid #3f3f4e;"
            "  padding: 4px;"
            "}"
        )
        self.input_comando.returnPressed.connect(self._enviar_comando_console)

        self.botao_enviar_comando = QPushButton("Enviar")
        self.botao_enviar_comando.setFixedWidth(65)
        self.botao_enviar_comando.clicked.connect(self._enviar_comando_console)

        layout_entrada.addWidget(self.input_comando)
        layout_entrada.addWidget(self.botao_enviar_comando)

        layout_console.addLayout(layout_entrada)
        return frame_console

    # ------------------------------------------------------------------ #
    #            PAINEL DIREITO: GERENCIADOR DE ARQUIVOS G-CODE          #
    # ------------------------------------------------------------------ #

    def _criar_painel_direito(self) -> QWidget:
        """
        Cria o painel direito com o gerenciador de arquivos de G-code,
        permitindo selecionar pastas e listar programas carregados com duplo clique.

        Returns:
            QWidget: Widget do painel direito.
        """
        widget_painel = QWidget()
        widget_painel.setMinimumWidth(200)
        widget_painel.setMaximumWidth(280)
        layout_painel = QVBoxLayout(widget_painel)
        layout_painel.setContentsMargins(0, 0, 0, 0)
        layout_painel.setSpacing(6)

        grupo_arquivos = QGroupBox("Arquivos G-code")
        grupo_arquivos.setStyleSheet(self.ESTILO_PAINEL_CARD)
        layout_grupo = QVBoxLayout(grupo_arquivos)
        layout_grupo.setContentsMargins(8, 10, 8, 8)
        layout_grupo.setSpacing(6)

        # Informação da pasta atual
        self.rotulo_diretorio_atual = QLabel("Nenhuma pasta selecionada")
        self.rotulo_diretorio_atual.setWordWrap(True)
        self.rotulo_diretorio_atual.setStyleSheet("font-size: 10px; color: #71717a;")

        self.botao_abrir_pasta = QPushButton("📁 Abrir Pasta...")
        self.botao_abrir_pasta.setToolTip("Selecionar diretório com arquivos G-code")
        self.botao_abrir_pasta.clicked.connect(self._abrir_pasta_arquivos)

        # Instrução de duplo clique para o usuário
        rotulo_dica = QLabel("Dê duplo clique no arquivo para carregar:")
        rotulo_dica.setStyleSheet("font-size: 10px; color: #00f0ff; margin-top: 2px;")

        # Lista de arquivos com duplo clique direto
        self.lista_arquivos = QListWidget()
        self.lista_arquivos.setStyleSheet(
            "QListWidget {"
            "  font-size: 11px;"
            "  background-color: #121216;"
            "  color: #e4e4e7;"
            "  border: 1px solid #2c2c38;"
            "  border-radius: 4px;"
            "}"
            "QListWidget::item {"
            "  padding: 5px 6px;"
            "}"
            "QListWidget::item:hover {"
            "  background-color: #272732;"
            "}"
            "QListWidget::item:selected {"
            "  background-color: #0284c7;"
            "  color: white;"
            "}"
        )
        self.lista_arquivos.itemDoubleClicked.connect(self._carregar_arquivo_selecionado_no_editor)

        layout_grupo.addWidget(self.rotulo_diretorio_atual)
        layout_grupo.addWidget(self.botao_abrir_pasta)
        layout_grupo.addWidget(rotulo_dica)
        layout_grupo.addWidget(self.lista_arquivos, 1)

        layout_painel.addWidget(grupo_arquivos)
        return widget_painel

    def _criar_separador_vertical(self) -> QFrame:
        """
        Cria um separador vertical visual elegante para barras de ferramentas.

        Returns:
            QFrame: Linha divisória vertical.
        """
        separador = QFrame()
        separador.setFrameShape(QFrame.Shape.VLine)
        separador.setFrameShadow(QFrame.Shadow.Sunken)
        separador.setStyleSheet("color: #333342;")
        return separador

    # ------------------------------------------------------------------ #
    #                      CONEXÃO DE SINAIS                              #
    # ------------------------------------------------------------------ #

    def _conectar_sinais(self) -> None:
        """
        Conecta os sinais do ControladorGrbl e eventos de interface aos slots.
        """
        # Sinais do Controlador GRBL
        self.controlador_grbl.sinal_posicao_atualizada.connect(self._atualizar_posicao_dro)
        self.controlador_grbl.sinal_status_atualizado.connect(self._atualizar_status_dro)
        self.controlador_grbl.sinal_conexao_alterada.connect(self._atualizar_estado_conexao)
        self.controlador_grbl.sinal_resposta_recebida.connect(self._adicionar_resposta_console)
        self.controlador_grbl.sinal_erro.connect(self._adicionar_erro_console)
        self.controlador_grbl.sinal_configuracao_recebida.connect(self._atualizar_area_trabalho)
        self.controlador_grbl.sinal_envio_arquivo_concluido.connect(self._ao_concluir_envio_trabalho)
        self.controlador_grbl.sinal_progresso_envio.connect(self._atualizar_progresso_trabalho)
        self.controlador_grbl.sinal_linha_enviada.connect(self.editor_gcode.definir_linha_enviando)
        self.controlador_grbl.sinal_pausa_alterada.connect(self._atualizar_estado_pausa)

        # Botões de Movimento Jog Ortogonal
        self.botao_jog_x_mais.clicked.connect(lambda: self._mover_eixo("X", 1))
        self.botao_jog_x_menos.clicked.connect(lambda: self._mover_eixo("X", -1))
        self.botao_jog_y_mais.clicked.connect(lambda: self._mover_eixo("Y", 1))
        self.botao_jog_y_menos.clicked.connect(lambda: self._mover_eixo("Y", -1))
        self.botao_jog_z_mais.clicked.connect(lambda: self._mover_eixo("Z", 1))
        self.botao_jog_z_menos.clicked.connect(lambda: self._mover_eixo("Z", -1))
        self.botao_jog_z_zero.clicked.connect(lambda: self._zerar_eixo_individual("Z"))

        # Botões de Movimento Jog Diagonal
        self.botao_jog_diag_no.clicked.connect(lambda: self._mover_diagonal(-1, 1))   # X- Y+
        self.botao_jog_diag_ne.clicked.connect(lambda: self._mover_diagonal(1, 1))    # X+ Y+
        self.botao_jog_diag_so.clicked.connect(lambda: self._mover_diagonal(-1, -1))  # X- Y-
        self.botao_jog_diag_se.clicked.connect(lambda: self._mover_diagonal(1, -1))   # X+ Y-

        # Botão Central do Jog
        self.botao_jog_centro.clicked.connect(self._ao_clicar_centro_jog)

    # ------------------------------------------------------------------ #
    #                         AÇÕES / SLOTS                               #
    # ------------------------------------------------------------------ #

    def _atualizar_lista_portas(self) -> None:
        """
        Atualiza as portas seriais disponíveis no seletor da barra superior.
        """
        self.combo_portas.clear()
        portas = self.controlador_grbl.listar_portas_disponiveis()
        if portas:
            self.combo_portas.addItems(portas)
        else:
            self.combo_portas.addItem("Nenhuma porta")

    def _alternar_conexao(self) -> None:
        """
        Alterna entre conectar e desconectar da porta serial selecionada.
        """
        if self.controlador_grbl.esta_conectado():
            self.controlador_grbl.desconectar()
        else:
            porta = self.combo_portas.currentText()
            if porta and porta != "Nenhuma porta":
                baud_rate = int(self.combo_baud.currentText())
                self.controlador_grbl.conectar(porta, baud_rate)

    def _mover_eixo(self, eixo: str, direcao: int) -> None:
        """
        Envia comando de movimentação jog em um único eixo, utilizando
        o passo específico para XY ou Z.

        Args:
            eixo (str): Eixo ('X', 'Y' ou 'Z').
            direcao (int): Direção (1 para positivo, -1 para negativo).
        """
        if eixo.upper() == "Z":
            passo = self.input_passo_z.value()
        else:
            passo = self.input_passo_xy.value()

        feed_rate = self.input_feed_rate.value()
        self.controlador_grbl.mover_eixo(eixo, direcao, passo, feed_rate)

    def _mover_diagonal(self, direcao_x: int, direcao_y: int) -> None:
        """
        Envia comando de movimentação jog diagonal em X e Y simultaneamente,
        utilizando o passo de XY.

        Args:
            direcao_x (int): Direção em X (1 ou -1).
            direcao_y (int): Direção em Y (1 ou -1).
        """
        passo = self.input_passo_xy.value()
        feed_rate = self.input_feed_rate.value()
        self.controlador_grbl.mover_eixos_diagonais(direcao_x, direcao_y, passo, feed_rate)

    def _ao_clicar_centro_jog(self) -> None:
        """
        Ação ao clicar no botão central do Jog.
        """
        self._adicionar_resposta_console("[SISTEMA] Posição de referência do Jog selecionada.")

    def _executar_auto_home(self) -> None:
        """
        Dispara o ciclo de auto home ($H) no GRBL.
        """
        self.controlador_grbl.executar_auto_home()

    def _desbloquear_grbl(self) -> None:
        """
        Envia comando de desbloqueio ($X) ao GRBL.
        """
        self.controlador_grbl.desbloquear_maquina()

    def _reiniciar_grbl(self) -> None:
        """
        Executa o soft-reset do controlador GRBL.
        """
        self.controlador_grbl.reiniciar_grbl()
        self._ao_concluir_envio_trabalho()
        self.rotulo_progresso_status.setText("Resetado")
        self.barra_progresso.setValue(0)

    def _zerar_eixo_individual(self, eixo: str) -> None:
        """
        Zera a coordenada de trabalho de um eixo específico.

        Args:
            eixo (str): Eixo a zerar ('X', 'Y' ou 'Z').
        """
        self.controlador_grbl.zerar_eixo(eixo)

    # ---- Controles de Execução de Trabalho (Play, Pause, Stop) ---- #

    def _iniciar_execucao_trabalho(self) -> None:
        """
        Inicia ou continua a execução do código G-code presente no editor.
        Bloqueia o envio se o código tiver alterações não salvas.
        """
        if self.controlador_grbl.esta_em_pausa():
            self.controlador_grbl.retomar_envio_arquivo()
            return

        conteudo = self.editor_gcode.toPlainText().strip()
        if not conteudo:
            self._adicionar_erro_console("Nenhum código G-code no editor para executar.")
            return

        # Validação: Impedir envio com alterações não salvas
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
        """
        Alterna entre pausar (Feed Hold) e retomar (Cycle Start) o trabalho.
        """
        self.controlador_grbl.alternar_pausa()

    def _parar_execucao_trabalho(self) -> None:
        """
        Cancela e aborta o trabalho em andamento.
        """
        self.controlador_grbl.cancelar_envio_arquivo()
        self._ao_concluir_envio_trabalho()
        self.rotulo_progresso_status.setText("Cancelado")
        self.barra_progresso.setValue(0)

    # ---- Gerenciamento de Edição e Salvamento de G-code ---- #

    def _ao_alterar_texto_editor(self) -> None:
        """
        Detecta quando o conteúdo do editor foi alterado pelo usuário
        e exibe o indicativo visual para salvar.
        """
        conteudo_atual = self.editor_gcode.toPlainText()
        if conteudo_atual != self._conteudo_original_salvo:
            self._arquivo_modificado = True
            nome = self._nome_arquivo_carregado if self._nome_arquivo_carregado else "Novo Arquivo"
            self.rotulo_arquivo_editor.setText(f"{nome} ● [Modificado - Salve antes de enviar]")
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #f59e0b; font-weight: bold;")
            self.botao_salvar_editor.setEnabled(True)
            self.botao_salvar_editor.setStyleSheet(
                "QPushButton { background-color: #f59e0b; color: white; font-weight: bold; border: none; padding: 4px 10px; }"
                "QPushButton:hover { background-color: #d97706; }"
            )
        else:
            self._arquivo_modificado = False
            nome = self._nome_arquivo_carregado if self._nome_arquivo_carregado else "Editor"
            total_linhas = len(conteudo_atual.splitlines())
            self.rotulo_arquivo_editor.setText(f"{nome} ({total_linhas} linhas) ✔")
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #71717a;")
            self.botao_salvar_editor.setEnabled(False)
            self.botao_salvar_editor.setStyleSheet(
                "QPushButton { background-color: #1f2937; color: #4b5563; border: none; padding: 4px 10px; }"
            )

    def _salvar_gcode_editor(self) -> None:
        """
        Salva as alterações do editor no arquivo atual ou abre diálogo para salvar novo.
        """
        conteudo = self.editor_gcode.toPlainText()

        if not self._caminho_arquivo_carregado:
            caminho_arquivo, _ = QFileDialog.getSaveFileName(
                self, "Salvar Arquivo G-code",
                os.path.join(self._diretorio_arquivos_atual or os.path.expanduser("~"), "programa.gcode"),
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
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #34d399; font-weight: bold;")
            self.botao_salvar_editor.setEnabled(False)
            self.botao_salvar_editor.setStyleSheet(
                "QPushButton { background-color: #1f2937; color: #4b5563; border: none; padding: 4px 10px; }"
            )
            self._adicionar_resposta_console(f"[SISTEMA] Arquivo salvo com sucesso: {self._nome_arquivo_carregado}")

            if self._diretorio_arquivos_atual:
                self._listar_arquivos_gcode(self._diretorio_arquivos_atual)

        except OSError as erro:
            self._adicionar_erro_console(f"Erro ao salvar arquivo: {str(erro)}")

    def _limpar_editor_gcode(self) -> None:
        """
        Limpa o conteúdo do editor de G-code e reseta o rastreamento do arquivo.
        """
        self.editor_gcode.clear()
        self._caminho_arquivo_carregado = ""
        self._nome_arquivo_carregado = ""
        self._conteudo_original_salvo = ""
        self._arquivo_modificado = False
        self.rotulo_arquivo_editor.setText("Nenhum arquivo carregado")
        self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #71717a;")
        self.botao_salvar_editor.setEnabled(False)

    def _limpar_console(self) -> None:
        """
        Limpa as mensagens exibidas no console serial.
        """
        self.area_console.clear()

    def _enviar_comando_console(self) -> None:
        """
        Envia o comando manual digitado no console para o GRBL.
        """
        comando = self.input_comando.text().strip()
        if comando:
            self.controlador_grbl.enviar_comando(comando)
            self.input_comando.clear()

    # ---- Gerenciador de Arquivos ---- #

    def _abrir_pasta_arquivos(self) -> None:
        """
        Abre o diálogo de seleção de diretório de arquivos G-code.
        """
        diretorio = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Arquivos G-code")
        if diretorio:
            self._diretorio_arquivos_atual = diretorio
            nome_pasta = os.path.basename(diretorio)
            self.rotulo_diretorio_atual.setText(f"📂 {nome_pasta}")
            self._listar_arquivos_gcode(diretorio)

    def _listar_arquivos_gcode(self, diretorio: str) -> None:
        """
        Lista os arquivos de extensão G-code válidos na lista.

        Args:
            diretorio (str): Caminho absoluto da pasta.
        """
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
        """
        Carrega o arquivo G-code atualmente selecionado na lista para o editor
        ao realizar duplo clique.
        """
        item_selecionado = self.lista_arquivos.currentItem()
        if item_selecionado is None:
            self._adicionar_erro_console("Nenhum arquivo selecionado na lista.")
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
            self.rotulo_arquivo_editor.setStyleSheet("font-size: 11px; color: #71717a;")
            self.botao_salvar_editor.setEnabled(False)
            self._adicionar_resposta_console(f"[SISTEMA] Arquivo carregado no editor: {item_selecionado.text()}")
        except OSError as erro:
            self._adicionar_erro_console(f"Erro ao ler arquivo: {str(erro)}")

    # ------------------------------------------------------------------ #
    #                   SLOTS DE ATUALIZAÇÃO VISUAL                       #
    # ------------------------------------------------------------------ #

    @Slot(float, float, float)
    def _atualizar_posicao_dro(self, x: float, y: float, z: float) -> None:
        """
        Atualiza os displays de coordenadas do DRO.

        Args:
            x (float): Coordenada X.
            y (float): Coordenada Y.
            z (float): Coordenada Z.
        """
        self.rotulo_posicao_x.setText(f"{x:.3f}")
        self.rotulo_posicao_y.setText(f"{y:.3f}")
        self.rotulo_posicao_z.setText(f"{z:.3f}")

    @Slot(str)
    def _atualizar_status_dro(self, status: str) -> None:
        """
        Atualiza o badge de estado da máquina no DRO com cor apropriada.

        Args:
            status (str): Estado retornado pelo GRBL (ex: 'Idle', 'Run', 'Hold', 'Alarm').
        """
        status_limpo = status.strip().upper()
        self.rotulo_estado_dro.setText(status_limpo)

        estilos_por_status = {
            "IDLE": "background-color: #064e3b; color: #34d399; border: 1px solid #059669;",
            "RUN": "background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7;",
            "HOLD": "background-color: #451a03; color: #fbbf24; border: 1px solid #d97706;",
            "ALARM": "background-color: #450a0a; color: #f87171; border: 1px solid #dc2626;",
            "CHECK": "background-color: #3b0764; color: #c084fc; border: 1px solid #9333ea;",
            "HOME": "background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7;",
        }

        estilo = estilos_por_status.get(
            status_limpo,
            "background-color: #18181b; color: #a1a1aa; border: 1px solid #27272a;"
        )
        self.rotulo_estado_dro.setStyleSheet(
            f"QLabel {{ {estilo} font-size: 13px; font-weight: 900; letter-spacing: 1px; border-radius: 4px; }}"
        )

    @Slot(bool)
    def _atualizar_estado_conexao(self, conectado: bool) -> None:
        """
        Atualiza os indicadores visuais de conexão serial.

        Args:
            conectado (bool): True se conectado com sucesso.
        """
        if conectado:
            self.rotulo_indicador_led.setStyleSheet("color: #10b981; font-size: 14px;")
            self.botao_conectar.setText("Desconectar")
            self.botao_conectar.setStyleSheet(
                "QPushButton { background-color: #3f3f46; color: white; border: none; }"
                "QPushButton:hover { background-color: #52525b; }"
            )
            self._atualizar_status_dro("IDLE")
        else:
            self.rotulo_indicador_led.setStyleSheet("color: #ef4444; font-size: 14px;")
            self.botao_conectar.setText("Conectar")
            self.botao_conectar.setStyleSheet(
                "QPushButton { background-color: #0284c7; color: white; font-weight: bold; border: none; }"
                "QPushButton:hover { background-color: #0369a1; }"
            )
            self._atualizar_status_dro("DESCONECTADO")
            self._ao_concluir_envio_trabalho()

    @Slot(bool)
    def _atualizar_estado_pausa(self, em_pausa: bool) -> None:
        """
        Atualiza o botão de pausa quando o estado é alterado.

        Args:
            em_pausa (bool): True se estiver pausado.
        """
        if em_pausa:
            self.botao_pausar_trabalho.setText("▶ Continuar")
            self.botao_pausar_trabalho.setStyleSheet(
                "QPushButton { background-color: #10b981; color: white; font-weight: bold; padding: 5px 14px; }"
                "QPushButton:hover { background-color: #059669; }"
            )
            self.rotulo_progresso_status.setText("Pausado")
        else:
            self.botao_pausar_trabalho.setText("⏸ Pausar")
            self.botao_pausar_trabalho.setStyleSheet(
                "QPushButton { background-color: #f59e0b; color: white; font-weight: bold; padding: 5px 14px; }"
                "QPushButton:hover { background-color: #d97706; }"
            )
            if self.controlador_grbl.esta_enviando():
                self.rotulo_progresso_status.setText("Executando...")

    @Slot(int, int)
    def _atualizar_progresso_trabalho(self, linha_atual: int, total_linhas: int) -> None:
        """
        Atualiza o contador e a barra visual de progresso durante a execução.

        Args:
            linha_atual (int): Linha sendo transmitida.
            total_linhas (int): Quantidade total de linhas.
        """
        if total_linhas > 0:
            percentual = int((linha_atual / total_linhas) * 100)
            self.barra_progresso.setValue(percentual)
            self.rotulo_progresso_status.setText(f"{linha_atual}/{total_linhas} ({percentual}%)")

    @Slot()
    def _ao_concluir_envio_trabalho(self) -> None:
        """
        Restaura o estado dos botões e do editor ao finalizar o envio do G-code.
        """
        self.editor_gcode.setReadOnly(False)
        self.editor_gcode.definir_linha_enviando(-1)
        self.botao_iniciar_trabalho.setEnabled(True)
        self.botao_pausar_trabalho.setEnabled(False)
        self.botao_pausar_trabalho.setText("⏸ Pausar")
        self.botao_pausar_trabalho.setStyleSheet(
            "QPushButton { background-color: #f59e0b; color: white; font-weight: bold; padding: 5px 14px; }"
            "QPushButton:hover { background-color: #d97706; }"
            "QPushButton:disabled { background-color: #382c16; color: #6b5c3b; }"
        )
        self.botao_parar_trabalho.setEnabled(False)
        self.rotulo_progresso_status.setText("Concluído")
        self.barra_progresso.setValue(100)

    @Slot(str)
    def _adicionar_resposta_console(self, texto: str) -> None:
        """
        Adiciona uma linha informativa recebida do GRBL ou do sistema ao console.

        Args:
            texto (str): Mensagem recebida.
        """
        if texto.startswith(">"):
            self.area_console.append(f'<span style="color: #38bdf8;">{texto}</span>')
        elif texto.startswith("[SISTEMA]"):
            self.area_console.append(f'<span style="color: #a78bfa;">{texto}</span>')
        elif texto == "ok":
            self.area_console.append(f'<span style="color: #4ade80;">{texto}</span>')
        else:
            self.area_console.append(f'<span style="color: #d4d4d8;">{texto}</span>')

    @Slot(str)
    def _adicionar_erro_console(self, mensagem_erro: str) -> None:
        """
        Adiciona uma mensagem de erro destacada em vermelho no console.

        Args:
            mensagem_erro (str): Mensagem de erro.
        """
        self.area_console.append(f'<span style="color: #f87171; font-weight: bold;">[ERRO] {mensagem_erro}</span>')

    @Slot(float, float, float)
    def _atualizar_area_trabalho(self, limite_x: float, limite_y: float, limite_z: float) -> None:
        """
        Atualiza as dimensões da área de trabalho no rodapé do DRO.

        Args:
            limite_x (float): Limite máximo do eixo X em mm.
            limite_y (float): Limite máximo do eixo Y em mm.
            limite_z (float): Limite máximo do eixo Z em mm.
        """
        self.rotulo_area_trabalho.setText(f"Área: [{limite_x:.0f} × {limite_y:.0f} × {limite_z:.0f} mm]")

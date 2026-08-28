"""
Módulo de interface gráfica para calibração de Z-Offset e nivelamento de mesa por software.

Contém o visualizador 2D interativo da malha de pontos e o painel assistente
para calibração do "ponto" com traços de teste para as 10 canetas,
incluindo DRO em tempo real, controle de Feed Rate e controle manual (Jog) ergonômico.
"""

import math
from typing import Optional, Dict, List, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QDoubleSpinBox, QSpinBox, QGroupBox, QFrame,
    QSplitter, QCheckBox, QMessageBox, QComboBox, QToolTip,
    QProgressBar, QButtonGroup, QScrollArea, QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QPointF, QRectF, Slot, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QMouseEvent, QPainterPath
)

from resources.controle_da_maquina.logica_controle_da_maquina import ControladorGrbl
from resources.controle_da_maquina.gerenciador_canetas import GerenciadorCanetas, SlotCaneta
from resources.controle_da_maquina.gerenciador_area_desenho import GerenciadorAreaDesenho
from resources.controle_da_maquina.gerenciador_nivelamento import (
    GerenciadorNivelamento, MalhaCaneta, PontoMalha
)
from resources.controle_da_maquina.aba_controle_da_maquina import SpinBoxPassoAdaptativo
from resources.estilo.tema_escuro import ESTILO_CARD_PADRAO, PALETA_CORES


class VisualizadorMalhaNivelamento(QWidget):
    """
    Widget 2D interativo que renderiza a área de desenho, as linhas virtuais
    delimitadoras, os pontos da malha com seus valores de Z e o cabeçote da máquina.
    Permite clicar diretamente sobre qualquer nó para selecioná-lo.
    """

    sinal_ponto_selecionado = Signal(int, int)  # (linha, coluna)

    def __init__(
        self,
        gerenciador_nivelamento: GerenciadorNivelamento,
        gerenciador_area: Optional[GerenciadorAreaDesenho] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.gerenciador_nivelamento = gerenciador_nivelamento
        self.gerenciador_area = gerenciador_area

        self._caneta_ativa_id: int = 1
        self._ponto_ativo_linha: int = 0
        self._ponto_ativo_coluna: int = 0

        # Posição da máquina em tempo real
        self.pos_maquina_x: float = 0.0
        self.pos_maquina_y: float = 0.0
        self.pos_maquina_z: float = 0.0

        # Limites da máquina (mm)
        self.limite_x: float = 330.0
        self.limite_y: float = 328.0

        # Estado da caneta engatada fisicamente no cabeçote
        self._caneta_engatada_id: Optional[int] = None
        self._caneta_engatada_nome: str = "Vazio"
        self._caneta_engatada_cor: str = "#6a6a82"

        self.setMinimumSize(360, 360)
        self.setMouseTracking(True)

        self.gerenciador_nivelamento.sinal_nivelamento_atualizado.connect(self.update)
        if self.gerenciador_area:
            self.gerenciador_area.sinal_area_alterada.connect(self._ao_alterar_area)

    def atualizar_caneta_engatada(self, id_caneta: Optional[int], nome: str, cor_hex: str) -> None:
        """Atualiza a indicação visual de qual caneta está no cabeçote físico."""
        self._caneta_engatada_id = id_caneta if id_caneta and id_caneta > 0 else None
        self._caneta_engatada_nome = nome
        self._caneta_engatada_cor = cor_hex
        self.update()

    def definir_caneta(self, id_caneta: int) -> None:
        """Define qual caneta está sendo visualizada/calibrada."""
        self._caneta_ativa_id = id_caneta
        self.update()

    def definir_ponto_ativo(self, linha: int, coluna: int) -> None:
        """Define o ponto atualmente focado no assistente de calibração."""
        self._ponto_ativo_linha = linha
        self._ponto_ativo_coluna = coluna
        self.update()

    def atualizar_posicao_maquina(self, x: float, y: float, z: float) -> None:
        """Atualiza o marcador de posição física da máquina."""
        self.pos_maquina_x = x
        self.pos_maquina_y = y
        self.pos_maquina_z = z
        self.update()

    def _ao_alterar_area(self, xi: float, yi: float, xf: float, yf: float) -> None:
        self.update()

    # ------------------------------------------------------------------ #
    #                       TRANSFORMAÇÃO DE COORDENADAS                 #
    # ------------------------------------------------------------------ #

    def _obter_transformacao(self) -> Tuple[float, float, float, float]:
        """Calcula escala e deslocamento para centralizar a mesa no widget mantendo proporção."""
        w = float(self.width())
        h = float(self.height())
        margem = 32.0

        escala_x = (w - 2.0 * margem) / max(1.0, self.limite_y)
        escala_y = (h - 2.0 * margem) / max(1.0, self.limite_x)
        escala = min(escala_x, escala_y)

        largura_desenhada = self.limite_y * escala
        altura_desenhada = self.limite_x * escala

        offset_x = (w - largura_desenhada) / 2.0
        offset_y = (h - altura_desenhada) / 2.0

        return escala, offset_x, offset_y, altura_desenhada

    def mm_para_pixel(self, x_mm: float, y_mm: float) -> QPointF:
        """Converte coordenadas em milímetros para pixels."""
        escala, off_x, off_y, alt_desenho = self._obter_transformacao()
        larg_desenho = self.limite_y * escala
        px = (off_x + larg_desenho) - (y_mm * escala)
        py = (off_y + alt_desenho) - (x_mm * escala)
        return QPointF(px, py)

    def pixel_para_mm(self, px: float, py: float) -> Tuple[float, float]:
        """Converte pixels para coordenadas em milímetros."""
        escala, off_x, off_y, alt_desenho = self._obter_transformacao()
        if escala <= 0:
            return 0.0, 0.0
        larg_desenho = self.limite_y * escala
        y_mm = (off_x + larg_desenho - px) / escala
        x_mm = (off_y + alt_desenho - py) / escala
        return x_mm, y_mm

    # ------------------------------------------------------------------ #
    #                       PINTURA DO VISUALIZADOR 2D                   #
    # ------------------------------------------------------------------ #

    def paintEvent(self, evento) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Fundo escuro
        painter.fillRect(self.rect(), QColor("#161628"))

        escala, off_x, off_y, alt_desenho = self._obter_transformacao()
        larg_desenho = self.limite_y * escala

        # 1. Mesa Física da Máquina
        ret_mesa = QRectF(off_x, off_y, larg_desenho, alt_desenho)
        painter.setPen(QPen(QColor("#2d2d48"), 1.5))
        painter.setBrush(QColor("#1b1b32"))
        painter.drawRoundedRect(ret_mesa, 6, 6)

        # Grade sutil de fundo (a cada 50mm)
        painter.setPen(QPen(QColor("#24243e"), 1, Qt.PenStyle.DotLine))
        for x_grid in range(0, int(self.limite_x) + 1, 50):
            p1 = self.mm_para_pixel(x_grid, 0)
            p2 = self.mm_para_pixel(x_grid, self.limite_y)
            painter.drawLine(p1, p2)
        for y_grid in range(0, int(self.limite_y) + 1, 50):
            p1 = self.mm_para_pixel(0, y_grid)
            p2 = self.mm_para_pixel(self.limite_x, y_grid)
            painter.drawLine(p1, p2)

        # 2. Área de Desenho (Retângulo Delimitador)
        x_ini, y_ini, x_fim, y_fim = self.gerenciador_nivelamento.obter_limites_area()
        p_inf_dir = self.mm_para_pixel(x_ini, y_ini)
        p_sup_esq = self.mm_para_pixel(x_fim, y_fim)

        ret_area = QRectF(
            p_sup_esq.x(),
            p_sup_esq.y(),
            p_inf_dir.x() - p_sup_esq.x(),
            p_inf_dir.y() - p_sup_esq.y()
        )

        painter.setPen(QPen(QColor("#5b7fff"), 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(91, 127, 255, 18))
        painter.drawRect(ret_area)

        # Rótulo de dimensões da Área de Desenho
        painter.setPen(QColor("#7da4ff"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        larg_area = y_fim - y_ini
        alt_area = x_fim - x_ini
        painter.drawText(
            QRectF(ret_area.left(), ret_area.top() - 18, ret_area.width(), 16),
            Qt.AlignmentFlag.AlignCenter,
            f"Área de Desenho: {larg_area:.1f} x {alt_area:.1f} mm"
        )

        # Indicador de Home (0, 0)
        p_home = self.mm_para_pixel(0.0, 0.0)
        painter.setPen(QColor("#fbbf24"))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(
            QRectF(p_home.x() - 48, p_home.y() - 16, 46, 14),
            Qt.AlignmentFlag.AlignRight,
            "🏠 (0,0)"
        )

        # 3. Malha de Calibração da Caneta Selecionada
        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_ativa_id)
        if malha and malha.pontos:
            self._desenhar_malha(painter, malha)

        # 4. Posição Atual do Cabeçote (Real-Time Live Tracker)
        p_cabeca = self.mm_para_pixel(self.pos_maquina_x, self.pos_maquina_y)
        painter.setPen(QPen(QColor("#4ade80"), 1.5))
        painter.setBrush(QColor(74, 222, 128, 90))
        painter.drawEllipse(p_cabeca, 6.0, 6.0)
        painter.drawLine(QPointF(p_cabeca.x() - 10, p_cabeca.y()), QPointF(p_cabeca.x() + 10, p_cabeca.y()))
        painter.drawLine(QPointF(p_cabeca.x(), p_cabeca.y() - 10), QPointF(p_cabeca.x(), p_cabeca.y() + 10))

        # 5. Chip de Status do Cabeçote no Canto Superior Direito
        if self._caneta_engatada_id and self._caneta_engatada_id > 0:
            txt_cabecote = f"🤖 Cabeçote: Caneta {self._caneta_engatada_id} ({self._caneta_engatada_nome})"
            cor_circulo = QColor(self._caneta_engatada_cor)
            cor_borda = QColor("#4ade80")
        else:
            txt_cabecote = "🤖 Cabeçote: Vazio (Sem Caneta)"
            cor_circulo = QColor("#6a6a82")
            cor_borda = QColor("#555570")

        rect_badge = QRectF(self.width() - 225, 10, 215, 24)
        painter.setPen(QPen(cor_borda, 1))
        painter.setBrush(QColor("#1b1b35"))
        painter.drawRoundedRect(rect_badge, 4, 4)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(cor_circulo)
        painter.drawEllipse(QPointF(rect_badge.left() + 12, rect_badge.center().y()), 4.5, 4.5)

        painter.setPen(QColor("#e8e8f0"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(
            QRectF(rect_badge.left() + 22, rect_badge.top(), rect_badge.width() - 24, rect_badge.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            txt_cabecote
        )

        # Legenda no Canto Inferior Esquerdo
        painter.setPen(QColor("#9090a8"))
        painter.setFont(QFont("Segoe UI", 8))
        status_head_curto = f"Caneta {self._caneta_engatada_id}" if self._caneta_engatada_id else "Vazio"
        texto_info = f"Calibrando: Caneta {self._caneta_ativa_id} ({malha.nome if malha else ''}) | Cabeçote: {status_head_curto} | Posição: X={self.pos_maquina_x:.2f} Y={self.pos_maquina_y:.2f} Z={self.pos_maquina_z:.2f}"
        painter.drawText(10, self.height() - 8, texto_info)

    def _desenhar_malha(self, painter: QPainter, malha: MalhaCaneta) -> None:
        """Renderiza as linhas horizontais, linhas verticais conectivas e os nós de teste da malha."""
        cor_caneta = QColor(malha.cor_hex)

        linhas_dict: Dict[int, List[PontoMalha]] = {}
        for p in malha.pontos:
            linhas_dict.setdefault(p.linha, []).append(p)

        for lin, pts in linhas_dict.items():
            pts.sort(key=lambda item: item.coluna)

        # 1. Linhas Virtuais Horizontais
        painter.setPen(QPen(QColor(100, 110, 150, 180), 1.2, Qt.PenStyle.DashDotLine))
        for lin, pts in linhas_dict.items():
            if len(pts) >= 2:
                p_inicio = self.mm_para_pixel(pts[0].x, pts[0].y)
                p_fim = self.mm_para_pixel(pts[-1].x, pts[-1].y)
                painter.drawLine(p_inicio, p_fim)

                painter.setPen(QColor("#7080a8"))
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.drawText(
                    QPointF(p_inicio.x() - 24, p_inicio.y() + 3),
                    f"L{lin+1}"
                )
                painter.setPen(QPen(QColor(100, 110, 150, 180), 1.2, Qt.PenStyle.DashDotLine))

        # 2. Conexões Verticais
        painter.setPen(QPen(QColor(80, 90, 130, 80), 1, Qt.PenStyle.DotLine))
        for col_idx in range(malha.num_pontos_por_linha):
            col_pts = [p for p in malha.pontos if p.coluna == col_idx]
            col_pts.sort(key=lambda item: item.linha)
            for k in range(len(col_pts) - 1):
                p1 = self.mm_para_pixel(col_pts[k].x, col_pts[k].y)
                p2 = self.mm_para_pixel(col_pts[k+1].x, col_pts[k+1].y)
                painter.drawLine(p1, p2)

        # 3. Nós / Pontos de Teste
        for p in malha.pontos:
            pt_pixel = self.mm_para_pixel(p.x, p.y)
            eh_ativo = (p.linha == self._ponto_ativo_linha and p.coluna == self._ponto_ativo_coluna)

            if eh_ativo:
                painter.setPen(QPen(QColor("#fbbf24"), 2.0))
                painter.setBrush(QColor(251, 191, 36, 40))
                painter.drawEllipse(pt_pixel, 12.0, 12.0)

                painter.setPen(QPen(QColor("#fbbf24"), 1.2))
                painter.drawLine(QPointF(pt_pixel.x() - 16, pt_pixel.y()), QPointF(pt_pixel.x() + 16, pt_pixel.y()))
                painter.drawLine(QPointF(pt_pixel.x(), pt_pixel.y() - 16), QPointF(pt_pixel.x(), pt_pixel.y() + 16))

            if p.calibrado:
                painter.setPen(QPen(QColor("#4ade80"), 1.8))
                painter.setBrush(cor_caneta)
                painter.drawEllipse(pt_pixel, 5.5, 5.5)

                painter.setPen(QColor("#e8e8f0"))
                painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
                z_txt = f"{p.z:+.2f}"
                painter.drawText(
                    QRectF(pt_pixel.x() - 25, pt_pixel.y() + 6, 50, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    z_txt
                )
            else:
                painter.setPen(QPen(QColor("#6a6a82"), 1.5, Qt.PenStyle.DashLine))
                painter.setBrush(QColor("#1e1e35"))
                painter.drawEllipse(pt_pixel, 4.5, 4.5)

                painter.setPen(QColor("#808098"))
                painter.setFont(QFont("Segoe UI", 7))
                idx_txt = f"P{p.coluna+1}"
                painter.drawText(
                    QRectF(pt_pixel.x() - 15, pt_pixel.y() + 5, 30, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    idx_txt
                )

    # ------------------------------------------------------------------ #
    #                       INTERAÇÃO COM MOUSE                          #
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, evento: QMouseEvent) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            clique_pos = evento.position()
            malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_ativa_id)
            if not malha:
                return

            melhor_ponto = None
            menor_dist = 18.0

            for p in malha.pontos:
                pt_pixel = self.mm_para_pixel(p.x, p.y)
                dist = math.hypot(clique_pos.x() - pt_pixel.x(), clique_pos.y() - pt_pixel.y())
                if dist < menor_dist:
                    menor_dist = dist
                    melhor_ponto = p

            if melhor_ponto:
                self.definir_ponto_ativo(melhor_ponto.linha, melhor_ponto.coluna)
                self.sinal_ponto_selecionado.emit(melhor_ponto.linha, melhor_ponto.coluna)

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:
        pos = evento.position()
        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_ativa_id)
        if not malha:
            return

        for p in malha.pontos:
            pt_pixel = self.mm_para_pixel(p.x, p.y)
            dist = math.hypot(pos.x() - pt_pixel.x(), pos.y() - pt_pixel.y())
            if dist < 12.0:
                status = f"Z Calibrado: {p.z:+.3f} mm" if p.calibrado else "Status: Pendente"
                QToolTip.showText(
                    evento.globalPosition().toPoint(),
                    f"Linha {p.linha+1}, Ponto {p.coluna+1}\n"
                    f"X: {p.x:.2f} mm | Y: {p.y:.2f} mm\n"
                    f"{status}",
                    self
                )
                return
        QToolTip.hideText()


class PainelCalibracaoZOffset(QWidget):
    """
    Painel completo e modernizado de Calibração de Z-Offset e Nivelamento por Software.
    Apresenta DRO em tempo real, controle claro de Feed Rate, Jog ergonômico e
    assistente sequencial intuitivo para as 10 canetas.
    """

    def __init__(
        self,
        gerenciador_nivelamento: GerenciadorNivelamento,
        gerenciador_canetas: GerenciadorCanetas,
        gerenciador_area: GerenciadorAreaDesenho,
        controlador_grbl: ControladorGrbl,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.gerenciador_nivelamento = gerenciador_nivelamento
        self.gerenciador_canetas = gerenciador_canetas
        self.gerenciador_area = gerenciador_area
        self.controlador_grbl = controlador_grbl

        self._caneta_selecionada_id: int = 1
        self._indice_linha_atual: int = 0
        self._indice_coluna_atual: int = 0
        self._passo_jog_z: float = 0.1
        self._bloqueando_atualizacao: bool = False

        self._configurar_ui()
        self._conectar_sinais()
        self._carregar_dados_caneta(1)

    def _configurar_ui(self) -> None:
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(10, 10, 10, 10)
        layout_raiz.setSpacing(10)

        # ============================================================== #
        #              TOPO: HEADER UNIFICADO DE STATUS & CANETA         #
        # ============================================================== #
        card_header = QFrame()
        card_header.setFixedHeight(46)
        card_header.setStyleSheet(
            "QFrame {"
            "  background-color: #1e1e38;"
            "  border: 1px solid #333355;"
            "  border-radius: 8px;"
            "}"
        )
        layout_header = QHBoxLayout(card_header)
        layout_header.setContentsMargins(10, 4, 10, 4)
        layout_header.setSpacing(10)

        # 1. Bloco Esquerda: Cabeçote da Máquina
        layout_cabecote_bloco = QHBoxLayout()
        layout_cabecote_bloco.setSpacing(6)

        self.lbl_icone_cabecote = QLabel("🤖")
        self.lbl_icone_cabecote.setStyleSheet("font-size: 16px;")

        self.lbl_pill_engatada = QLabel(" ⚪ ")
        self.lbl_pill_engatada.setFixedSize(30, 24)
        self.lbl_pill_engatada.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pill_engatada.setStyleSheet("font-weight: 800; border-radius: 4px; color: white; background-color: #444460;")

        layout_txt_cabecote = QVBoxLayout()
        layout_txt_cabecote.setSpacing(0)

        lbl_tit_cabecote = QLabel("FERRAMENTA NO CABEÇOTE")
        lbl_tit_cabecote.setStyleSheet("font-size: 9px; font-weight: 800; color: #7da4ff; letter-spacing: 0.5px;")

        self.lbl_status_cabecote = QLabel("Nenhuma Caneta Engatada (Vazio)")
        self.lbl_status_cabecote.setStyleSheet("font-size: 11px; font-weight: 700; color: #e8e8f0;")

        layout_txt_cabecote.addWidget(lbl_tit_cabecote)
        layout_txt_cabecote.addWidget(self.lbl_status_cabecote)

        self.btn_devolver_caneta = QPushButton("⏏ Devolver")
        self.btn_devolver_caneta.setToolTip("Devolver caneta engatada na baia")
        self.btn_devolver_caneta.setStyleSheet(
            "QPushButton { background-color: #2c2c48; font-weight: 600; font-size: 11px; padding: 3px 8px; border: 1px solid #3a3a58; border-radius: 5px; }"
            "QPushButton:hover { background-color: #e05555; color: white; border-color: #f87171; }"
        )
        self.btn_devolver_caneta.clicked.connect(self._ao_clicar_devolver_caneta)

        layout_cabecote_bloco.addWidget(self.lbl_icone_cabecote)
        layout_cabecote_bloco.addWidget(self.lbl_pill_engatada)
        layout_cabecote_bloco.addLayout(layout_txt_cabecote)
        layout_cabecote_bloco.addWidget(self.btn_devolver_caneta)

        # Divisor vertical discreto
        linha_div = QFrame()
        linha_div.setFrameShape(QFrame.Shape.VLine)
        linha_div.setFrameShadow(QFrame.Shadow.Sunken)
        linha_div.setFixedHeight(24)
        linha_div.setStyleSheet("color: #333355;")

        # 2. Bloco Direita: Seletor de Caneta para Calibração
        layout_calib_bloco = QHBoxLayout()
        layout_calib_bloco.setSpacing(6)

        lbl_tit_alvo = QLabel("CALIBRAR:")
        lbl_tit_alvo.setStyleSheet("font-size: 10px; font-weight: 800; color: #9090a8;")

        self.lbl_pill_cor = QLabel(" 1 ")
        self.lbl_pill_cor.setFixedSize(28, 24)
        self.lbl_pill_cor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pill_cor.setStyleSheet("font-weight: 800; border-radius: 4px; color: white; background-color: #1e1e35;")

        self.combo_canetas = QComboBox()
        self.combo_canetas.setMinimumWidth(160)
        self._preencher_combo_canetas()
        self.combo_canetas.currentIndexChanged.connect(self._ao_trocar_caneta_combo)

        self.badge_status_calib = QLabel("⚪ Não Calibrada")
        self.badge_status_calib.setStyleSheet(
            "background-color: #222238; color: #9090a8; border: 1px solid #3a3a58; "
            "border-radius: 4px; padding: 3px 6px; font-weight: 700; font-size: 11px;"
        )

        self.progresso_calib = QProgressBar()
        self.progresso_calib.setRange(0, 100)
        self.progresso_calib.setValue(0)
        self.progresso_calib.setFixedSize(110, 16)
        self.progresso_calib.setFormat("%v% (%p%)")

        self.btn_engatar_caneta = QPushButton("⚡ Engatar Caneta")
        self.btn_engatar_caneta.setToolTip("Envia a macro para trocar fisicamente o cabeçote para esta caneta")
        self.btn_engatar_caneta.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
        )
        self.btn_engatar_caneta.clicked.connect(self._ao_clicar_engatar_caneta)

        layout_calib_bloco.addWidget(lbl_tit_alvo)
        layout_calib_bloco.addWidget(self.lbl_pill_cor)
        layout_calib_bloco.addWidget(self.combo_canetas, 1)
        layout_calib_bloco.addWidget(self.badge_status_calib)
        layout_calib_bloco.addWidget(self.progresso_calib)
        layout_calib_bloco.addWidget(self.btn_engatar_caneta)

        layout_header.addLayout(layout_cabecote_bloco)
        layout_header.addWidget(linha_div)
        layout_header.addLayout(layout_calib_bloco, 1)

        layout_raiz.addWidget(card_header, 0)

        # ============================================================== #
        #              DIVISOR PRINCIPAL: ESQUERDA (CONTROLES) / DIR (2D)#
        # ============================================================== #
        divisor = QSplitter(Qt.Orientation.Horizontal)

        scroll_esq = QScrollArea()
        scroll_esq.setWidgetResizable(True)
        scroll_esq.setFrameShape(QFrame.Shape.NoFrame)
        scroll_esq.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_esq.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        widget_esquerda = QWidget()
        widget_esquerda.setStyleSheet("background: transparent;")
        layout_esq = QVBoxLayout(widget_esquerda)
        layout_esq.setContentsMargins(0, 0, 8, 0)
        layout_esq.setSpacing(8)

        # 1. DRO em Tempo Real & Status da Máquina
        layout_esq.addWidget(self._criar_painel_dro())

        # 2. Assistente de Calibração (Passo a Passo)
        layout_esq.addWidget(self._criar_painel_assistente())

        # 3. Controle Manual (Joystick / Jog) com Feed Rate
        layout_esq.addWidget(self._criar_painel_jog())

        # 4. Configuração da Malha e Altura de Segurança Z-Up
        layout_esq.addWidget(self._criar_painel_config_malha_zup())

        # 5. Ações Globais de Calibração
        layout_acoes_globais = QHBoxLayout()
        layout_acoes_globais.setSpacing(6)

        self.btn_importar_offsets = QPushButton("📥 Importar Offsets Calibrados")
        self.btn_importar_offsets.setToolTip("Importa arquivo JSON com a calibração de pontos e offsets de todas as canetas")
        self.btn_importar_offsets.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; padding: 6px 12px; font-weight: 700; font-size: 11px; border: 1px solid #10b981; border-radius: 5px; }"
            "QPushButton:hover { background-color: #10b981; }"
        )
        self.btn_importar_offsets.clicked.connect(self._ao_importar_offsets)

        self.btn_exportar_offsets = QPushButton("📤 Exportar Offsets")
        self.btn_exportar_offsets.setToolTip("Salva backup das calibrações de todas as canetas em arquivo JSON")
        self.btn_exportar_offsets.setStyleSheet(
            "QPushButton { background-color: #252540; color: #e8e8f0; padding: 6px 10px; font-weight: 600; font-size: 11px; border: 1px solid #33334d; border-radius: 5px; }"
            "QPushButton:hover { background-color: #3b82f6; color: white; border-color: #60a5fa; }"
        )
        self.btn_exportar_offsets.clicked.connect(self._ao_exportar_offsets)

        self.btn_copiar_para_todas = QPushButton("📋 Copiar p/ Todas")
        self.btn_copiar_para_todas.setToolTip("Copia a malha desta caneta para as outras 9 canetas")
        self.btn_copiar_para_todas.setStyleSheet("QPushButton { padding: 6px 10px; font-weight: 600; font-size: 11px; }")
        self.btn_copiar_para_todas.clicked.connect(self._ao_copiar_para_todas)

        self.btn_resetar_caneta = QPushButton("🗑️ Resetar")
        self.btn_resetar_caneta.setToolTip("Resetar calibração desta caneta")
        self.btn_resetar_caneta.setStyleSheet("QPushButton { padding: 6px 10px; font-weight: 600; font-size: 11px; color: #f87171; }")
        self.btn_resetar_caneta.clicked.connect(self._ao_resetar_calibracao)

        layout_acoes_globais.addWidget(self.btn_importar_offsets, 2)
        layout_acoes_globais.addWidget(self.btn_exportar_offsets, 1)
        layout_acoes_globais.addWidget(self.btn_copiar_para_todas, 1)
        layout_acoes_globais.addWidget(self.btn_resetar_caneta, 1)
        layout_esq.addLayout(layout_acoes_globais)

        layout_esq.addStretch()
        scroll_esq.setWidget(widget_esquerda)
        divisor.addWidget(scroll_esq)

        # ============================================================== #
        #              PAINEL DIREITO: VISUALIZADOR 2D DA MALHA          #
        # ============================================================== #
        widget_direita = QFrame()
        widget_direita.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_dir = QVBoxLayout(widget_direita)
        layout_dir.setContentsMargins(10, 10, 10, 10)
        layout_dir.setSpacing(8)

        layout_topo_dir = QHBoxLayout()
        rotulo_mapa = QLabel("🗺️ Visualização da Malha & Linhas Delimitadoras")
        rotulo_mapa.setStyleSheet("font-weight: 700; color: #7da4ff; font-size: 13px;")

        self.lbl_info_dimensoes_malha = QLabel("4x3 (12 pontos)")
        self.lbl_info_dimensoes_malha.setStyleSheet(
            "background-color: #1e1e35; color: #4ade80; border: 1px solid #2e2e4a; border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 10px;"
        )

        layout_topo_dir.addWidget(rotulo_mapa)
        layout_topo_dir.addStretch()
        layout_topo_dir.addWidget(self.lbl_info_dimensoes_malha)
        layout_dir.addLayout(layout_topo_dir)

        self.visualizador_malha = VisualizadorMalhaNivelamento(
            gerenciador_nivelamento=self.gerenciador_nivelamento,
            gerenciador_area=self.gerenciador_area,
            parent=self
        )
        self.visualizador_malha.sinal_ponto_selecionado.connect(self._ao_clicar_ponto_visualizador)
        layout_dir.addWidget(self.visualizador_malha, 1)

        # Legenda explicativa
        layout_legenda = QHBoxLayout()
        layout_legenda.setSpacing(10)

        lbl_leg_calib = QLabel("🟢 Calibrado")
        lbl_leg_calib.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 600;")
        lbl_leg_pend = QLabel("⚪ Pendente")
        lbl_leg_pend.setStyleSheet("color: #9090a8; font-size: 11px; font-weight: 600;")
        lbl_leg_ativo = QLabel("🟡 Selecionado")
        lbl_leg_ativo.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 600;")
        lbl_leg_dica = QLabel("💡 Clique no nó para inspecionar")
        lbl_leg_dica.setStyleSheet("color: #7da4ff; font-size: 11px; font-style: italic;")

        layout_legenda.addWidget(lbl_leg_calib)
        layout_legenda.addWidget(lbl_leg_pend)
        layout_legenda.addWidget(lbl_leg_ativo)
        layout_legenda.addStretch()
        layout_legenda.addWidget(lbl_leg_dica)

        layout_dir.addLayout(layout_legenda)

        divisor.addWidget(widget_direita)
        divisor.setSizes([750, 480])
        divisor.setStretchFactor(0, 3)
        divisor.setStretchFactor(1, 2)

        layout_raiz.addWidget(divisor, 1)

    # ------------------------------------------------------------------ #
    #                      PAINEL: DRO EM TEMPO REAL                     #
    # ------------------------------------------------------------------ #

    def _criar_painel_dro(self) -> QGroupBox:
        """Cria o painel de leitura digital das coordenadas XYZ e status da máquina."""
        grupo_dro = QGroupBox("📟 Posição em Tempo Real (DRO) & Status")
        grupo_dro.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_dro = QVBoxLayout(grupo_dro)
        layout_dro.setContentsMargins(10, 12, 10, 8)
        layout_dro.setSpacing(6)

        # Topo: Estado GRBL e botões de ação rápida
        layout_topo_dro = QHBoxLayout()
        layout_topo_dro.setSpacing(6)

        self.rotulo_estado_dro = QLabel("DESCONECTADO")
        self.rotulo_estado_dro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_estado_dro.setFixedHeight(26)
        self.rotulo_estado_dro.setMinimumWidth(110)
        self.rotulo_estado_dro.setStyleSheet(
            "QLabel {"
            "  background-color: #1e1e35;"
            "  color: #6a6a82;"
            "  font-size: 11px;"
            "  font-weight: 800;"
            "  letter-spacing: 1px;"
            "  border: 1px solid #2e2e4a;"
            "  border-radius: 5px;"
            "  padding: 0 8px;"
            "}"
        )

        self.btn_zerar_tudo = QPushButton("Zerar XYZ")
        self.btn_zerar_tudo.setToolTip("Zerar todos os eixos de trabalho (G10 L20 P1 X0 Y0 Z0)")
        self.btn_zerar_tudo.setStyleSheet(
            "QPushButton { background-color: #2c2c48; font-weight: 700; font-size: 11px; padding: 4px 10px; border: 1px solid #3a3a58; border-radius: 5px; }"
            "QPushButton:hover { background-color: #3b82f6; color: white; border-color: #60a5fa; }"
        )
        self.btn_zerar_tudo.clicked.connect(self._zerar_todos_eixos)

        self.btn_origem_rapida = QPushButton("🏠 Origem (0, 0)")
        self.btn_origem_rapida.setToolTip("Move X e Y para 0 com segurança prévia em Z")
        self.btn_origem_rapida.setStyleSheet(
            "QPushButton { background-color: #252540; font-weight: 600; font-size: 11px; padding: 4px 8px; border: 1px solid #33334d; border-radius: 5px; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; }"
        )
        self.btn_origem_rapida.clicked.connect(self._mover_para_origem_jog)

        self.lbl_indicador_feed_atual = QLabel("⚡ Feed: 2500 mm/min")
        self.lbl_indicador_feed_atual.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_indicador_feed_atual.setStyleSheet("font-size: 11px; font-weight: 700; color: #7da4ff;")

        layout_topo_dro.addWidget(self.rotulo_estado_dro)
        layout_topo_dro.addWidget(self.btn_zerar_tudo)
        layout_topo_dro.addWidget(self.btn_origem_rapida)
        layout_topo_dro.addStretch()
        layout_topo_dro.addWidget(self.lbl_indicador_feed_atual)
        layout_dro.addLayout(layout_topo_dro)

        # Linha dos 3 eixos (X, Y, Z) em 3 colunas elegantes
        layout_eixos = QHBoxLayout()
        layout_eixos.setSpacing(6)

        self.rotulo_posicao_x = QLabel("0.000")
        self.rotulo_posicao_y = QLabel("0.000")
        self.rotulo_posicao_z = QLabel("0.000")

        layout_eixos.addWidget(self._criar_linha_eixo_dro("X", self.rotulo_posicao_x, "#f87171"), 1)
        layout_eixos.addWidget(self._criar_linha_eixo_dro("Y", self.rotulo_posicao_y, "#4ade80"), 1)
        layout_eixos.addWidget(self._criar_linha_eixo_dro("Z", self.rotulo_posicao_z, "#5b7fff"), 1)

        layout_dro.addLayout(layout_eixos)
        return grupo_dro

    def _criar_linha_eixo_dro(self, nome_eixo: str, label_valor: QLabel, cor_eixo: str) -> QFrame:
        """Cria um bloco visual moderno para exibição e zeramento de um eixo no DRO."""
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
        botao_zerar.setFixedSize(30, 24)
        botao_zerar.setToolTip(f"Zerar eixo {nome_eixo} (G10 L20 P1 {nome_eixo}0)")
        botao_zerar.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: #252540;"
            f"  color: {cor_eixo};"
            f"  font-size: 11px;"
            f"  font-weight: 800;"
            f"  border: 1px solid #33334d;"
            f"  border-radius: 4px;"
            f"  padding: 0;"
            f"}}"
            f"QPushButton:hover {{ background-color: {cor_eixo}; color: white; }}"
        )
        botao_zerar.clicked.connect(lambda _, e=nome_eixo: self._zerar_eixo_individual(e))

        label_valor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_valor.setStyleSheet(
            "QLabel {"
            "  font-family: 'Consolas', 'Ubuntu Mono', monospace;"
            "  font-size: 16px;"
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

    # ------------------------------------------------------------------ #
    #                  PAINEL: ASSISTENTE DE CALIBRAÇÃO                  #
    # ------------------------------------------------------------------ #

    def _criar_painel_assistente(self) -> QGroupBox:
        """Cria a seção do Assistente de Calibração guiado passo a passo."""
        card_wizard = QGroupBox("🎯 Assistente de Calibração (Ponto)")
        card_wizard.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_wiz = QVBoxLayout(card_wizard)
        layout_wiz.setContentsMargins(10, 12, 10, 10)
        layout_wiz.setSpacing(8)

        # Linha 1: Identificador do Ponto Atual, Coordenadas e Z Máquina
        layout_info_ponto = QHBoxLayout()
        layout_info_ponto.setSpacing(6)

        self.lbl_info_passo = QLabel("Linha 1 de 4, Ponto 1 de 4")
        self.lbl_info_passo.setStyleSheet(
            "background-color: #1a1a35; color: #fbbf24; border: 1px solid #3a3a65; "
            "border-radius: 4px; padding: 4px 8px; font-weight: 800; font-size: 11px;"
        )

        self.lbl_coords_ponto = QLabel("X: 40.00 mm | Y: 40.00 mm")
        self.lbl_coords_ponto.setStyleSheet(
            "background-color: #1a1a35; color: #7da4ff; border: 1px solid #3a3a65; "
            "border-radius: 4px; padding: 4px 8px; font-weight: 700; font-size: 11px;"
        )

        self.lbl_z_maquina_chip = QLabel("Z Máq: 0.000 mm")
        self.lbl_z_maquina_chip.setStyleSheet(
            "background-color: #1a1a35; color: #4ade80; border: 1px solid #285535; "
            "border-radius: 4px; padding: 4px 8px; font-weight: 700; font-size: 11px;"
        )

        layout_info_ponto.addWidget(self.lbl_info_passo)
        layout_info_ponto.addWidget(self.lbl_coords_ponto, 1)
        layout_info_ponto.addWidget(self.lbl_z_maquina_chip)
        layout_wiz.addLayout(layout_info_ponto)

        # Linha 2: Botões de Movimentação do Cabeçote para o Ponto
        layout_nav_topo = QHBoxLayout()
        layout_nav_topo.setSpacing(6)

        self.btn_mover_para_ponto = QPushButton("🚀 1. Mover Cabeçote (Z-Up)")
        self.btn_mover_para_ponto.setToolTip("Translada em XY a uma altura segura (Z-Up), posicionando no ar sobre o nó")
        self.btn_mover_para_ponto.setStyleSheet(
            "QPushButton { background-color: #3b82f6; color: white; font-weight: bold; padding: 6px 10px; border: 1px solid #60a5fa; font-size: 11px; }"
            "QPushButton:hover { background-color: #2563eb; }"
        )
        self.btn_mover_para_ponto.clicked.connect(self._ao_mover_para_ponto_atual)

        self.btn_descer_z_salvo = QPushButton("⬇️ Descer p/ Z Alvo")
        self.btn_descer_z_salvo.setToolTip("Desce a caneta suavemente na posição XY atual até a altura Z de escrita")
        self.btn_descer_z_salvo.setStyleSheet(
            "QPushButton { background-color: #4338ca; border-color: #6366f1; font-weight: bold; padding: 6px 10px; font-size: 11px; }"
            "QPushButton:hover { background-color: #4f46e5; }"
        )
        self.btn_descer_z_salvo.clicked.connect(self._ao_descer_para_z_salvo)

        self.btn_pegar_z_maquina = QPushButton("📍 Usar Z Máquina")
        self.btn_pegar_z_maquina.setToolTip("Copia a coordenada Z atual reportada pelo GRBL para este ponto")
        self.btn_pegar_z_maquina.setStyleSheet("QPushButton { font-size: 11px; padding: 6px 8px; }")
        self.btn_pegar_z_maquina.clicked.connect(self._ao_copiar_z_maquina)

        layout_nav_topo.addWidget(self.btn_mover_para_ponto, 2)
        layout_nav_topo.addWidget(self.btn_descer_z_salvo, 1)
        layout_nav_topo.addWidget(self.btn_pegar_z_maquina, 1)
        layout_wiz.addLayout(layout_nav_topo)

        # Linha 3: Ajuste Fino de Z (Jog & Direct Input)
        layout_ajuste_z = QHBoxLayout()
        layout_ajuste_z.setSpacing(6)

        layout_ajuste_z.addWidget(QLabel("Altura Z (Ponto):"))
        self.spin_z_alvo = QDoubleSpinBox()
        self.spin_z_alvo.setRange(-20.0, 60.0)
        self.spin_z_alvo.setDecimals(3)
        self.spin_z_alvo.setSingleStep(0.1)
        self.spin_z_alvo.setValue(25.0)
        self.spin_z_alvo.setStyleSheet("font-weight: 800; font-size: 13px; color: #4ade80;")
        layout_ajuste_z.addWidget(self.spin_z_alvo, 1)

        self.btn_z_menos = QPushButton("▲ Z- (Subir)")
        self.btn_z_menos.setToolTip("Sobe o cabeçote em direção ao ar (-Z)")
        self.btn_z_menos.setStyleSheet("QPushButton { font-weight: 700; font-size: 11px; padding: 4px 8px; }")
        self.btn_z_menos.clicked.connect(lambda: self._ajustar_z_jog(-1))

        self.btn_z_mais = QPushButton("▼ Z+ (Descer)")
        self.btn_z_mais.setToolTip("Desce a caneta em direção ao papel (+Z)")
        self.btn_z_mais.setStyleSheet(
            "QPushButton { background-color: #4338ca; border-color: #6366f1; font-weight: bold; font-size: 11px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #4f46e5; }"
        )
        self.btn_z_mais.clicked.connect(lambda: self._ajustar_z_jog(1))

        self.btn_aplicar_z_todos = QPushButton("📋 Aplicar a Todos")
        self.btn_aplicar_z_todos.setToolTip("Define este valor Z como base inicial para todos os pontos da malha desta caneta")
        self.btn_aplicar_z_todos.setStyleSheet("QPushButton { font-size: 11px; padding: 4px 8px; }")
        self.btn_aplicar_z_todos.clicked.connect(self._ao_aplicar_z_todos_pontos)

        layout_ajuste_z.addWidget(self.btn_z_menos)
        layout_ajuste_z.addWidget(self.btn_z_mais)
        layout_ajuste_z.addWidget(self.btn_aplicar_z_todos)
        layout_wiz.addLayout(layout_ajuste_z)

        # Linha 4: Seletor de Passo Jog Z
        layout_passo = QHBoxLayout()
        layout_passo.setSpacing(4)
        layout_passo.addWidget(QLabel("Passo Z:"))
        self.grupo_passo_z = QButtonGroup(self)
        self.grupo_passo_z.setExclusive(True)
        self.botoes_passo_z = []

        for val in [1.0, 0.5, 0.1, 0.05, 0.01]:
            btn = QPushButton(f"{val:g} mm")
            btn.setCheckable(True)
            btn.setProperty("valor_passo", val)
            btn.setStyleSheet(
                "QPushButton { padding: 3px 6px; font-size: 11px; font-weight: 600; min-width: 44px; }"
                "QPushButton:checked { background-color: #5b7fff; color: white; border: 1px solid #7090ff; font-weight: 800; }"
            )
            if val == 0.1:
                btn.setChecked(True)
            self.grupo_passo_z.addButton(btn)
            btn.clicked.connect(self._ao_selecionar_passo_z)
            self.botoes_passo_z.append(btn)
            layout_passo.addWidget(btn)
        layout_wiz.addLayout(layout_passo)

        # Linha 5: Card de Teste do Traço com Feed Rate & Distância
        card_teste_traco = QFrame()
        card_teste_traco.setStyleSheet("background-color: #1a1a32; border: 1px solid #2e2e4a; border-radius: 6px; padding: 4px;")
        layout_traco = QVBoxLayout(card_teste_traco)
        layout_traco.setContentsMargins(6, 6, 6, 6)
        layout_traco.setSpacing(5)

        layout_traco_params = QHBoxLayout()
        layout_traco_params.setSpacing(6)

        layout_traco_params.addWidget(QLabel("Traço:"))
        self.spin_dist_traco = QDoubleSpinBox()
        self.spin_dist_traco.setRange(1.0, 50.0)
        self.spin_dist_traco.setValue(10.0)
        self.spin_dist_traco.setSuffix(" mm")
        layout_traco_params.addWidget(self.spin_dist_traco)

        layout_traco_params.addWidget(QLabel("Feed Traço:"))
        self.spin_feed_traco = QSpinBox()
        self.spin_feed_traco.setRange(100, 10000)
        self.spin_feed_traco.setValue(1000)
        self.spin_feed_traco.setSingleStep(100)
        self.spin_feed_traco.setSuffix(" mm/min")
        layout_traco_params.addWidget(self.spin_feed_traco)

        # Presets rápidos de velocidade para o traço
        self.btn_preset_traco_500 = QPushButton("500")
        self.btn_preset_traco_500.setToolTip("500 mm/min (Lento/Fino)")
        self.btn_preset_traco_500.setStyleSheet("QPushButton { padding: 3px 5px; font-size: 10px; }")
        self.btn_preset_traco_500.clicked.connect(lambda: self.spin_feed_traco.setValue(500))

        self.btn_preset_traco_1000 = QPushButton("1000")
        self.btn_preset_traco_1000.setToolTip("1000 mm/min (Padrão)")
        self.btn_preset_traco_1000.setStyleSheet("QPushButton { padding: 3px 5px; font-size: 10px; font-weight: bold; }")
        self.btn_preset_traco_1000.clicked.connect(lambda: self.spin_feed_traco.setValue(1000))

        self.btn_preset_traco_2000 = QPushButton("2000")
        self.btn_preset_traco_2000.setToolTip("2000 mm/min (Rápido)")
        self.btn_preset_traco_2000.setStyleSheet("QPushButton { padding: 3px 5px; font-size: 10px; }")
        self.btn_preset_traco_2000.clicked.connect(lambda: self.spin_feed_traco.setValue(2000))

        layout_traco_params.addWidget(self.btn_preset_traco_500)
        layout_traco_params.addWidget(self.btn_preset_traco_1000)
        layout_traco_params.addWidget(self.btn_preset_traco_2000)

        layout_traco.addLayout(layout_traco_params)

        self.btn_testar_traco = QPushButton("✏️ 2. Testar Ponto (Todos os Eixos)")
        self.btn_testar_traco.setToolTip("Desce para o Z alvo e executa um teste em estrela em todos os eixos e diagonais (Y+, Y-, X+, X-, Diagonais) na velocidade configurada")
        self.btn_testar_traco.setStyleSheet(
            "QPushButton { background-color: #eab308; color: #111827; font-weight: 800; padding: 7px 12px; border: 1px solid #facc15; font-size: 11px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #facc15; }"
        )
        self.btn_testar_traco.clicked.connect(self._ao_testar_traco_ponto)
        layout_traco.addWidget(self.btn_testar_traco)

        layout_wiz.addWidget(card_teste_traco)

        # Linha 6: Navegação e Salvar
        layout_nav_botoes = QHBoxLayout()
        layout_nav_botoes.setSpacing(6)

        self.btn_ponto_anterior = QPushButton("⬅ Ponto Anterior")
        self.btn_ponto_anterior.setStyleSheet("QPushButton { font-size: 11px; padding: 7px 10px; }")
        self.btn_ponto_anterior.clicked.connect(self._ao_ponto_anterior)

        self.btn_salvar_ponto = QPushButton("💾 3. Salvar Ponto")
        self.btn_salvar_ponto.setToolTip("Salva a altura Z calibrada para o ponto atual sem mover o cabeçote")
        self.btn_salvar_ponto.setStyleSheet(
            "QPushButton { background-color: #22c55e; color: white; font-weight: 800; padding: 8px 14px; border: 1px solid #4ade80; font-size: 12px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #16a34a; }"
        )
        self.btn_salvar_ponto.clicked.connect(self._ao_salvar_ponto)
        self.btn_salvar_avancar = self.btn_salvar_ponto

        self.btn_ponto_proximo = QPushButton("Próximo ➡")
        self.btn_ponto_proximo.setStyleSheet("QPushButton { font-size: 11px; padding: 7px 10px; }")
        self.btn_ponto_proximo.clicked.connect(self._ao_ponto_proximo)

        layout_nav_botoes.addWidget(self.btn_ponto_anterior)
        layout_nav_botoes.addWidget(self.btn_salvar_ponto, 2)
        layout_nav_botoes.addWidget(self.btn_ponto_proximo)

        layout_wiz.addLayout(layout_nav_botoes)
        return card_wizard

    # ------------------------------------------------------------------ #
    #               PAINEL: CONTROLE MANUAL (JOG) & FEED RATE            #
    # ------------------------------------------------------------------ #

    def _criar_painel_jog(self) -> QGroupBox:
        """
        Cria o painel ergonômico de controle manual (Jog) com D-Pad 3x3 balanceado,
        coluna dedicada de eixo Z e controle direto de Feed Rate.
        """
        grupo_jog = QGroupBox("🎮 Controle Manual (Joystick / Jog) & Velocidade")
        grupo_jog.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_jog = QVBoxLayout(grupo_jog)
        layout_jog.setContentsMargins(10, 12, 10, 10)
        layout_jog.setSpacing(8)

        layout_corpo_jog = QHBoxLayout()
        layout_corpo_jog.setSpacing(12)

        # 1. Bloco XY: D-Pad 3x3
        grid_xy = QGridLayout()
        grid_xy.setSpacing(3)

        largura_btn_xy = 50
        altura_btn_xy = 32

        estilo_direcional = (
            "QPushButton { background-color: #2c2c48; color: #e8e8f0; font-weight: 700; font-size: 11px; border: 1px solid #3a3a58; border-radius: 5px; padding: 0; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; border-color: #7090ff; }"
            "QPushButton:pressed { background-color: #4a6ae0; }"
        )
        estilo_diagonal = (
            "QPushButton { background-color: #252540; color: #9090a8; font-weight: 700; font-size: 11px; border: 1px solid #33334d; border-radius: 5px; padding: 0; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; border-color: #7090ff; }"
        )

        self.btn_jog_diag_no = QPushButton("↖")
        self.btn_jog_x_mais = QPushButton("X+")
        self.btn_jog_diag_ne = QPushButton("↗")

        self.btn_jog_y_mais = QPushButton("Y+")
        self.btn_jog_centro = QPushButton("🏠")
        self.btn_jog_y_menos = QPushButton("Y-")

        self.btn_jog_diag_so = QPushButton("↙")
        self.btn_jog_x_menos = QPushButton("X-")
        self.btn_jog_diag_se = QPushButton("↘")

        botoes_xy = [
            (self.btn_jog_diag_no, 0, 0, estilo_diagonal, "Noroeste (X+ Y+)"),
            (self.btn_jog_x_mais, 0, 1, estilo_direcional, "Mover X+ (Fundo)"),
            (self.btn_jog_diag_ne, 0, 2, estilo_diagonal, "Nordeste (X+ Y-)"),

            (self.btn_jog_y_mais, 1, 0, estilo_direcional, "Mover Y+ (Esquerda)"),
            (self.btn_jog_centro, 1, 1, estilo_diagonal, "Origem (0, 0)"),
            (self.btn_jog_y_menos, 1, 2, estilo_direcional, "Mover Y- (Direita)"),

            (self.btn_jog_diag_so, 2, 0, estilo_diagonal, "Sudoeste (X- Y+)"),
            (self.btn_jog_x_menos, 2, 1, estilo_direcional, "Mover X- (Frente)"),
            (self.btn_jog_diag_se, 2, 2, estilo_diagonal, "Sudeste (X- Y-)"),
        ]

        for b, linha, col, estilo, dica in botoes_xy:
            b.setFixedSize(largura_btn_xy, altura_btn_xy)
            b.setStyleSheet(estilo)
            b.setToolTip(dica)
            grid_xy.addWidget(b, linha, col)

        layout_corpo_jog.addLayout(grid_xy)

        # 2. Bloco Z: Coluna de Movimentação Vertical Z
        layout_coluna_z = QVBoxLayout()
        layout_coluna_z.setSpacing(3)

        estilo_eixo_z = (
            "QPushButton { background-color: #222248; color: #7da4ff; font-weight: 700; font-size: 10px; border: 1px solid #3a3a68; border-radius: 5px; padding: 2px 4px; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; }"
        )

        self.btn_jog_z_menos = QPushButton("▲ Subir (Z-)")
        self.btn_jog_z_menos.setFixedSize(94, 32)
        self.btn_jog_z_menos.setStyleSheet(estilo_eixo_z)
        self.btn_jog_z_menos.setToolTip("Subir eixo Z (Levantar no ar)")

        self.btn_jog_z_mais = QPushButton("▼ Descer (Z+)")
        self.btn_jog_z_mais.setFixedSize(94, 32)
        self.btn_jog_z_mais.setStyleSheet(estilo_eixo_z)
        self.btn_jog_z_mais.setToolTip("Descer eixo Z (Aproximar do papel)")

        self.btn_jog_z_zero = QPushButton("Z₀ Zerar Z")
        self.btn_jog_z_zero.setFixedSize(94, 32)
        self.btn_jog_z_zero.setStyleSheet(
            "QPushButton { background-color: #252540; color: #5b7fff; font-weight: 800; font-size: 10px; border: 1px solid #3a3a58; border-radius: 5px; padding: 2px 4px; }"
            "QPushButton:hover { background-color: #5b7fff; color: white; }"
        )
        self.btn_jog_z_zero.setToolTip("Zerar coordenada de trabalho do eixo Z")

        layout_coluna_z.addWidget(self.btn_jog_z_menos)
        layout_coluna_z.addWidget(self.btn_jog_z_mais)
        layout_coluna_z.addWidget(self.btn_jog_z_zero)

        layout_corpo_jog.addLayout(layout_coluna_z)

        # 3. Bloco Direita: Parâmetros de Passo e Feed Rate
        layout_params = QVBoxLayout()
        layout_params.setSpacing(4)

        # Passo XY & Passo Z
        layout_passos_inputs = QHBoxLayout()
        layout_passos_inputs.setSpacing(6)

        layout_passos_inputs.addWidget(QLabel("Passo XY:"))
        self.input_jog_passo_xy = SpinBoxPassoAdaptativo()
        self.input_jog_passo_xy.setValue(1.0)
        layout_passos_inputs.addWidget(self.input_jog_passo_xy)

        layout_passos_inputs.addWidget(QLabel("Passo Z:"))
        self.input_jog_passo_z = SpinBoxPassoAdaptativo()
        self.input_jog_passo_z.setValue(0.5)
        layout_passos_inputs.addWidget(self.input_jog_passo_z)

        layout_params.addLayout(layout_passos_inputs)

        # Feed Rate com SpinBox e Presets Rápidos
        layout_feed_linha = QHBoxLayout()
        layout_feed_linha.setSpacing(4)

        lbl_feed = QLabel("Feed:")
        lbl_feed.setToolTip("Velocidade de translação para o controle manual (mm/min)")
        layout_feed_linha.addWidget(lbl_feed)

        self.input_jog_feed_rate = QSpinBox()
        self.input_jog_feed_rate.setRange(1, 15000)
        self.input_jog_feed_rate.setValue(2500)
        self.input_jog_feed_rate.setSingleStep(100)
        self.input_jog_feed_rate.setSuffix(" mm/min")
        self.input_jog_feed_rate.valueChanged.connect(self._ao_mudar_feed_rate_jog)
        layout_feed_linha.addWidget(self.input_jog_feed_rate, 1)

        btn_feed_500 = QPushButton("500")
        btn_feed_500.setToolTip("Velocidade Lenta: 500 mm/min")
        btn_feed_500.setStyleSheet("QPushButton { padding: 3px 5px; font-size: 10px; }")
        btn_feed_500.clicked.connect(lambda: self.input_jog_feed_rate.setValue(500))

        btn_feed_1500 = QPushButton("1500")
        btn_feed_1500.setToolTip("Velocidade Média: 1500 mm/min")
        btn_feed_1500.setStyleSheet("QPushButton { padding: 3px 5px; font-size: 10px; }")
        btn_feed_1500.clicked.connect(lambda: self.input_jog_feed_rate.setValue(1500))

        btn_feed_3000 = QPushButton("3000")
        btn_feed_3000.setToolTip("Velocidade Rápida: 3000 mm/min")
        btn_feed_3000.setStyleSheet("QPushButton { padding: 3px 5px; font-size: 10px; font-weight: bold; }")
        btn_feed_3000.clicked.connect(lambda: self.input_jog_feed_rate.setValue(3000))

        layout_feed_linha.addWidget(btn_feed_500)
        layout_feed_linha.addWidget(btn_feed_1500)
        layout_feed_linha.addWidget(btn_feed_3000)

        layout_params.addLayout(layout_feed_linha)
        layout_corpo_jog.addLayout(layout_params, 1)

        layout_jog.addLayout(layout_corpo_jog)

        # 4. Linha de Seletores Rápidos de Passo XY
        layout_passos_rapidos = QHBoxLayout()
        layout_passos_rapidos.setSpacing(4)
        lbl_passo_rap = QLabel("Passo Rápido:")
        lbl_passo_rap.setStyleSheet("font-size: 11px; color: #9090a8;")
        layout_passos_rapidos.addWidget(lbl_passo_rap)

        self.grupo_jog_botoes_passo = QButtonGroup(self)
        valores_passo = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
        for valor in valores_passo:
            botao_passo = QPushButton(f"{valor:g} mm")
            botao_passo.setCheckable(True)
            botao_passo.setStyleSheet(
                "QPushButton { padding: 3px 6px; font-size: 11px; font-weight: 600; min-width: 36px; }"
                "QPushButton:checked { background-color: #5b7fff; color: white; border-color: #7090ff; }"
            )
            if valor == 1.0:
                botao_passo.setChecked(True)
            self.grupo_jog_botoes_passo.addButton(botao_passo)
            layout_passos_rapidos.addWidget(botao_passo)
            botao_passo.clicked.connect(lambda _, v=valor: self.input_jog_passo_xy.setValue(v))

        layout_jog.addLayout(layout_passos_rapidos)

        # Conectar ações dos botões direcionais
        self.btn_jog_x_mais.clicked.connect(lambda: self._mover_eixo_jog("X", 1))
        self.btn_jog_x_menos.clicked.connect(lambda: self._mover_eixo_jog("X", -1))
        self.btn_jog_y_mais.clicked.connect(lambda: self._mover_eixo_jog("Y", 1))
        self.btn_jog_y_menos.clicked.connect(lambda: self._mover_eixo_jog("Y", -1))
        self.btn_jog_z_menos.clicked.connect(lambda: self._mover_eixo_jog("Z", -1))
        self.btn_jog_z_mais.clicked.connect(lambda: self._mover_eixo_jog("Z", 1))
        self.btn_jog_z_zero.clicked.connect(lambda: self._zerar_eixo_individual("Z"))

        self.btn_jog_diag_no.clicked.connect(lambda: self._mover_diagonal_jog(1, 1))
        self.btn_jog_diag_ne.clicked.connect(lambda: self._mover_diagonal_jog(1, -1))
        self.btn_jog_diag_so.clicked.connect(lambda: self._mover_diagonal_jog(-1, 1))
        self.btn_jog_diag_se.clicked.connect(lambda: self._mover_diagonal_jog(-1, -1))
        self.btn_jog_centro.clicked.connect(self._mover_para_origem_jog)

        return grupo_jog

    # ------------------------------------------------------------------ #
    #             PAINEL: CONFIGURAÇÃO DE MALHA & Z-UP SEGURO            #
    # ------------------------------------------------------------------ #

    def _criar_painel_config_malha_zup(self) -> QGroupBox:
        """Cria o painel conjunto para Z-Up seguro e dimensões da malha."""
        grupo = QGroupBox("⚙️ Configurações da Malha & Trânsito Seguro (Z-Up)")
        grupo.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_grid = QGridLayout(grupo)
        layout_grid.setContentsMargins(10, 12, 10, 10)
        layout_grid.setSpacing(6)

        # Seção Z-Up Seguro
        layout_grid.addWidget(QLabel("🛡️ Z-Up (Ar):"), 0, 0)
        self.spin_z_up = QDoubleSpinBox()
        self.spin_z_up.setRange(-100.0, 100.0)
        self.spin_z_up.setDecimals(2)
        self.spin_z_up.setSingleStep(0.5)
        self.spin_z_up.setValue(-4.0)
        self.spin_z_up.setSuffix(" mm")
        self.spin_z_up.setStyleSheet("font-weight: 700; color: #60a5fa;")
        layout_grid.addWidget(self.spin_z_up, 0, 1)

        self.btn_testar_z_up = QPushButton("▲ Subir")
        self.btn_testar_z_up.setToolTip("Move a máquina imediatamente para a altura segura Z-Up")
        self.btn_testar_z_up.setStyleSheet("QPushButton { font-size: 11px; padding: 4px 6px; }")
        self.btn_testar_z_up.clicked.connect(self._ao_testar_z_up)
        layout_grid.addWidget(self.btn_testar_z_up, 0, 2)

        self.btn_capturar_z_up = QPushButton("📍 Usar Z")
        self.btn_capturar_z_up.setToolTip("Copia a altura Z atual do GRBL para o campo Z-Up")
        self.btn_capturar_z_up.setStyleSheet("QPushButton { font-size: 11px; padding: 4px 6px; }")
        self.btn_capturar_z_up.clicked.connect(self._ao_capturar_z_up)
        layout_grid.addWidget(self.btn_capturar_z_up, 0, 3)

        self.btn_salvar_z_up = QPushButton("💾 Salvar Z-Up")
        self.btn_salvar_z_up.setStyleSheet("QPushButton { font-weight: 700; font-size: 11px; padding: 4px 6px; }")
        self.btn_salvar_z_up.clicked.connect(self._ao_salvar_z_up)
        layout_grid.addWidget(self.btn_salvar_z_up, 0, 4)

        self.btn_aplicar_todas_z_up = QPushButton("📋 Replicar a Todas")
        self.btn_aplicar_todas_z_up.setToolTip("Aplica este Z-Up a todas as 10 canetas")
        self.btn_aplicar_todas_z_up.setStyleSheet("QPushButton { font-size: 11px; padding: 4px 6px; }")
        self.btn_aplicar_todas_z_up.clicked.connect(self._ao_aplicar_z_up_todas)
        layout_grid.addWidget(self.btn_aplicar_todas_z_up, 0, 5)

        # Seção Dimensões da Malha
        layout_grid.addWidget(QLabel("Linhas (Y):"), 1, 0)
        self.spin_num_linhas = QSpinBox()
        self.spin_num_linhas.setRange(2, 20)
        self.spin_num_linhas.setValue(4)
        self.spin_num_linhas.valueChanged.connect(self._ao_alterar_dimensoes_malha)
        layout_grid.addWidget(self.spin_num_linhas, 1, 1)

        layout_grid.addWidget(QLabel("Pontos (X):"), 1, 2)
        self.spin_pontos_por_linha = QSpinBox()
        self.spin_pontos_por_linha.setRange(2, 20)
        self.spin_pontos_por_linha.setValue(3)
        self.spin_pontos_por_linha.valueChanged.connect(self._ao_alterar_dimensoes_malha)
        layout_grid.addWidget(self.spin_pontos_por_linha, 1, 3)

        self.lbl_total_pontos = QLabel("Total: 12 pontos")
        self.lbl_total_pontos.setStyleSheet("color: #7da4ff; font-weight: 700; font-size: 11px;")
        layout_grid.addWidget(self.lbl_total_pontos, 1, 4)

        self.btn_redefinir_malha = QPushButton("🔄 Redefinir")
        self.btn_redefinir_malha.setStyleSheet("QPushButton { font-size: 11px; padding: 4px 6px; }")
        self.btn_redefinir_malha.clicked.connect(self._ao_clicar_redefinir_malha)
        layout_grid.addWidget(self.btn_redefinir_malha, 1, 5)

        # Toggle de Compensação Dinâmica
        self.check_nivelamento_ativo = QCheckBox("⚡ Ativar Compensação Dinâmica de Nivelamento no G-code")
        self.check_nivelamento_ativo.setChecked(self.gerenciador_nivelamento.esta_nivelamento_ativo())
        self.check_nivelamento_ativo.toggled.connect(self._ao_alternar_compensacao_ativa)
        self.check_nivelamento_ativo.setStyleSheet("font-weight: bold; color: #4ade80; margin-top: 2px;")
        layout_grid.addWidget(self.check_nivelamento_ativo, 2, 0, 1, 6)

        return grupo

    # ------------------------------------------------------------------ #
    #                       CONEXÕES E SINCRONIZAÇÃO                     #
    # ------------------------------------------------------------------ #

    def _conectar_sinais(self) -> None:
        self.controlador_grbl.sinal_posicao_atualizada.connect(self._ao_atualizar_posicao_grbl)
        self.controlador_grbl.sinal_status_atualizado.connect(self._ao_atualizar_status_grbl)
        self.controlador_grbl.sinal_conexao_alterada.connect(self._ao_atualizar_conexao_grbl)
        self.gerenciador_nivelamento.sinal_nivelamento_atualizado.connect(self._ao_atualizar_nivelamento)
        self.gerenciador_canetas.sinal_slots_atualizados.connect(self._sincronizar_combo_canetas)
        self.gerenciador_canetas.sinal_caneta_alterada.connect(self._ao_alterar_caneta_ativa_cabecote)

    def _preencher_combo_canetas(self) -> None:
        self.combo_canetas.clear()
        slots = self.gerenciador_canetas.obter_todos_slots()
        for slot in slots:
            self.combo_canetas.addItem(f"Caneta {slot.id} — {slot.nome}", slot.id)

    def _sincronizar_combo_canetas(self) -> None:
        idx_atual = self.combo_canetas.currentIndex()
        self._preencher_combo_canetas()
        if 0 <= idx_atual < self.combo_canetas.count():
            self.combo_canetas.setCurrentIndex(idx_atual)

    def _carregar_dados_caneta(self, id_caneta: int, recarregar_ponto: bool = True) -> None:
        self._caneta_selecionada_id = id_caneta
        malha = self.gerenciador_nivelamento.obter_malha_caneta(id_caneta)
        if not malha:
            return

        # Pill de cor
        self.lbl_pill_cor.setText(f" {id_caneta} ")
        self.lbl_pill_cor.setStyleSheet(
            f"background-color: {malha.cor_hex}; font-weight: 800; border-radius: 4px; color: white;"
        )

        # SpinBoxes de Linhas e Colunas
        self._bloqueando_atualizacao = True
        self.spin_num_linhas.blockSignals(True)
        self.spin_pontos_por_linha.blockSignals(True)
        self.spin_num_linhas.setValue(malha.num_linhas)
        self.spin_pontos_por_linha.setValue(malha.num_pontos_por_linha)
        self.spin_num_linhas.blockSignals(False)
        self.spin_pontos_por_linha.blockSignals(False)
        self._bloqueando_atualizacao = False

        total = malha.num_linhas * malha.num_pontos_por_linha
        calibrados = sum(1 for p in malha.pontos if p.calibrado)
        porcentagem = int((calibrados / max(1, total)) * 100)
        self.progresso_calib.setValue(porcentagem)

        if malha.calibrado:
            self.badge_status_calib.setText(f"🟢 Calibrada ({malha.num_linhas}x{malha.num_pontos_por_linha})")
            self.badge_status_calib.setStyleSheet(
                "background-color: #1a3a2a; color: #4ade80; border: 1px solid #285535; "
                "border-radius: 4px; padding: 4px 8px; font-weight: 700; font-size: 11px;"
            )
        else:
            self.badge_status_calib.setText(f"🟡 {calibrados}/{total} Pontos")
            self.badge_status_calib.setStyleSheet(
                "background-color: #3a321a; color: #fbbf24; border: 1px solid #5a4a25; "
                "border-radius: 4px; padding: 4px 8px; font-weight: 700; font-size: 11px;"
            )

        self.lbl_total_pontos.setText(f"Total: {total} pontos")
        self.lbl_info_dimensoes_malha.setText(f"{malha.num_linhas}x{malha.num_pontos_por_linha} ({total} pontos)")

        # Traço params - atualiza somente se não estiver em foco de edição
        if not self.spin_dist_traco.hasFocus():
            self.spin_dist_traco.blockSignals(True)
            self.spin_dist_traco.setValue(malha.distancia_teste_traco)
            self.spin_dist_traco.blockSignals(False)

        if not self.spin_feed_traco.hasFocus():
            self.spin_feed_traco.blockSignals(True)
            self.spin_feed_traco.setValue(malha.feed_teste_traco)
            self.spin_feed_traco.blockSignals(False)

        # Z-Up - atualiza somente se não estiver em foco de edição
        if not self.spin_z_up.hasFocus():
            self.spin_z_up.blockSignals(True)
            self.spin_z_up.setValue(malha.z_up)
            self.spin_z_up.blockSignals(False)

        self._atualizar_botao_engate()
        self.visualizador_malha.definir_caneta(id_caneta)
        self._carregar_ponto_atual(manter_z_alvo=(not recarregar_ponto))

    def _ao_alterar_caneta_ativa_cabecote(self, id_caneta: int, nome: str, cor_hex: str) -> None:
        """Atualiza a exibição em tempo real do cabeçote quando a ferramenta muda."""
        if id_caneta and id_caneta > 0:
            self.lbl_pill_engatada.setText(f" {id_caneta} ")
            self.lbl_pill_engatada.setStyleSheet(
                f"background-color: {cor_hex}; font-weight: 800; border-radius: 4px; color: white;"
            )
            self.lbl_status_cabecote.setText(f"Caneta {id_caneta} ({nome}) — Acoplada")
            self.btn_devolver_caneta.setEnabled(True)
        else:
            self.lbl_pill_engatada.setText(" ⚪ ")
            self.lbl_pill_engatada.setStyleSheet(
                "background-color: #333348; font-weight: 800; border-radius: 4px; color: #8888a0;"
            )
            self.lbl_status_cabecote.setText("Cabeçote Livre / Vazio (Nenhuma Caneta)")
            self.btn_devolver_caneta.setEnabled(False)

        self.visualizador_malha.atualizar_caneta_engatada(id_caneta, nome, cor_hex)
        self._atualizar_botao_engate()

    def _atualizar_botao_engate(self) -> None:
        """Atualiza o texto e estilo do botão de engate de acordo com a caneta atual no cabeçote."""
        caneta_engatada = self.gerenciador_canetas.obter_caneta_ativa_id()
        if caneta_engatada == self._caneta_selecionada_id:
            self.btn_engatar_caneta.setText(f"✔ Caneta {self._caneta_selecionada_id} Já Engatada")
            self.btn_engatar_caneta.setStyleSheet(
                "QPushButton { background-color: #166534; color: #4ade80; font-weight: bold; border: 1px solid #22c55e; font-size: 11px; padding: 5px 10px; }"
            )
        elif caneta_engatada:
            self.btn_engatar_caneta.setText(f"⚡ Trocar p/ Caneta {self._caneta_selecionada_id}")
            self.btn_engatar_caneta.setStyleSheet(
                "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; font-size: 11px; padding: 5px 10px; }"
                "QPushButton:hover { background-color: #4a6ae0; }"
            )
        else:
            self.btn_engatar_caneta.setText(f"⚡ Engatar Caneta {self._caneta_selecionada_id}")
            self.btn_engatar_caneta.setStyleSheet(
                "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; font-size: 11px; padding: 5px 10px; }"
                "QPushButton:hover { background-color: #4a6ae0; }"
            )

    def _ao_clicar_devolver_caneta(self) -> None:
        caneta_atual = self.gerenciador_canetas.obter_caneta_ativa_id()
        if not caneta_atual:
            # Fallback inteligente: se não houver caneta explicitamente ativa no estado, usar a selecionada no painel
            caneta_atual = self._caneta_selecionada_id
            if not caneta_atual:
                QMessageBox.information(self, "Aviso", "O cabeçote já está vazio.")
                return

        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de devolver a caneta.")
            return

        slot = self.gerenciador_canetas.obter_slot(caneta_atual)
        z_seguro = slot.z_seguro if slot else -4.0
        velocidade = slot.velocidade if slot else 3000

        gcode_soltar = self.gerenciador_canetas.gerar_gcode_soltar_caneta(caneta_atual)

        # Verificação de segurança: garantir elevação antes de ir à baia se a caneta estiver baixa
        if self.controlador_grbl.caneta_esta_abaixada():
            gcode_soltar = f"G90\nG21\nG0 Z{z_seguro:.2f} F{velocidade}\n" + gcode_soltar

        self.controlador_grbl.enviar_script_gcode(
            conteudo=gcode_soltar,
            nome=f"Devolver Caneta {caneta_atual}",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(None)
        )

    def _carregar_ponto_atual(self, manter_z_alvo: bool = False) -> None:
        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        if not malha or not malha.pontos:
            return

        self._indice_linha_atual = max(0, min(malha.num_linhas - 1, self._indice_linha_atual))
        self._indice_coluna_atual = max(0, min(malha.num_pontos_por_linha - 1, self._indice_coluna_atual))

        ponto = None
        for p in malha.pontos:
            if p.linha == self._indice_linha_atual and p.coluna == self._indice_coluna_atual:
                ponto = p
                break

        if not ponto and malha.pontos:
            ponto = malha.pontos[0]
            self._indice_linha_atual = ponto.linha
            self._indice_coluna_atual = ponto.coluna

        if ponto:
            self.lbl_info_passo.setText(
                f"Linha {ponto.linha+1} de {malha.num_linhas}, Ponto {ponto.coluna+1} de {malha.num_pontos_por_linha}"
            )
            self.lbl_coords_ponto.setText(f"X: {ponto.x:.2f} mm | Y: {ponto.y:.2f} mm")
            if not manter_z_alvo:
                self.spin_z_alvo.blockSignals(True)
                self.spin_z_alvo.setValue(ponto.z)
                self.spin_z_alvo.blockSignals(False)
            self.visualizador_malha.definir_ponto_ativo(ponto.linha, ponto.coluna)

    # ------------------------------------------------------------------ #
    #                       AÇÕES DE CALIBRAÇÃO                          #
    # ------------------------------------------------------------------ #

    def _ao_trocar_caneta_combo(self, index: int) -> None:
        if index < 0:
            return
        id_caneta = self.combo_canetas.itemData(index)
        if id_caneta:
            self._indice_linha_atual = 0
            self._indice_coluna_atual = 0
            self._carregar_dados_caneta(id_caneta)

    def _ao_clicar_engatar_caneta(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de trocar de caneta.")
            return

        gcode_troca = self.gerenciador_canetas.gerar_gcode_troca_completa(self._caneta_selecionada_id)
        self.controlador_grbl.enviar_script_gcode(
            conteudo=gcode_troca,
            nome=f"Engate Caneta {self._caneta_selecionada_id}",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(self._caneta_selecionada_id)
        )

    def _ao_alterar_dimensoes_malha(self) -> None:
        """Atualiza dinamicamente e em tempo real a malha da caneta ao mudar os spinboxes."""
        if self._bloqueando_atualizacao:
            return

        num_linhas = self.spin_num_linhas.value()
        num_pontos = self.spin_pontos_por_linha.value()

        malha_atual = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        if malha_atual and malha_atual.num_linhas == num_linhas and malha_atual.num_pontos_por_linha == num_pontos:
            return

        self.gerenciador_nivelamento.redimensionar_malha_caneta(
            self._caneta_selecionada_id,
            num_linhas,
            num_pontos,
            manter_valores_z=True
        )

        total = num_linhas * num_pontos
        self.lbl_total_pontos.setText(f"Total: {total} pontos")
        self.lbl_info_dimensoes_malha.setText(f"{num_linhas}x{num_pontos} ({total} pontos)")
        self.visualizador_malha.definir_caneta(self._caneta_selecionada_id)
        self._carregar_ponto_atual()

    def _ao_clicar_redefinir_malha(self) -> None:
        num_linhas = self.spin_num_linhas.value()
        num_pontos = self.spin_pontos_por_linha.value()

        resposta = QMessageBox.question(
            self,
            "Redefinir Malha",
            f"Deseja gerar uma nova malha de {num_linhas} linhas x {num_pontos} pontos para a Caneta {self._caneta_selecionada_id}?\n"
            "Os valores existentes de Z serão interpolados na nova grade.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self.gerenciador_nivelamento.redimensionar_malha_caneta(
                self._caneta_selecionada_id,
                num_linhas,
                num_pontos,
                manter_valores_z=True
            )
            self._carregar_dados_caneta(self._caneta_selecionada_id)

    def _ao_alternar_compensacao_ativa(self, ativo: bool) -> None:
        self.gerenciador_nivelamento.definir_nivelamento_ativo(ativo)

    def _ao_clicar_ponto_visualizador(self, linha: int, coluna: int) -> None:
        self._indice_linha_atual = linha
        self._indice_coluna_atual = coluna
        self._carregar_ponto_atual()

    def _ao_mover_para_ponto_atual(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover.")
            return

        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        if not malha:
            return

        ponto = next(
            (p for p in malha.pontos if p.linha == self._indice_linha_atual and p.coluna == self._indice_coluna_atual),
            None
        )
        if not ponto:
            return

        z_up = malha.z_up
        feed_jog = self.input_jog_feed_rate.value()

        script_mover = (
            f"G90 ; Coordenadas absolutas\n"
            f"G0 Z{z_up:.2f} F3000 ; Elevar para Z-Up seguro no ar\n"
            f"G0 X{ponto.x:.2f} Y{ponto.y:.2f} F{feed_jog} ; Mover para o ponto\n"
        )
        self.controlador_grbl.enviar_script_gcode(
            conteudo=script_mover,
            nome=f"Mover P{ponto.coluna+1} L{ponto.linha+1}"
        )

    def _ao_descer_para_z_salvo(self) -> None:
        """Desce a caneta suavemente até a altura de escrita/contato alvo configurada."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover.")
            return
        z_alvo = self.spin_z_alvo.value()
        script = f"G90\nG1 Z{z_alvo:.2f} F600\n"
        self.controlador_grbl.enviar_script_gcode(
            conteudo=script,
            nome=f"Descer para Z={z_alvo:.2f}"
        )

    def _ao_aplicar_z_todos_pontos(self) -> None:
        """Aplica o Z alvo atual como valor base para todos os pontos da malha desta caneta."""
        z_valor = self.spin_z_alvo.value()
        resposta = QMessageBox.question(
            self,
            "Aplicar Z a Todos os Pontos",
            f"Deseja definir Z = {z_valor:.2f} mm como valor base para todos os pontos da Caneta {self._caneta_selecionada_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resposta == QMessageBox.StandardButton.Yes:
            malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
            if malha:
                malha.z_down = round(z_valor, 3)
                for p in malha.pontos:
                    p.z = round(z_valor, 3)
                    p.calibrado = True
                malha.calibrado = True
                self.gerenciador_nivelamento._salvar_configuracao()
                self.gerenciador_nivelamento.sinal_nivelamento_atualizado.emit()
                self._carregar_ponto_atual()
                QMessageBox.information(
                    self,
                    "Sucesso",
                    f"Valor Z = {z_valor:.2f} mm aplicado como base para todos os pontos da malha!"
                )

    def _ao_testar_z_up(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de testar.")
            return
        z_up = self.spin_z_up.value()
        self.controlador_grbl.enviar_script_gcode(
            conteudo=f"G90\nG0 Z{z_up:.2f} F3000\n",
            nome=f"Subir Z-Up ({z_up:.2f}mm)"
        )

    def _ao_capturar_z_up(self) -> None:
        z_atual = self.controlador_grbl.obter_posicao_z()
        self.spin_z_up.setValue(z_atual)

    def _ao_salvar_z_up(self) -> None:
        z_up = self.spin_z_up.value()
        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        z_down = malha.z_down if malha else 25.0
        self.gerenciador_nivelamento.definir_z_up_down(self._caneta_selecionada_id, z_up, z_down)
        QMessageBox.information(
            self,
            "Sucesso",
            f"Altura de segurança Z-Up salva para a Caneta {self._caneta_selecionada_id}: {z_up:.2f} mm"
        )

    def _ao_aplicar_z_up_todas(self) -> None:
        z_up = self.spin_z_up.value()
        resposta = QMessageBox.question(
            self,
            "Aplicar a Todas",
            f"Deseja aplicar Z-Up = {z_up:.2f} mm a todas as 10 canetas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resposta == QMessageBox.StandardButton.Yes:
            malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
            z_down = malha.z_down if malha else 25.0
            self.gerenciador_nivelamento.definir_z_up_down(self._caneta_selecionada_id, z_up, z_down)
            self.gerenciador_nivelamento.copiar_z_up_down_para_todas(self._caneta_selecionada_id)
            QMessageBox.information(
                self,
                "Sucesso",
                "Altura Z-Up aplicada com sucesso para todas as 10 canetas!"
            )

    def _ao_copiar_z_maquina(self) -> None:
        z_atual = self.controlador_grbl.obter_posicao_z()
        self.spin_z_alvo.setValue(z_atual)

    def _ao_selecionar_passo_z(self) -> None:
        sender = self.sender()
        if not sender:
            return
        sender.setChecked(True)
        self._passo_jog_z = float(sender.property("valor_passo"))

    def _ajustar_z_jog(self, direcao: int) -> None:
        """
        Ajusta Z no spinbox e envia movimentação jog.
        direcao = +1: Descer (Z+, aproximando do papel)
        direcao = -1: Subir (Z-, levantando em direção ao ar)
        """
        delta = self._passo_jog_z * direcao
        novo_z = self.spin_z_alvo.value() + delta
        self.spin_z_alvo.setValue(novo_z)

        if self.controlador_grbl.esta_conectado():
            self.controlador_grbl.mover_eixo("Z", direcao, self._passo_jog_z, 600)

    def _ao_testar_traco_ponto(self) -> None:
        """
        Executa o teste do ponto:
        Garante que Z está na altura alvo e faz um teste completo em estrela
        cobrindo todos os eixos e diagonais (Y+, Y-, X+, X-, Diagonais) no papel.
        """
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de testar.")
            return

        dist_traco = self.spin_dist_traco.value()
        feed_traco = self.spin_feed_traco.value()
        z_alvo = self.spin_z_alvo.value()

        # Salvar parâmetros do traço para a caneta
        self.gerenciador_nivelamento.definir_parametros_traco(
            self._caneta_selecionada_id,
            dist_traco,
            feed_traco
        )

        script_teste = (
            f"G90\n"
            f"G1 Z{z_alvo:.3f} F600 ; Descer para altura de teste\n"
            f"G91 ; Modo relativo\n"
            f"; 1. Y+ e volta\n"
            f"G1 Y{dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 Y{-dist_traco:.2f} F{feed_traco}\n"
            f"; 2. Y- e volta\n"
            f"G1 Y{-dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 Y{dist_traco:.2f} F{feed_traco}\n"
            f"; 3. X+ e volta\n"
            f"G1 X{dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 X{-dist_traco:.2f} F{feed_traco}\n"
            f"; 4. X- e volta\n"
            f"G1 X{-dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 X{dist_traco:.2f} F{feed_traco}\n"
            f"; 5. Diagonal superior esquerda (X- Y+) e volta\n"
            f"G1 X{-dist_traco:.2f} Y{dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 X{dist_traco:.2f} Y{-dist_traco:.2f} F{feed_traco}\n"
            f"; 6. Diagonal inferior direita (X+ Y-) e volta\n"
            f"G1 X{dist_traco:.2f} Y{-dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 X{-dist_traco:.2f} Y{dist_traco:.2f} F{feed_traco}\n"
            f"; 7. Diagonal superior direita (X+ Y+) e volta\n"
            f"G1 X{dist_traco:.2f} Y{dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 X{-dist_traco:.2f} Y{-dist_traco:.2f} F{feed_traco}\n"
            f"; 8. Diagonal inferior esquerda (X- Y-) e volta\n"
            f"G1 X{-dist_traco:.2f} Y{-dist_traco:.2f} F{feed_traco}\n"
            f"G4 P0.05\n"
            f"G1 X{dist_traco:.2f} Y{dist_traco:.2f} F{feed_traco}\n"
            f"G90 ; Retornar a modo absoluto\n"
        )
        self.controlador_grbl.enviar_script_gcode(
            conteudo=script_teste,
            nome=f"Teste Ponto L{self._indice_linha_atual+1} P{self._indice_coluna_atual+1}"
        )

    def _ao_salvar_ponto(self) -> None:
        """Salva o Z calibrado do ponto atual sem avançar automaticamente."""
        z_valor = self.spin_z_alvo.value()
        self.gerenciador_nivelamento.definir_ponto_z(
            self._caneta_selecionada_id,
            self._indice_linha_atual,
            self._indice_coluna_atual,
            z_valor
        )

        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        self._carregar_dados_caneta(self._caneta_selecionada_id, recarregar_ponto=False)
        self._carregar_ponto_atual(manter_z_alvo=True)

        if hasattr(self, "visualizador_malha"):
            self.visualizador_malha.update()

    def _ao_salvar_e_avancar(self) -> None:
        """Alias para compatibilidade retroativa."""
        self._ao_salvar_ponto()

    def _ao_ponto_anterior(self) -> None:
        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        if not malha:
            return

        if self._indice_coluna_atual > 0:
            self._indice_coluna_atual -= 1
        elif self._indice_linha_atual > 0:
            self._indice_linha_atual -= 1
            self._indice_coluna_atual = malha.num_pontos_por_linha - 1

        self._carregar_ponto_atual()
        if self.controlador_grbl.esta_conectado():
            self._ao_mover_para_ponto_atual()

    def _ao_ponto_proximo(self) -> None:
        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        if not malha:
            return

        if self._indice_coluna_atual < malha.num_pontos_por_linha - 1:
            self._indice_coluna_atual += 1
        elif self._indice_linha_atual < malha.num_linhas - 1:
            self._indice_linha_atual += 1
            self._indice_coluna_atual = 0

        self._carregar_ponto_atual()
        if self.controlador_grbl.esta_conectado():
            self._ao_mover_para_ponto_atual()

    def _ao_importar_offsets(self) -> None:
        """Abre o diálogo para importar arquivo JSON de calibração de offsets."""
        caminho_arquivo, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Offsets Calibrados",
            "",
            "Arquivos de Calibração (*.json);;Todos os Arquivos (*)"
        )
        if not caminho_arquivo:
            return

        sucesso, msg, total = self.gerenciador_nivelamento.importar_calibracao_de_arquivo(caminho_arquivo)
        if sucesso:
            self._sincronizar_combo_canetas()
            self._carregar_dados_caneta(self._caneta_selecionada_id)
            if hasattr(self, "visualizador_malha"):
                self.visualizador_malha.update()

            QMessageBox.information(
                self,
                "Importação Concluída",
                f"✅ {msg}\n\nOs offsets e pontos calibrados foram carregados e salvos com sucesso!"
            )
        else:
            QMessageBox.critical(
                self,
                "Erro ao Importar",
                f"❌ Não foi possível importar os offsets:\n{msg}"
            )

    def _ao_exportar_offsets(self) -> None:
        """Abre o diálogo para salvar arquivo JSON com as calibrações atuais."""
        caminho_arquivo, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Offsets Calibrados",
            "nivelamento_canetas_backup.json",
            "Arquivos de Calibração (*.json);;Todos os Arquivos (*)"
        )
        if not caminho_arquivo:
            return

        sucesso, msg = self.gerenciador_nivelamento.exportar_calibracao_para_arquivo(caminho_arquivo)
        if sucesso:
            QMessageBox.information(self, "Exportação Concluída", f"✅ {msg}")
        else:
            QMessageBox.critical(self, "Erro ao Exportar", f"❌ {msg}")

    def _ao_copiar_para_todas(self) -> None:
        resposta = QMessageBox.question(
            self,
            "Copiar para Todas",
            f"Deseja aplicar a calibração da Caneta {self._caneta_selecionada_id} para todas as outras 9 canetas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self.gerenciador_nivelamento.copiar_malha_para_todas_canetas(self._caneta_selecionada_id)
            QMessageBox.information(self, "Sucesso", "Malha copiada com sucesso para todas as 10 canetas!")
            self._carregar_dados_caneta(self._caneta_selecionada_id, recarregar_ponto=False)

    def _ao_resetar_calibracao(self) -> None:
        resposta = QMessageBox.question(
            self,
            "Resetar Calibração",
            f"Deseja zerar todos os pontos calibrados da Caneta {self._caneta_selecionada_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self.gerenciador_nivelamento.resetar_calibracao_caneta(self._caneta_selecionada_id)
            self._carregar_dados_caneta(self._caneta_selecionada_id)

    # ------------------------------------------------------------------ #
    #                       COMANDOS JOG & DRO                           #
    # ------------------------------------------------------------------ #

    def _mover_eixo_jog(self, eixo: str, direcao: int) -> None:
        """Envia comando jog para o eixo especificado com verificação de conexão."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover.")
            return

        if eixo.upper() == "Z":
            passo = self.input_jog_passo_z.value()
        else:
            passo = self.input_jog_passo_xy.value()

        feed_rate = self.input_jog_feed_rate.value()
        self.controlador_grbl.mover_eixo(eixo, direcao, passo, feed_rate)

    def _mover_diagonal_jog(self, direcao_x: int, direcao_y: int) -> None:
        """Envia comando jog diagonal simultâneo nos eixos X e Y."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover.")
            return

        passo = self.input_jog_passo_xy.value()
        feed_rate = self.input_jog_feed_rate.value()
        self.controlador_grbl.mover_eixos_diagonais(direcao_x, direcao_y, passo, feed_rate)

    def _mover_para_origem_jog(self) -> None:
        """Move o cabeçote para a origem (0, 0) com elevação prévia para Z seguro."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de mover.")
            return
        malha = self.gerenciador_nivelamento.obter_malha_caneta(self._caneta_selecionada_id)
        z_seguro = malha.z_up if malha else -4.0
        feed_jog = self.input_jog_feed_rate.value()
        gcode_origem = f"G90\nG0 Z{z_seguro:.2f} F3000\nG0 X0 Y0 F{feed_jog}\n"
        self.controlador_grbl.enviar_script_gcode(gcode_origem, nome="Mover para Origem (0, 0)")

    def _zerar_eixo_individual(self, eixo: str) -> None:
        """Zera a coordenada de trabalho de um eixo individual."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", f"Conecte a máquina para zerar o eixo {eixo}.")
            return
        self.controlador_grbl.zerar_eixo(eixo)

    def _zerar_todos_eixos(self) -> None:
        """Zera as coordenadas de trabalho de todos os eixos (X, Y, Z)."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial para zerar as coordenadas.")
            return
        self.controlador_grbl.zerar_coordenadas()

    def _ao_mudar_feed_rate_jog(self, valor: int) -> None:
        self.lbl_indicador_feed_atual.setText(f"⚡ Feed: {valor} mm/min")

    # ------------------------------------------------------------------ #
    #                       SINCRONIZAÇÃO DE SLOTS                       #
    # ------------------------------------------------------------------ #

    @Slot(float, float, float)
    def _ao_atualizar_posicao_grbl(self, x: float, y: float, z: float) -> None:
        self.rotulo_posicao_x.setText(f"{x:.3f}")
        self.rotulo_posicao_y.setText(f"{y:.3f}")
        self.rotulo_posicao_z.setText(f"{z:.3f}")
        self.lbl_z_maquina_chip.setText(f"Z Máq: {z:.3f} mm")
        self.visualizador_malha.atualizar_posicao_maquina(x, y, z)

    @Slot(str)
    def _ao_atualizar_status_grbl(self, status: str) -> None:
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
            f"QLabel {{ {estilo} font-size: 11px; font-weight: 800; letter-spacing: 1px; border-radius: 5px; padding: 0 8px; }}"
        )

    @Slot(bool)
    def _ao_atualizar_conexao_grbl(self, conectado: bool) -> None:
        if not conectado:
            self.rotulo_estado_dro.setText("DESCONECTADO")
            self.rotulo_estado_dro.setStyleSheet(
                "QLabel { background-color: #1e1e35; color: #6a6a82; font-size: 11px; font-weight: 800; letter-spacing: 1px; border: 1px solid #2e2e4a; border-radius: 5px; padding: 0 8px; }"
            )

    @Slot()
    def _ao_atualizar_nivelamento(self) -> None:
        self._carregar_dados_caneta(self._caneta_selecionada_id, recarregar_ponto=False)

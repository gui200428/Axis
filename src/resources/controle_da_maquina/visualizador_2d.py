"""
Módulo de visualização 2D interativa em tempo real da mesa da plotter AXIS.

Renderiza a área de trabalho da máquina (calibrada dinamicamente via firmware),
as 10 estações/slots de caneta com suas cores, posição física de HOME no canto inferior direito,
cabeçote da plotter em movimento ao vivo e preview fiel das trajetórias de G-code com suporte a zoom e pan.
"""

import math
import re
from typing import List, Tuple, Optional, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt, QPointF, QRectF, Slot
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QWheelEvent, QMouseEvent, QPaintEvent
)

from resources.controle_da_maquina.gerenciador_canetas import GerenciadorCanetas


def interpolar_arco_gcode(
    ponto_inicio: QPointF,
    ponto_fim: QPointF,
    offset_i: Optional[float],
    offset_j: Optional[float],
    raio: Optional[float],
    sentido_horario: bool,
    num_max_segmentos: int = 36
) -> List[Tuple[QPointF, QPointF]]:
    """
    Interpola um arco circular 2D (G2/G3) em pequenos segmentos lineares para renderização visual.

    Args:
        ponto_inicio (QPointF): Coordenada inicial do arco na mesa (mm).
        ponto_fim (QPointF): Coordenada final do arco na mesa (mm).
        offset_i (float, optional): Offset X relativo do centro do arco (I).
        offset_j (float, optional): Offset Y relativo do centro do arco (J).
        raio (float, optional): Raio do arco (R).
        sentido_horario (bool): True se o arco for no sentido horário (G2), False se anti-horário (G3).
        num_max_segmentos (int): Quantidade máxima de subdivisões lineares para suavização.

    Returns:
        List[Tuple[QPointF, QPointF]]: Lista de tuplas contendo segmentos de reta conectando o arco.
    """
    x0, y0 = ponto_inicio.x(), ponto_inicio.y()
    x1, y1 = ponto_fim.x(), ponto_fim.y()

    if offset_i is not None or offset_j is not None:
        cx = x0 + (offset_i if offset_i is not None else 0.0)
        cy = y0 + (offset_j if offset_j is not None else 0.0)
        r = math.hypot(x0 - cx, y0 - cy)
    elif raio is not None and raio > 0.0:
        r = raio
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        if dist > 2.0 * r or dist < 1e-6:
            return [(ponto_inicio, ponto_fim)]
        h = math.sqrt(max(0.0, r * r - (dist / 2.0) ** 2))
        mx = (x0 + x1) / 2.0
        my = (y0 + y1) / 2.0
        nx = -dy / dist
        ny = dx / dist
        if sentido_horario:
            cx = mx + nx * h
            cy = my + ny * h
        else:
            cx = mx - nx * h
            cy = my - ny * h
    else:
        return [(ponto_inicio, ponto_fim)]

    if r < 1e-4:
        return [(ponto_inicio, ponto_fim)]

    ang_ini = math.atan2(y0 - cy, x0 - cx)
    ang_fim = math.atan2(y1 - cy, x1 - cx)

    is_circulo_fechado = (math.hypot(x1 - x0, y1 - y0) < 1e-4)

    if sentido_horario:
        if is_circulo_fechado:
            sweep = -2.0 * math.pi
        else:
            if ang_fim >= ang_ini:
                ang_fim -= 2.0 * math.pi
            sweep = ang_fim - ang_ini
    else:
        if is_circulo_fechado:
            sweep = 2.0 * math.pi
        else:
            if ang_fim <= ang_ini:
                ang_fim += 2.0 * math.pi
            sweep = ang_fim - ang_ini

    passos = max(4, min(num_max_segmentos, int(math.ceil(abs(sweep) / (math.pi / 18)))))
    segmentos: List[Tuple[QPointF, QPointF]] = []
    ponto_anterior = ponto_inicio
    for k in range(1, passos + 1):
        frac = k / passos
        ang = ang_ini + frac * sweep
        px = cx + r * math.cos(ang)
        py = cy + r * math.sin(ang)
        ponto_atual = QPointF(px, py)
        segmentos.append((ponto_anterior, ponto_atual))
        ponto_anterior = ponto_atual

    return segmentos


class CanvasVisualizador2D(QWidget):
    """
    Área de desenho personalizada com aceleração gráfica para renderizar a mesa 2D.
    """

    def __init__(
        self,
        gerenciador_canetas: Optional[GerenciadorCanetas] = None,
        gerenciador_macros: Optional[Any] = None,
        gerenciador_area: Optional[Any] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.gerenciador_canetas = gerenciador_canetas
        self.gerenciador_macros = gerenciador_macros
        self.gerenciador_area = gerenciador_area

        # Dimensões da mesa de trabalho em milímetros (atualizadas dinamicamente via GRBL $130/$131)
        self.limite_x: float = 330.0
        self.limite_y: float = 328.0

        # Coordenadas da área de desenho da caneta (X e Y início/fim)
        self.area_x_inicio: float = 60.0
        self.area_y_inicio: float = 10.0
        self.area_x_fim: float = 270.0
        self.area_y_fim: float = 307.0

        if self.gerenciador_area is not None:
            cfg = self.gerenciador_area.obter_configuracao()
            self.area_x_inicio = cfg.x_inicio
            self.area_y_inicio = cfg.y_inicio
            self.area_x_fim = cfg.x_fim
            self.area_y_fim = cfg.y_fim
            self.gerenciador_area.sinal_area_alterada.connect(self.atualizar_area_desenho)

        # Posição atual da máquina (X, Y, Z)
        self.pos_x: float = 0.0
        self.pos_y: float = 0.0
        self.pos_z: float = 0.0

        # Caneta ativa
        self.caneta_ativa_id: Optional[int] = None
        self.cor_caneta_ativa = QColor("#5b7fff")

        # Trajetórias de pré-visualização de G-code (G0 e G1)
        self.linhas_preview_g0: List[Tuple[QPointF, QPointF]] = []
        self.linhas_preview_g1: List[Tuple[QPointF, QPointF]] = []

        # Transformações de câmera (Zoom e Pan)
        self.escala_zoom: float = 1.0
        self.deslocamento_pan = QPointF(0.0, 0.0)
        self._arrastando_mouse = False
        self._ultimo_pos_mouse = QPointF()

        self.setMouseTracking(True)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #15152a;")

    def definir_gerenciador_macros(self, gerenciador: Any) -> None:
        """Define o gerenciador de macros para expansão de macros no preview de G-code."""
        self.gerenciador_macros = gerenciador

    def definir_gerenciador_canetas(self, gerenciador: GerenciadorCanetas) -> None:
        """Define o gerenciador de canetas para expansão de trocas no preview."""
        self.gerenciador_canetas = gerenciador

    # ------------------------------------------------------------------ #
    #                     TRANSFORMAÇÕES DE COORDENADAS                  #
    # ------------------------------------------------------------------ #

    def mm_para_tela(self, x_mm: float, y_mm: float) -> QPointF:
        """
        Converte coordenadas em milímetros (origem 0,0 no canto inferior direito)
        para coordenadas de pixels na tela.

        Args:
            x_mm (float): Coordenada no eixo X da máquina em milímetros.
            y_mm (float): Coordenada no eixo Y da máquina em milímetros.

        Returns:
            QPointF: Ponto correspondente em pixels no canvas.
        """
        largura_tela = self.width()
        altura_tela = self.height()
        margem = 40.0

        # Y da máquina -> eixo horizontal do mapa (largura)
        # X da máquina -> eixo vertical do mapa (altura)
        escala_base_h = (largura_tela - 2 * margem) / max(1.0, self.limite_y)
        escala_base_v = (altura_tela - 2 * margem) / max(1.0, self.limite_x)
        fator_base = min(escala_base_h, escala_base_v) * self.escala_zoom

        largura_mesa = self.limite_y * fator_base  # Y da máquina na horizontal
        altura_mesa = self.limite_x * fator_base   # X da máquina na vertical

        offset_x = (largura_tela - largura_mesa) / 2.0 + self.deslocamento_pan.x()
        offset_y = (altura_tela - altura_mesa) / 2.0 + self.deslocamento_pan.y()

        # Origem (0, 0) no canto inferior direito:
        # Y da máquina cresce para a esquerda no mapa: y_mm = 0 -> direita, y_mm = limite_y -> esquerda
        # X da máquina cresce para cima no mapa: x_mm = 0 -> base, x_mm = limite_x -> topo
        px = (offset_x + largura_mesa) - (y_mm * fator_base)
        py = (offset_y + altura_mesa) - (x_mm * fator_base)
        return QPointF(px, py)

    def obter_fator_escala(self) -> float:
        """
        Retorna o fator de escala atual de mm para pixels.

        Returns:
            float: Fator multiplicativo de escala da visualização.
        """
        margem = 40.0
        escala_base_h = (self.width() - 2 * margem) / max(1.0, self.limite_y)
        escala_base_v = (self.height() - 2 * margem) / max(1.0, self.limite_x)
        return min(escala_base_h, escala_base_v) * self.escala_zoom

    # ------------------------------------------------------------------ #
    #                           EVENTOS DE DESENHO                       #
    # ------------------------------------------------------------------ #

    def paintEvent(self, evento: QPaintEvent) -> None:
        """
        Renderiza todos os elementos gráficos do canvas 2D da plotter.

        Args:
            evento (QPaintEvent): Evento de pintura disparado pelo Qt.
        """
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pintor.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        pintor.fillRect(self.rect(), QColor("#15152a"))

        # 1. Desenhar a Grade Milimétrica e Área da Mesa
        self._desenhar_grade_e_mesa(pintor)

        # 2. Desenhar a Área de Desenho da Caneta (Retângulo delimitador)
        self._desenhar_area_desenho(pintor)

        # 3. Desenhar a indicação de HOME no canto inferior direito
        self._desenhar_indicador_home(pintor)

        # 4. Desenhar o Preview do G-code
        self._desenhar_preview_gcode(pintor)

        # 5. Desenhar as 10 Estações/Slots de Caneta
        self._desenhar_estacoes_canetas(pintor)

        # 6. Desenhar o Cabeçote / Ferramenta da Plotter
        self._desenhar_cabecote(pintor)

        # 7. HUD de status
        self._desenhar_overlay_status(pintor)

        pintor.end()

    def _desenhar_grade_e_mesa(self, pintor: QPainter) -> None:
        """
        Desenha o retângulo de fundo da mesa de trabalho com linhas de grade e réguas graduadas.

        Args:
            pintor (QPainter): Instância ativa do pintor gráfico.
        """
        p_topo_esq = self.mm_para_tela(self.limite_x, self.limite_y)
        p_baixo_dir = self.mm_para_tela(0.0, 0.0)

        retangulo_mesa = QRectF(
            p_topo_esq.x(),
            p_topo_esq.y(),
            p_baixo_dir.x() - p_topo_esq.x(),
            p_baixo_dir.y() - p_topo_esq.y()
        )

        # Fundo da mesa de trabalho
        pintor.fillRect(retangulo_mesa, QColor("#1e1e35"))
        pen_borda = QPen(QColor("#33334d"), 1.2)
        pintor.setPen(pen_borda)
        pintor.drawRect(retangulo_mesa)

        fator = self.obter_fator_escala()
        passo_grade = 50.0 if fator < 0.8 else 10.0

        pen_fina = QPen(QColor("#28284a"), 0.8, Qt.PenStyle.DotLine)
        pen_media = QPen(QColor("#33335a"), 1.0)
        fonte_regua = QFont("Consolas", 8)
        pintor.setFont(fonte_regua)

        # Linhas horizontais (X constante → linhas horizontais no mapa)
        # X da máquina é o eixo vertical: rótulos na borda direita
        x_mm = 0.0
        while x_mm <= self.limite_x + 0.1:
            pt_dir = self.mm_para_tela(x_mm, 0.0)
            pt_esq = self.mm_para_tela(x_mm, self.limite_y)
            if int(round(x_mm)) % 50 == 0:
                pintor.setPen(pen_media)
                pintor.drawLine(pt_esq, pt_dir)
                pintor.setPen(QColor("#6a6a82"))
                pintor.drawText(QPointF(pt_dir.x() + 6, pt_dir.y() + 4), f"{int(round(x_mm))}")
                pintor.drawText(QPointF(pt_esq.x() - 28, pt_esq.y() + 4), f"{int(round(x_mm))}")
            elif passo_grade == 10.0:
                pintor.setPen(pen_fina)
                pintor.drawLine(pt_esq, pt_dir)
            x_mm += 10.0

        # Linhas verticais (Y constante → linhas verticais no mapa)
        # Y da máquina é o eixo horizontal: rótulos na borda inferior
        y_mm = 0.0
        while y_mm <= self.limite_y + 0.1:
            pt_baixo = self.mm_para_tela(0.0, y_mm)
            pt_cima = self.mm_para_tela(self.limite_x, y_mm)
            if int(round(y_mm)) % 50 == 0:
                pintor.setPen(pen_media)
                pintor.drawLine(pt_baixo, pt_cima)
                pintor.setPen(QColor("#6a6a82"))
                pintor.drawText(QPointF(pt_baixo.x() - 10, pt_baixo.y() + 15), f"{int(round(y_mm))}")
            elif passo_grade == 10.0:
                pintor.setPen(pen_fina)
                pintor.drawLine(pt_baixo, pt_cima)
            y_mm += 10.0

        # Origem (0, 0) no canto inferior direito
        p_origem = self.mm_para_tela(0.0, 0.0)
        # Eixo Y+ (verde) aponta para a esquerda (alinha com estojos)
        pintor.setPen(QPen(QColor("#4ade80"), 2.0))
        pintor.drawLine(p_origem, QPointF(p_origem.x() - 25, p_origem.y()))
        pintor.drawText(QPointF(p_origem.x() - 38, p_origem.y() + 4), "Y+")

        # Eixo X+ (vermelho) aponta para cima (aproxima dos estojos)
        pintor.setPen(QPen(QColor("#f87171"), 2.0))
        pintor.drawLine(p_origem, QPointF(p_origem.x(), p_origem.y() - 25))
        pintor.drawText(QPointF(p_origem.x() - 6, p_origem.y() - 28), "X+")

    def _desenhar_area_desenho(self, pintor: QPainter) -> None:
        """
        Renderiza a área de desenho delimitada pelas coordenadas (x_inicio, y_inicio)
        e (x_fim, y_fim) sobre a mesa da plotter.

        Args:
            pintor (QPainter): Instância ativa do pintor gráfico.
        """
        x_min = min(self.area_x_inicio, self.area_x_fim)
        x_max = max(self.area_x_inicio, self.area_x_fim)
        y_min = min(self.area_y_inicio, self.area_y_fim)
        y_max = max(self.area_y_inicio, self.area_y_fim)

        largura_mm = y_max - y_min  # Horizontal (Y)
        altura_mm = x_max - x_min   # Vertical (X)

        if largura_mm <= 0.1 or altura_mm <= 0.1:
            return

        p_tl = self.mm_para_tela(x_max, y_max)
        p_br = self.mm_para_tela(x_min, y_min)

        retangulo_desenho = QRectF(
            p_tl.x(),
            p_tl.y(),
            p_br.x() - p_tl.x(),
            p_br.y() - p_tl.y()
        )

        # Fundo translúcido para destacar a área de desenho
        pintor.fillRect(retangulo_desenho, QColor(91, 127, 255, 20))

        # Borda tracejada elegante
        pen_borda = QPen(QColor("#5b7fff"), 1.4, Qt.PenStyle.DashLine)
        pintor.setPen(pen_borda)
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.drawRect(retangulo_desenho)

        # Marcadores de canto (L-brackets de enquadramento)
        tam_canto = min(12.0, min(retangulo_desenho.width(), retangulo_desenho.height()) / 4.0)
        pen_canto = QPen(QColor("#7da4ff"), 2.0, Qt.PenStyle.SolidLine)
        pintor.setPen(pen_canto)

        # Canto Superior Esquerdo
        pintor.drawLine(QPointF(retangulo_desenho.left(), retangulo_desenho.top()), QPointF(retangulo_desenho.left() + tam_canto, retangulo_desenho.top()))
        pintor.drawLine(QPointF(retangulo_desenho.left(), retangulo_desenho.top()), QPointF(retangulo_desenho.left(), retangulo_desenho.top() + tam_canto))

        # Canto Superior Direito
        pintor.drawLine(QPointF(retangulo_desenho.right(), retangulo_desenho.top()), QPointF(retangulo_desenho.right() - tam_canto, retangulo_desenho.top()))
        pintor.drawLine(QPointF(retangulo_desenho.right(), retangulo_desenho.top()), QPointF(retangulo_desenho.right(), retangulo_desenho.top() + tam_canto))

        # Canto Inferior Esquerdo
        pintor.drawLine(QPointF(retangulo_desenho.left(), retangulo_desenho.bottom()), QPointF(retangulo_desenho.left() + tam_canto, retangulo_desenho.bottom()))
        pintor.drawLine(QPointF(retangulo_desenho.left(), retangulo_desenho.bottom()), QPointF(retangulo_desenho.left(), retangulo_desenho.bottom() - tam_canto))

        # Canto Inferior Direito
        pintor.drawLine(QPointF(retangulo_desenho.right(), retangulo_desenho.bottom()), QPointF(retangulo_desenho.right() - tam_canto, retangulo_desenho.bottom()))
        pintor.drawLine(QPointF(retangulo_desenho.right(), retangulo_desenho.bottom()), QPointF(retangulo_desenho.right(), retangulo_desenho.bottom() - tam_canto))

        # Rótulo informativo da área de desenho
        fonte_tag = QFont("Segoe UI", 8, QFont.Weight.Bold)
        pintor.setFont(fonte_tag)
        texto_rotulo = f"Área de Desenho ({largura_mm:.0f}×{altura_mm:.0f} mm)"

        largura_tag = 170
        altura_tag = 18
        tag_rect = QRectF(retangulo_desenho.left() + 4, retangulo_desenho.top() + 4, largura_tag, altura_tag)
        pintor.setBrush(QColor(26, 26, 50, 200))
        pintor.setPen(QPen(QColor("#3d5bc7"), 1.0))
        pintor.drawRoundedRect(tag_rect, 3, 3)
        pintor.setPen(QColor("#a0b4ff"))
        pintor.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, texto_rotulo)

    def _desenhar_indicador_home(self, pintor: QPainter) -> None:
        """
        Desenha o marcador físico de HOME no canto inferior direito (0, 0) da mesa de trabalho.

        Args:
            pintor (QPainter): Instância ativa do pintor gráfico.
        """
        pt_home = self.mm_para_tela(0.0, 0.0)

        pintor.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        ret_home = QRectF(pt_home.x() - 40, pt_home.y() + 20, 80, 18)
        pintor.setBrush(QColor("#2a2a55"))
        pintor.setPen(QPen(QColor("#5b7fff"), 1.0))
        pintor.drawRoundedRect(ret_home, 3, 3)

        pintor.setPen(QColor("#a0b4ff"))
        pintor.drawText(ret_home, Qt.AlignmentFlag.AlignCenter, "🏠 HOME (0,0)")

        # Círculo alvo no ponto exato
        pintor.setBrush(QColor("#5b7fff"))
        pintor.setPen(QPen(QColor("#ffffff"), 1.2))
        pintor.drawEllipse(pt_home, 5, 5)

    def _desenhar_estacoes_canetas(self, pintor: QPainter) -> None:
        """
        Renderiza as 10 baias/slots de caneta com suas cores correspondentes.

        Args:
            pintor (QPainter): Instância ativa do pintor gráfico.
        """
        if not self.gerenciador_canetas:
            return

        slots = self.gerenciador_canetas.obter_todos_slots()
        fonte_slot = QFont("Segoe UI", 8, QFont.Weight.Bold)
        pintor.setFont(fonte_slot)

        for slot in slots:
            pt = self.mm_para_tela(slot.x_pegar, slot.y_pegar)
            raio = 9.0
            cor_caneta = QColor(slot.cor_hex)

            # Sombra da baia
            pintor.setBrush(QColor("#222240"))
            pintor.setPen(QPen(QColor("#3a3a58"), 1.2))
            pintor.drawRoundedRect(QRectF(pt.x() - 13, pt.y() - 13, 26, 26), 4, 4)

            esta_acoplada = (self.caneta_ativa_id == slot.id)
            if esta_acoplada:
                pintor.setBrush(Qt.BrushStyle.NoBrush)
                pintor.setPen(QPen(cor_caneta, 1.5, Qt.PenStyle.DashLine))
                pintor.drawEllipse(pt, raio, raio)
            else:
                pintor.setBrush(cor_caneta)
                pintor.setPen(QPen(QColor("#ffffff"), 1.0))
                pintor.drawEllipse(pt, raio, raio)

                pintor.setPen(QColor("#ffffff") if cor_caneta.lightness() < 130 else QColor("#000000"))
                pintor.drawText(QRectF(pt.x() - 9, pt.y() - 9, 18, 18), Qt.AlignmentFlag.AlignCenter, f"{slot.id}")

    def _desenhar_preview_gcode(self, pintor: QPainter) -> None:
        """
        Desenha as linhas de trajetória de G-code interpretadas no canvas (G0 pontilhado, G1 traço sólido).

        Args:
            pintor (QPainter): Instância ativa do pintor gráfico.
        """
        if self.linhas_preview_g0:
            pen_g0 = QPen(QColor("#44446a"), 1.0, Qt.PenStyle.DotLine)
            pintor.setPen(pen_g0)
            for p1_mm, p2_mm in self.linhas_preview_g0:
                p1_tela = self.mm_para_tela(p1_mm.x(), p1_mm.y())
                p2_tela = self.mm_para_tela(p2_mm.x(), p2_mm.y())
                pintor.drawLine(p1_tela, p2_tela)

        if self.linhas_preview_g1:
            pen_g1 = QPen(QColor("#7da4ff"), 1.2)
            pintor.setPen(pen_g1)
            for p1_mm, p2_mm in self.linhas_preview_g1:
                p1_tela = self.mm_para_tela(p1_mm.x(), p1_mm.y())
                p2_tela = self.mm_para_tela(p2_mm.x(), p2_mm.y())
                pintor.drawLine(p1_tela, p2_tela)

    def _desenhar_cabecote(self, pintor: QPainter) -> None:
        """
        Desenha o marcador do cabeçote móvel da máquina com retículo e estado de Z (PEN UP / PEN DOWN).

        Args:
            pintor (QPainter): Instância ativa do pintor gráfico.
        """
        pos_tela = self.mm_para_tela(self.pos_x, self.pos_y)

        pen_reticulo = QPen(QColor("#7da4ff"), 0.8, Qt.PenStyle.DashLine)
        pintor.setPen(pen_reticulo)
        pintor.drawLine(QPointF(pos_tela.x() - 20, pos_tela.y()), QPointF(pos_tela.x() + 20, pos_tela.y()))
        pintor.drawLine(QPointF(pos_tela.x(), pos_tela.y() - 20), QPointF(pos_tela.x(), pos_tela.y() + 20))

        pen_cabecote = QPen(QColor("#7da4ff"), 1.8)
        pintor.setPen(pen_cabecote)
        pintor.setBrush(QColor(27, 27, 47, 180))
        pintor.drawEllipse(pos_tela, 12, 12)

        pen_abaixada = (self.pos_z < -0.05)
        cor_ponta = self.cor_caneta_ativa if self.caneta_ativa_id else QColor("#9090a8")
        pintor.setBrush(cor_ponta)
        pintor.setPen(QPen(QColor("#ffffff") if pen_abaixada else QColor("#55556e"), 1.5))
        raio_ponta = 6.0 if pen_abaixada else 4.0
        pintor.drawEllipse(pos_tela, raio_ponta, raio_ponta)

        status_z = "PEN DOWN" if pen_abaixada else "PEN UP"
        cor_z = QColor("#4ade80") if pen_abaixada else QColor("#9090a8")
        pintor.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        pintor.setPen(cor_z)
        pintor.drawText(QPointF(pos_tela.x() + 15, pos_tela.y() - 4), status_z)

    def _desenhar_overlay_status(self, pintor: QPainter) -> None:
        """
        Desenha o HUD textual com informações de zoom e dimensões da mesa e área útil.

        Args:
            pintor (QPainter): Instância ativa do pintor gráfico.
        """
        fonte_hud = QFont("Consolas", 8)
        pintor.setFont(fonte_hud)
        pintor.setPen(QColor("#6a6a82"))

        largura_desenho = abs(self.area_y_fim - self.area_y_inicio)
        altura_desenho = abs(self.area_x_fim - self.area_x_inicio)
        texto_zoom = (
            f"Zoom: {self.escala_zoom * 100:.0f}%  |  "
            f"Mesa: {self.limite_x:.0f}x{self.limite_y:.0f}mm (Firmware)  |  "
            f"Área Desenho: {largura_desenho:.0f}x{altura_desenho:.0f}mm "
            f"(X:{min(self.area_x_inicio, self.area_x_fim):.0f}..{max(self.area_x_inicio, self.area_x_fim):.0f}, "
            f"Y:{min(self.area_y_inicio, self.area_y_fim):.0f}..{max(self.area_y_inicio, self.area_y_fim):.0f})"
        )
        pintor.drawText(QPointF(10, self.height() - 10), texto_zoom)

    # ------------------------------------------------------------------ #
    #                      INTERAÇÃO DE MOUSE (ZOOM & PAN)               #
    # ------------------------------------------------------------------ #

    def wheelEvent(self, evento: QWheelEvent) -> None:
        """
        Altera o nível de zoom da visualização através da roda do mouse.

        Args:
            evento (QWheelEvent): Evento da roda do mouse.
        """
        delta = evento.angleDelta().y()
        fator = 1.15 if delta > 0 else 0.85
        novo_zoom = max(0.3, min(5.0, self.escala_zoom * fator))
        self.escala_zoom = novo_zoom
        self.update()

    def mousePressEvent(self, evento: QMouseEvent) -> None:
        """
        Inicia a operação de arrasto (pan) da visualização com o botão do mouse.

        Args:
            evento (QMouseEvent): Evento de clique do mouse.
        """
        if evento.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._arrastando_mouse = True
            self._ultimo_pos_mouse = evento.position()

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:
        """
        Atualiza o deslocamento de translação (pan) da câmera ao arrastar o mouse.

        Args:
            evento (QMouseEvent): Evento de movimento do mouse.
        """
        if self._arrastando_mouse:
            delta = evento.position() - self._ultimo_pos_mouse
            self.deslocamento_pan += delta
            self._ultimo_pos_mouse = evento.position()
            self.update()

    def mouseReleaseEvent(self, evento: QMouseEvent) -> None:
        """
        Finaliza a operação de arrasto do mouse.

        Args:
            evento (QMouseEvent): Evento de soltura do botão do mouse.
        """
        self._arrastando_mouse = False

    # ------------------------------------------------------------------ #
    #                     SLOTS E ATUALIZAÇÕES PÚBLICAS                  #
    # ------------------------------------------------------------------ #

    @Slot(float, float, float)
    def atualizar_posicao(self, x: float, y: float, z: float) -> None:
        """
        Atualiza a posição do cabeçote em tempo real e redesenha o canvas.

        Args:
            x (float): Posição no eixo X em mm.
            y (float): Posição no eixo Y em mm.
            z (float): Posição no eixo Z em mm.
        """
        self.pos_x = x
        self.pos_y = y
        self.pos_z = z
        self.update()

    @Slot(int, str, str)
    def atualizar_caneta_ativa(self, id_caneta: int, nome: str, cor_hex: str) -> None:
        """
        Atualiza a caneta engatada no cabeçote e sua cor correspondente.

        Args:
            id_caneta (int): Número da caneta (1 a 10) ou 0 para livre.
            nome (str): Nome descritivo da caneta.
            cor_hex (str): Cor em hexadecimal da caneta ativa.
        """
        self.caneta_ativa_id = id_caneta if id_caneta > 0 else None
        self.cor_caneta_ativa = QColor(cor_hex)
        self.update()

    @Slot(float, float, float)
    def atualizar_limites_mesa(self, max_x: float, max_y: float, max_z: float) -> None:
        """
        Atualiza a área útil a partir dos dados $130, $131 recebidos do firmware.

        Args:
            max_x (float): Curso máximo do eixo X em mm.
            max_y (float): Curso máximo do eixo Y em mm.
            max_z (float): Curso máximo do eixo Z em mm.
        """
        alterou = False
        if max_x > 10 and max_x != self.limite_x:
            self.limite_x = max_x
            alterou = True
        if max_y > 10 and max_y != self.limite_y:
            self.limite_y = max_y
            alterou = True

        if alterou:
            self.ajustar_vista()
        self.update()

    @Slot(float, float, float, float)
    def atualizar_area_desenho(self, x_inicio: float, y_inicio: float, x_fim: float, y_fim: float) -> None:
        """
        Atualiza as coordenadas delimitadoras da área de desenho da caneta.

        Args:
            x_inicio (float): Posição inicial X em mm.
            y_inicio (float): Posição inicial Y em mm.
            x_fim (float): Posição final X em mm.
            y_fim (float): Posição final Y em mm.
        """
        self.area_x_inicio = x_inicio
        self.area_y_inicio = y_inicio
        self.area_x_fim = x_fim
        self.area_y_fim = y_fim
        self.update()

    def limpar_trilha(self) -> None:
        """
        Limpa todas as trajetórias de pré-visualização de G-code do canvas.
        """
        self.linhas_preview_g0.clear()
        self.linhas_preview_g1.clear()
        self.update()

    def ajustar_vista(self) -> None:
        """
        Redefine o zoom e a translação para enquadrar a mesa perfeitamente no centro.
        """
        self.escala_zoom = 1.0
        self.deslocamento_pan = QPointF(0.0, 0.0)
        self.update()

    def _expandir_gcode_preview(self, conteudo_gcode: str) -> str:
        """
        Expande macros de canetas e macros do usuário para cálculo exato do preview.

        Args:
            conteudo_gcode (str): Bloco de texto contendo comandos G-code.

        Returns:
            str: Código G-code expandido com rotinas substituídas.
        """
        texto = conteudo_gcode

        # Expansão de macros de usuário se disponível
        if self.gerenciador_macros is not None:
            try:
                texto = self.gerenciador_macros.expandir_macros_em_gcode(texto)
            except Exception:
                pass

        # Expansão de comandos de caneta se disponível
        if self.gerenciador_canetas is not None:
            gc = self.gerenciador_canetas
            caneta_simulada = gc.obter_caneta_ativa_id()
            padrao_trocar = re.compile(r'^TROCA[R]?[_\s]?(?:CANETA|ESTOJO|SLOT)[_\s]?(\d{1,2})$', re.IGNORECASE)
            padrao_pegar = re.compile(r'^PEGA[R]?[_\s]?(?:CANETA|ESTOJO|SLOT)[_\s]?(\d{1,2})$', re.IGNORECASE)
            padrao_soltar_id = re.compile(r'^(?:SOLTA[R]?|GUARDA[R]?|DEVOLVER?)[_\s]?(?:CANETA|ESTOJO|SLOT)[_\s]?(\d{1,2})$', re.IGNORECASE)
            padrao_soltar = re.compile(r'^(?:SOLTA[R]?|GUARDA[R]?|DEVOLVER?)[_\s]?(?:CANETA|ESTOJO)?$', re.IGNORECASE)

            linhas_exp = []
            for linha in texto.splitlines():
                linha_sem_com = linha.split(";")[0].split("(")[0].strip()
                if not linha_sem_com:
                    continue

                m_trocar = padrao_trocar.match(linha_sem_com)
                if m_trocar:
                    nid = int(m_trocar.group(1))
                    if caneta_simulada != nid:
                        if caneta_simulada:
                            linhas_exp.append(gc.gerar_gcode_soltar_caneta(caneta_simulada))
                        linhas_exp.append(gc.gerar_gcode_pegar_caneta(nid))
                        caneta_simulada = nid
                    continue

                m_pegar = padrao_pegar.match(linha_sem_com)
                if m_pegar:
                    nid = int(m_pegar.group(1))
                    linhas_exp.append(gc.gerar_gcode_pegar_caneta(nid))
                    caneta_simulada = nid
                    continue

                m_soltar_id = padrao_soltar_id.match(linha_sem_com)
                if m_soltar_id:
                    nid = int(m_soltar_id.group(1))
                    linhas_exp.append(gc.gerar_gcode_soltar_caneta(nid))
                    if caneta_simulada == nid:
                        caneta_simulada = None
                    continue

                if padrao_soltar.match(linha_sem_com):
                    if caneta_simulada:
                        linhas_exp.append(gc.gerar_gcode_soltar_caneta(caneta_simulada))
                        caneta_simulada = None
                    continue

                linhas_exp.append(linha)
            texto = "\n".join(linhas_exp)

        return texto

    def carregar_gcode_preview(self, conteudo_gcode: str) -> None:
        """
        Interpreta o código G-code completo com suporte a comandos modais, arcos G2/G3,
        posicionamento absoluto/relativo e expansão de macros para renderizar no canvas 2D.

        Args:
            conteudo_gcode (str): Código G-code completo a ser renderizado.
        """
        self.linhas_preview_g0.clear()
        self.linhas_preview_g1.clear()

        if not conteudo_gcode or not conteudo_gcode.strip():
            self.update()
            return

        conteudo_expandido = self._expandir_gcode_preview(conteudo_gcode)

        pos_atual_x = 0.0
        pos_atual_y = 0.0
        modo_absoluto = True
        fator_unidade = 1.0  # 1.0 para mm (G21), 25.4 para polegadas (G20)
        modo_movimento = 0   # 0: G0 (rápido), 1: G1 (linear), 2: G2 (arco horário), 3: G3 (arco anti-horário)

        padrao_palavras = re.compile(r'([A-Za-z])\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)')

        for linha_bruta in conteudo_expandido.splitlines():
            # 1. Remover comentários inline e em parênteses
            linha = re.sub(r'\(.*?\)', '', linha_bruta)
            linha = linha.split(';')[0].strip().upper()
            if not linha:
                continue

            # 2. Remover número de linha N...
            linha = re.sub(r'^N\d+\s*', '', linha)
            if not linha:
                continue

            # 3. Extrair pares letra/valor
            pares = padrao_palavras.findall(linha)
            if not pares:
                continue

            palavras = {letra: float(valor) for letra, valor in pares}

            # 4. Avaliar comandos G modais e de modo
            for letra, valor in pares:
                if letra == 'G':
                    g_num = int(round(float(valor) * 10))  # G00->0, G01->10, G02->20, G03->30, G90->900, etc.
                    g_val = int(round(float(valor)))

                    if g_val == 0:
                        modo_movimento = 0
                    elif g_val == 1:
                        modo_movimento = 1
                    elif g_val == 2:
                        modo_movimento = 2
                    elif g_val == 3:
                        modo_movimento = 3
                    elif g_val == 90:
                        modo_absoluto = True
                    elif g_val == 91:
                        modo_absoluto = False
                    elif g_val == 20:
                        fator_unidade = 25.4
                    elif g_val == 21:
                        fator_unidade = 1.0
                    elif g_val == 28:
                        # Homing / retorno à origem
                        modo_movimento = 0
                        palavras['X'] = 0.0
                        palavras['Y'] = 0.0

            # 5. Processar coordenadas de movimento
            tem_x = 'X' in palavras
            tem_y = 'Y' in palavras
            tem_i = 'I' in palavras
            tem_j = 'J' in palavras
            tem_r = 'R' in palavras

            if not (tem_x or tem_y or tem_i or tem_j or tem_r):
                continue

            prox_x = pos_atual_x
            prox_y = pos_atual_y

            if tem_x:
                val_x = palavras['X'] * fator_unidade
                prox_x = val_x if modo_absoluto else (pos_atual_x + val_x)

            if tem_y:
                val_y = palavras['Y'] * fator_unidade
                prox_y = val_y if modo_absoluto else (pos_atual_y + val_y)

            # Coordenadas G-code passadas diretamente para mm_para_tela que já
            # mapeia X da máquina no eixo vertical e Y no eixo horizontal.
            p_ini = QPointF(pos_atual_x, pos_atual_y)
            p_fim = QPointF(prox_x, prox_y)

            # Evita linhas de comprimento zero
            dist_movimento = math.hypot(prox_x - pos_atual_x, prox_y - pos_atual_y)

            if modo_movimento == 0:
                if dist_movimento > 1e-4:
                    self.linhas_preview_g0.append((p_ini, p_fim))
            elif modo_movimento == 1:
                if dist_movimento > 1e-4:
                    self.linhas_preview_g1.append((p_ini, p_fim))
            elif modo_movimento in (2, 3):
                i_val = (palavras['I'] * fator_unidade) if tem_i else None
                j_val = (palavras['J'] * fator_unidade) if tem_j else None
                r_val = (palavras['R'] * fator_unidade) if tem_r else None
                sentido_cw = (modo_movimento == 2)  # G2 = horário, G3 = anti-horário

                segs_arco = interpolar_arco_gcode(
                    p_ini, p_fim, i_val, j_val, r_val, sentido_cw
                )
                for s_ini, s_fim in segs_arco:
                    self.linhas_preview_g1.append((s_ini, s_fim))

            pos_atual_x = prox_x
            pos_atual_y = prox_y

        self.update()


class Visualizador2DMaquina(QFrame):
    """
    Widget container para o Visualizador 2D com barra de ferramentas e controles.
    """

    def __init__(
        self,
        gerenciador_canetas: Optional[GerenciadorCanetas] = None,
        gerenciador_macros: Optional[Any] = None,
        gerenciador_area: Optional[Any] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #222240; border: 1px solid #2e2e4a; border-radius: 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Cabeçalho do Visualizador
        layout_topo = QHBoxLayout()
        layout_topo.setContentsMargins(4, 2, 4, 2)

        rotulo_titulo = QLabel("📐 Visualizador 2D da Plotter (Tempo Real)")
        rotulo_titulo.setStyleSheet("font-weight: 700; font-size: 12px; color: #e8e8f0; border: none;")

        self.botao_ajustar = QPushButton("🎯 Centralizar")
        self.botao_ajustar.setToolTip("Ajustar visualização para o centro da mesa")
        self.botao_ajustar.setFixedHeight(24)

        layout_topo.addWidget(rotulo_titulo)
        layout_topo.addStretch()
        layout_topo.addWidget(self.botao_ajustar)

        layout.addLayout(layout_topo)

        # Canvas 2D
        self.canvas = CanvasVisualizador2D(
            gerenciador_canetas=gerenciador_canetas,
            gerenciador_macros=gerenciador_macros,
            gerenciador_area=gerenciador_area,
            parent=self
        )
        layout.addWidget(self.canvas, 1)

        self.botao_ajustar.clicked.connect(self.canvas.ajustar_vista)

"""
Módulo do editor de G-code com números de linha e destaque
de linha ativa durante o envio para o GRBL.
"""

from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PySide6.QtCore import Qt, QRect, QSize, Slot
from PySide6.QtGui import (
    QColor, QPainter, QTextFormat, QTextCursor,
    QPaintEvent, QResizeEvent
)


class AreaNumerosLinha(QWidget):
    """
    Widget auxiliar que renderiza os números de linha
    na lateral esquerda do editor de G-code.
    """

    def __init__(self, editor: "EditorGcode") -> None:
        """
        Inicializa a área de números vinculada ao editor.

        Args:
            editor (EditorGcode): Instância do editor de G-code pai.
        """
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        """
        Retorna o tamanho sugerido baseado na largura
        necessária para exibir os números de linha.

        Returns:
            QSize: Tamanho sugerido do widget.
        """
        return QSize(self._editor.calcular_largura_area_numeros(), 0)

    def paintEvent(self, evento: QPaintEvent) -> None:
        """
        Delega a pintura dos números de linha para o editor.

        Args:
            evento (QPaintEvent): Evento de pintura do Qt.
        """
        self._editor.pintar_area_numeros(evento)


class EditorGcode(QPlainTextEdit):
    """
    Editor de texto especializado para G-code com números de linha,
    destaque da linha atual do cursor e destaque da linha sendo
    enviada para o GRBL durante a execução.
    """

    COR_FUNDO_NUMERO = QColor("#1a1a30")
    COR_TEXTO_NUMERO = QColor("#6a6a82")
    COR_LINHA_CURSOR = QColor("#252545")
    COR_LINHA_ENVIANDO = QColor("#1a3a2a")
    COR_NUMERO_ENVIANDO = QColor("#4ade80")

    def __init__(self, parent: QWidget = None) -> None:
        """
        Inicializa o editor de G-code com área de números de linha
        e configurações visuais.

        Args:
            parent (QWidget): Widget pai opcional.
        """
        super().__init__(parent)
        self._area_numeros = AreaNumerosLinha(self)
        self._indice_linha_enviando = -1

        self.blockCountChanged.connect(self._atualizar_largura_area_numeros)
        self.updateRequest.connect(self._atualizar_area_numeros)
        self.cursorPositionChanged.connect(self._destacar_linha_atual)

        self._atualizar_largura_area_numeros()
        self._destacar_linha_atual()

        # Estilo herdado do tema global (QPlainTextEdit) — nenhum override necessário
        self.setTabStopDistance(28)

    def calcular_largura_area_numeros(self) -> int:
        """
        Calcula a largura necessária para exibir todos os
        números de linha baseado na quantidade de linhas do documento.

        Returns:
            int: Largura em pixels para a área de números.
        """
        digitos = len(str(max(1, self.blockCount())))
        digitos = max(digitos, 3)
        largura = 10 + self.fontMetrics().horizontalAdvance("9") * digitos
        return largura

    def resizeEvent(self, evento: QResizeEvent) -> None:
        """
        Reposiciona a área de números ao redimensionar o editor.

        Args:
            evento (QResizeEvent): Evento de redimensionamento.
        """
        super().resizeEvent(evento)
        retangulo_conteudo = self.contentsRect()
        retangulo_numeros = QRect(
            retangulo_conteudo.left(),
            retangulo_conteudo.top(),
            self.calcular_largura_area_numeros(),
            retangulo_conteudo.height()
        )
        self._area_numeros.setGeometry(retangulo_numeros)

    def pintar_area_numeros(self, evento: QPaintEvent) -> None:
        """
        Renderiza os números de linha na área lateral.
        Destaca o número da linha sendo enviada em verde.

        Args:
            evento (QPaintEvent): Evento de pintura.
        """
        pintor = QPainter(self._area_numeros)
        pintor.fillRect(evento.rect(), self.COR_FUNDO_NUMERO)

        bloco = self.firstVisibleBlock()
        numero_bloco = bloco.blockNumber()
        topo = round(
            self.blockBoundingGeometry(bloco)
            .translated(self.contentOffset()).top()
        )
        base = topo + round(self.blockBoundingRect(bloco).height())

        while bloco.isValid() and topo <= evento.rect().bottom():
            if bloco.isVisible() and base >= evento.rect().top():
                numero_linha = str(numero_bloco + 1)

                if numero_bloco == self._indice_linha_enviando:
                    pintor.setPen(self.COR_NUMERO_ENVIANDO)
                else:
                    pintor.setPen(self.COR_TEXTO_NUMERO)

                pintor.drawText(
                    0, topo,
                    self._area_numeros.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    numero_linha
                )

            bloco = bloco.next()
            topo = base
            base = topo + round(self.blockBoundingRect(bloco).height())
            numero_bloco += 1

        pintor.end()

    @Slot(int)
    def definir_linha_enviando(self, indice_linha: int) -> None:
        """
        Define qual linha está sendo enviada ao GRBL e atualiza
        o destaque visual. Rola o editor para manter a linha visível.

        Args:
            indice_linha (int): Índice da linha (0-based). Use -1 para limpar.
        """
        if indice_linha == self._indice_linha_enviando:
            return

        self._indice_linha_enviando = indice_linha
        self._destacar_linha_atual()
        self._area_numeros.update()

        if indice_linha >= 0:
            cursor = QTextCursor(
                self.document().findBlockByNumber(indice_linha)
            )
            self.setTextCursor(cursor)
            self.centerCursor()

    def _atualizar_largura_area_numeros(self) -> None:
        """
        Atualiza a margem esquerda do editor para acomodar
        a área de números de linha.
        """
        self.setViewportMargins(
            self.calcular_largura_area_numeros(), 0, 0, 0
        )

    def _atualizar_area_numeros(self, retangulo: QRect, delta_y: int) -> None:
        """
        Atualiza a posição da área de números quando o editor
        é rolado verticalmente.

        Args:
            retangulo (QRect): Área a ser atualizada.
            delta_y (int): Deslocamento vertical em pixels.
        """
        if delta_y:
            self._area_numeros.scroll(0, delta_y)
        else:
            self._area_numeros.update(
                0, retangulo.y(),
                self._area_numeros.width(),
                retangulo.height()
            )
        if retangulo.contains(self.viewport().rect()):
            self._atualizar_largura_area_numeros()

    def _destacar_linha_atual(self) -> None:
        """
        Aplica destaque visual na linha do cursor e na linha
        sendo enviada ao GRBL (se houver).
        """
        selecoes_extras = []

        # Destaque da linha do cursor
        selecao_cursor = QTextEdit.ExtraSelection()
        selecao_cursor.format.setBackground(self.COR_LINHA_CURSOR)
        selecao_cursor.format.setProperty(
            QTextFormat.Property.FullWidthSelection, True
        )
        selecao_cursor.cursor = self.textCursor()
        selecao_cursor.cursor.clearSelection()
        selecoes_extras.append(selecao_cursor)

        # Destaque da linha sendo enviada
        if self._indice_linha_enviando >= 0:
            bloco = self.document().findBlockByNumber(
                self._indice_linha_enviando
            )
            if bloco.isValid():
                selecao_envio = QTextEdit.ExtraSelection()
                selecao_envio.format.setBackground(self.COR_LINHA_ENVIANDO)
                selecao_envio.format.setProperty(
                    QTextFormat.Property.FullWidthSelection, True
                )
                selecao_envio.cursor = QTextCursor(bloco)
                selecao_envio.cursor.clearSelection()
                selecoes_extras.append(selecao_envio)

        self.setExtraSelections(selecoes_extras)

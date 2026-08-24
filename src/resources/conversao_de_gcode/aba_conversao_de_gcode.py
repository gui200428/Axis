from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class AbaConversaoDeGcode(QWidget):
    """
    Widget da aba de Conversão de Gcode.

    Responsável pela interface visual que permite ao usuário
    gerar e manipular arquivos Gcode na aplicação AXIS.
    """

    def __init__(self) -> None:
        """
        Inicializa o widget da aba de Conversão de Gcode
        e configura o layout inicial.
        """
        super().__init__()
        self._configurar_layout()

    def _configurar_layout(self) -> None:
        """
        Configura o layout e os componentes visuais da aba.
        """
        layout_principal = QVBoxLayout()

        rotulo_titulo = QLabel("Conversão de Gcode")
        rotulo_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rotulo_descricao = QLabel(
            "Módulo responsável pela geração e manipulação de arquivos Gcode."
        )
        rotulo_descricao.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout_principal.addStretch()
        layout_principal.addWidget(rotulo_titulo)
        layout_principal.addWidget(rotulo_descricao)
        layout_principal.addStretch()

        self.setLayout(layout_principal)

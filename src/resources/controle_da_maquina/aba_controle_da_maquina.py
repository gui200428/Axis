from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class AbaControleDaMaquina(QWidget):
    """
    Widget da aba de Controle da Máquina.

    Responsável pela interface visual que permite ao usuário
    interagir com os controles da máquina AXIS.
    """

    def __init__(self) -> None:
        """
        Inicializa o widget da aba de Controle da Máquina
        e configura o layout inicial.
        """
        super().__init__()
        self._configurar_layout()

    def _configurar_layout(self) -> None:
        """
        Configura o layout e os componentes visuais da aba.
        """
        layout_principal = QVBoxLayout()

        rotulo_titulo = QLabel("Controle da Máquina")
        rotulo_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rotulo_descricao = QLabel(
            "Módulo responsável pelo controle dos motores e atuadores."
        )
        rotulo_descricao.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout_principal.addStretch()
        layout_principal.addWidget(rotulo_titulo)
        layout_principal.addWidget(rotulo_descricao)
        layout_principal.addStretch()

        self.setLayout(layout_principal)

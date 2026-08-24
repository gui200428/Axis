from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class AbaProcessamentoDeImagem(QWidget):
    """
    Widget da aba de Processamento de Imagem.

    Responsável pela interface visual que permite ao usuário
    carregar, visualizar e processar imagens na aplicação AXIS.
    """

    def __init__(self) -> None:
        """
        Inicializa o widget da aba de Processamento de Imagem
        e configura o layout inicial.
        """
        super().__init__()
        self._configurar_layout()

    def _configurar_layout(self) -> None:
        """
        Configura o layout e os componentes visuais da aba.
        """
        layout_principal = QVBoxLayout()

        rotulo_titulo = QLabel("Processamento de Imagem")
        rotulo_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rotulo_descricao = QLabel(
            "Módulo responsável pelo processamento e manipulação de imagens."
        )
        rotulo_descricao.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout_principal.addStretch()
        layout_principal.addWidget(rotulo_titulo)
        layout_principal.addWidget(rotulo_descricao)
        layout_principal.addStretch()

        self.setLayout(layout_principal)

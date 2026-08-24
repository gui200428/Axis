import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from resources import (
    AbaControleDaMaquina,
    AbaProcessamentoDeImagem,
    AbaConversaoDeSvg,
    AbaConversaoDeGcode,
)


def registrar_abas(widget_abas: QTabWidget, lista_de_abas: list) -> None:
    """
    Registra uma lista de abas no widget de abas da janela principal.

    Para adicionar uma nova aba, basta incluir uma nova tupla na lista_de_abas
    com o formato (nome_da_aba, instancia_do_widget).

    Args:
        widget_abas (QTabWidget): O widget de abas onde as abas serão inseridas.
        lista_de_abas (list): Lista de tuplas no formato (str, QWidget).
    """
    for nome_da_aba, widget_da_aba in lista_de_abas:
        widget_abas.addTab(widget_da_aba, nome_da_aba)


def iniciar_interface_grafica(
    width: int,
    height: int,
    title: str) -> None:
    """
    Inicializa e exibe a janela principal com o sistema de abas.

    Args:
        width (int): Comprimento da Janela em pixels.
        height (int): Altura da janela em pixels.
        title (str): Titulo da janela.
    """
    aplicativo = QApplication(sys.argv)
    janela_principal = QMainWindow()
    janela_principal.setWindowTitle(title)
    janela_principal.resize(width, height)

    widget_abas = QTabWidget()
    janela_principal.setCentralWidget(widget_abas)
    janela_principal.setMinimumSize(950, 600)

    lista_de_abas = [
        ("Controle da Máquina", AbaControleDaMaquina()),
        ("Processamento de Imagem", AbaProcessamentoDeImagem()),
        ("Conversão de SVG", AbaConversaoDeSvg()),
        ("Conversão de Gcode", AbaConversaoDeGcode()),
    ]

    registrar_abas(widget_abas, lista_de_abas)

    janela_principal.show()
    sys.exit(aplicativo.exec())


if __name__ == "__main__":
    titulo_janela = "Janela Principal Axis"
    iniciar_interface_grafica(width=1150, height=720, title=titulo_janela)


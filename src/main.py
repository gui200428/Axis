"""
Módulo principal do AXIS Plotter.

Inicializa a aplicação gráfica PySide6, aplica o tema escuro moderno,
instancia os controladores compartilhados e registra as abas de navegação.
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from resources import (
    AbaControleDaMaquina,
    AbaConfiguracoes,
    AbaProcessamentoDeImagem,
    AbaConversaoDeSvg,
    AbaConversaoDeGcode,
)
from resources.controle_da_maquina.logica_controle_da_maquina import ControladorGrbl
from resources.controle_da_maquina.gerenciador_canetas import GerenciadorCanetas
from resources.controle_da_maquina.gerenciador_area_desenho import GerenciadorAreaDesenho
from resources.controle_da_maquina.gerenciador_nivelamento import GerenciadorNivelamento
from resources.macros.logica_macros import GerenciadorMacros
from resources.estilo import ESTILO_GLOBAL


def registrar_abas(widget_abas: QTabWidget, lista_de_abas: list) -> None:
    """
    Registra uma lista de abas no widget de abas da janela principal.

    Args:
        widget_abas (QTabWidget): O widget de abas onde as abas serão inseridas.
        lista_de_abas (list): Lista de tuplas no formato (str, QWidget).
    """
    for nome_da_aba, widget_da_aba in lista_de_abas:
        widget_abas.addTab(widget_da_aba, nome_da_aba)


def iniciar_interface_grafica(
    largura: int,
    altura: int,
    titulo: str) -> None:
    """
    Inicializa e exibe a janela principal com o sistema de abas e controladores compartilhados.

    Args:
        largura (int): Comprimento da janela em pixels.
        altura (int): Altura da janela em pixels.
        titulo (str): Título da janela principal.
    """
    aplicativo = QApplication(sys.argv)
    aplicativo.setStyleSheet(ESTILO_GLOBAL)

    janela_principal = QMainWindow()
    janela_principal.setWindowTitle(titulo)
    janela_principal.resize(largura, altura)
    janela_principal.setMinimumSize(980, 640)

    widget_abas = QTabWidget()
    janela_principal.setCentralWidget(widget_abas)

    # Controladores Compartilhados (GRBL, Canetas, Macros, Área de Desenho e Nivelamento)
    controlador_grbl = ControladorGrbl()
    gerenciador_canetas = GerenciadorCanetas()
    gerenciador_macros = GerenciadorMacros()
    gerenciador_area = GerenciadorAreaDesenho()
    gerenciador_nivelamento = GerenciadorNivelamento(
        gerenciador_area=gerenciador_area,
        gerenciador_canetas=gerenciador_canetas
    )

    aba_controle = AbaControleDaMaquina(
        controlador_grbl=controlador_grbl,
        gerenciador_canetas=gerenciador_canetas,
        gerenciador_macros=gerenciador_macros,
        gerenciador_area=gerenciador_area,
        gerenciador_nivelamento=gerenciador_nivelamento
    )
    aba_configuracoes = AbaConfiguracoes(
        controlador_grbl=controlador_grbl,
        gerenciador_canetas=gerenciador_canetas,
        gerenciador_macros=gerenciador_macros,
        gerenciador_area=gerenciador_area,
        gerenciador_nivelamento=gerenciador_nivelamento
    )

    lista_de_abas = [
        ("🎛️ Controle da Máquina", aba_controle),
        ("🖼️ Processamento de Imagem", AbaProcessamentoDeImagem()),
        ("📐 Conversão de SVG", AbaConversaoDeSvg()),
        ("⚙️ Conversão de Gcode", AbaConversaoDeGcode()),
        ("⚙️ Configurações", aba_configuracoes),
    ]

    registrar_abas(widget_abas, lista_de_abas)

    janela_principal.show()
    sys.exit(aplicativo.exec())


if __name__ == "__main__":
    titulo_janela = "AXIS Plotter Control"
    iniciar_interface_grafica(largura=1200, altura=760, titulo=titulo_janela)

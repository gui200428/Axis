import sys
from PySide6.QtWidgets import QApplication, QMainWindow

def iniciar_interface_grafica(
    width: int, 
    height: int,
    title: str) -> None:
    """
    Inicializa e exibe a janela principal.
    
    Args:
        width - Comprimento da Janela em pixels
        height - Altura da janela em pixels
        title - Titulo da janela
    """
    aplicativo = QApplication(sys.argv)
    janela_principal = QMainWindow()
    janela_principal.setWindowTitle(title)
    janela_principal.resize(width, height)
    
    janela_principal.show()
    sys.exit(aplicativo.exec())

if __name__ == "__main__":
    titulo_janela = "Janela Principal Axis"
    iniciar_interface_grafica(width=800, height=500, title=titulo_janela)

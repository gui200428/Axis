from PySide6.QtCore import QObject, Signal, Slot

from resources.processamento_de_imagem.logica_processamento_de_imagem import ImageProcessor


class ImageWorker(QObject):
    """
    Worker executado em uma thread separada.

    Isso evita que o processamento congele a interface.
    """

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, imagem, parametros):
        super().__init__()

        self.imagem = imagem
        self.parametros = parametros

        self.processor = ImageProcessor()

    @Slot()
    def run(self):
        try:
            resultado = self.processor.processar(
                self.imagem,
                self.parametros
            )

            self.finished.emit(resultado)

        except Exception as exc:
            self.error.emit(str(exc))
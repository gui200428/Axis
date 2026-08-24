from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QFileDialog, QSlider, QProgressBar,
    QMessageBox, QScrollArea, QFrame, QComboBox, QSpinBox, QDoubleSpinBox
)
from PySide6.QtSvgWidgets import QSvgWidget
from PIL import Image

from resources.processamento_de_imagem.worker_processamento import ImageWorker

class ImagePreview(QScrollArea):
    """
    Área responsável por mostrar uma imagem raster (original).
    """
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumSize(300, 300)
        self.setWidget(self.label)
        self.imagem = None

    def mostrar_imagem(self, imagem: Image.Image):
        self.imagem = imagem
        if imagem.mode != "RGB":
            imagem = imagem.convert("RGB")
        largura, altura = imagem.size
        dados = imagem.tobytes("raw", "RGB")
        qimage = QImage(dados, largura, altura, largura * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage.copy())
        self.label.setPixmap(pixmap.scaled(self.viewport().size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def limpar(self):
        self.imagem = None
        self.label.clear()

class SvgPreview(QScrollArea):
    """
    Área responsável por mostrar o resultado SVG.
    """
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        # Widget para SVG
        self.svg_widget = QSvgWidget()
        self.svg_widget.setMinimumSize(300, 300)
        
        # Container para centralizar o SVG
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.svg_widget)
        self.setWidget(self.container)

    def mostrar_svg(self, svg_string: str):
        self.svg_widget.load(svg_string.encode('utf-8'))
        
    def limpar(self):
        self.svg_widget.load(b"")

class AbaProcessamentoDeImagem(QWidget):
    """
    Aba principal de processamento de imagens (Squiggle Vectorizer).
    """
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.imagem_original = None
        self.thread = None
        self.worker = None
        self._construir_interface()

    def _construir_interface(self):
        layout_principal = QHBoxLayout(self)
        layout_principal.setContentsMargins(10, 10, 10, 10)
        layout_principal.setSpacing(10)

        # Barra lateral de parâmetros
        sidebar = self._criar_sidebar()
        layout_principal.addWidget(sidebar, stretch=0)

        # Área de visualização (Original vs SVG)
        visualizacao = self._criar_visualizacao()
        layout_principal.addWidget(visualizacao, stretch=1)

    def _criar_sidebar(self):
        frame = QFrame()
        frame.setMinimumWidth(320)
        frame.setMaximumWidth(380)
        
        # O layout geral da sidebar (dentro de um ScrollArea para caber tudo)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        
        # 1. ARQUIVO
        grupo_arquivo = QGroupBox("Imagem")
        layout_arquivo = QVBoxLayout(grupo_arquivo)
        self.btn_carregar = QPushButton("Carregar imagem")
        self.btn_carregar.clicked.connect(self.carregar_imagem)
        layout_arquivo.addWidget(self.btn_carregar)
        self.lbl_arquivo = QLabel("Nenhuma imagem carregada")
        self.lbl_arquivo.setWordWrap(True)
        layout_arquivo.addWidget(self.lbl_arquivo)
        layout.addWidget(grupo_arquivo)

        # 2. PARÂMETROS
        grupo_parametros = QGroupBox("Parâmetros (Squiggle)")
        grid = QGridLayout(grupo_parametros)
        
        # Funções helpers para criar os controles
        linha = 0
        self.controles = {}
        
        def add_slider(nome, lbl_texto, min_val, max_val, default_val):
            nonlocal linha
            lbl = QLabel(lbl_texto)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(min_val)
            slider.setMaximum(max_val)
            slider.setValue(default_val)
            val_lbl = QLabel(str(default_val))
            slider.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
            grid.addWidget(lbl, linha, 0)
            grid.addWidget(slider, linha, 1)
            grid.addWidget(val_lbl, linha, 2)
            self.controles[nome] = slider
            linha += 1
            
        def add_combo(nome, lbl_texto, opcoes, default_idx):
            nonlocal linha
            lbl = QLabel(lbl_texto)
            combo = QComboBox()
            combo.addItems(opcoes)
            combo.setCurrentIndex(default_idx)
            grid.addWidget(lbl, linha, 0)
            grid.addWidget(combo, linha, 1, 1, 2)
            self.controles[nome] = combo
            linha += 1

        # Adicionando na ordem requisitada:
        # Densidade, Comprimento Min, Comprimento Max, Nº Testes, Apagamento Min, Apagamento Max, Tom(Tone Curve), Squiggle Min, Squiggle Max, Desvio Squiggle
        add_slider("densidade", "Densidade", 1, 500, 100)
        add_slider("comprimento_min", "Comprimento Min", 1, 100, 1)
        add_slider("comprimento_max", "Comprimento Max", 1, 100, 10)
        add_slider("n_testes", "Nº Testes", 1, 50, 1)
        add_slider("apagamento_min", "Apagamento Min", 0, 255, 0)
        add_slider("apagamento_max", "Apagamento Max", 0, 255, 255)
        add_combo("tom", "Tom (Tone Curve)", ["Linear", "Exponencial"], 0)
        add_slider("squiggle_min", "Squiggle Min", 0, 100, 0)
        add_slider("squiggle_max", "Squiggle Max", 0, 100, 10)
        add_slider("desvio_squiggle", "Desvio Squiggle", 0, 100, 0)

        layout.addWidget(grupo_parametros)
        
        # 3. SAÍDA (Output)
        grupo_saida = QGroupBox("Saída (Output)")
        grid_saida = QGridLayout(grupo_saida)
        linha = 0
        
        def add_spinbox(nome, lbl_texto, min_val, max_val, default_val):
            nonlocal linha
            lbl = QLabel(lbl_texto)
            spin = QSpinBox()
            spin.setMinimum(min_val)
            spin.setMaximum(max_val)
            spin.setValue(default_val)
            grid_saida.addWidget(lbl, linha, 0)
            grid_saida.addWidget(spin, linha, 1)
            self.controles[nome] = spin
            linha += 1
            
        def add_double_spinbox(nome, lbl_texto, min_val, max_val, default_val):
            nonlocal linha
            lbl = QLabel(lbl_texto)
            spin = QDoubleSpinBox()
            spin.setMinimum(min_val)
            spin.setMaximum(max_val)
            spin.setValue(default_val)
            spin.setSingleStep(0.1)
            grid_saida.addWidget(lbl, linha, 0)
            grid_saida.addWidget(spin, linha, 1)
            self.controles[nome] = spin
            linha += 1
            
        add_spinbox("resolucao_max", "Resolução Max", 1, 500, 10)
        add_double_spinbox("espessura_traco", "Espessura do Traço", 0.1, 10.0, 1.0)
        
        layout.addWidget(grupo_saida)

        # 4. BOTÕES E PROGRESSO
        self.btn_processar = QPushButton("Gerar SVG")
        self.btn_processar.setMinimumHeight(45)
        self.btn_processar.clicked.connect(self.processar_imagem)
        layout.addWidget(self.btn_processar)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("Pronto")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        layout.addStretch()
        scroll.setWidget(scroll_widget)
        
        main_sidebar_layout = QVBoxLayout(frame)
        main_sidebar_layout.setContentsMargins(0,0,0,0)
        main_sidebar_layout.addWidget(scroll)

        return frame

    def _criar_visualizacao(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        titulo = QLabel("Visualização Vetorial")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(titulo)

        imagens_layout = QHBoxLayout()

        # Original
        grupo_original = QGroupBox("Imagem Original")
        layout_original = QVBoxLayout(grupo_original)
        self.preview_original = ImagePreview()
        layout_original.addWidget(self.preview_original)

        # SVG Processado
        grupo_processada = QGroupBox("Preview SVG")
        layout_processada = QVBoxLayout(grupo_processada)
        self.preview_svg = SvgPreview()
        layout_processada.addWidget(self.preview_svg)

        imagens_layout.addWidget(grupo_original)
        imagens_layout.addWidget(grupo_processada)
        layout.addLayout(imagens_layout)

        self.lbl_info = QLabel("Nenhuma imagem carregada")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_info)

        return frame

    def carregar_imagem(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar imagem", "", "Imagens (*.png *.jpg *.jpeg)")
        if not caminho:
            return
        try:
            imagem = Image.open(caminho)
            imagem.load()
            self.imagem_original = imagem.copy()
            
            self.preview_original.mostrar_imagem(self.imagem_original)
            self.preview_svg.limpar()
            self.lbl_arquivo.setText(caminho)
            
            largura, altura = self.imagem_original.size
            self.lbl_info.setText(f"Resolução Original: {largura} × {altura} px")
            self.lbl_status.setText("Imagem carregada")
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar a imagem:\\n\\n{exc}")

    def obter_parametros(self):
        # Mapeamento dinâmico para pegar os valores
        params = {}
        for nome, widget in self.controles.items():
            if isinstance(widget, QComboBox):
                params[nome] = widget.currentIndex()
            else:
                params[nome] = widget.value()
        return params

    def processar_imagem(self):
        if self.imagem_original is None:
            QMessageBox.warning(self, "Nenhuma imagem", "Carregue uma imagem antes de processar.")
            return

        parametros = self.obter_parametros()
        
        self.btn_processar.setEnabled(False)
        self.btn_carregar.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_status.setText("Gerando SVG...")

        self.thread = QThread()
        self.worker = ImageWorker(self.imagem_original.copy(), parametros)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        
        self.worker.finished.connect(self.processamento_finalizado)
        self.worker.error.connect(self.processamento_erro)
        
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.limpar_thread)
        
        self.thread.start()

    def processamento_finalizado(self, svg_string: str):
        self.preview_svg.mostrar_svg(svg_string)
        self.lbl_status.setText("Conversão concluída!")
        self.btn_processar.setEnabled(True)
        self.btn_carregar.setEnabled(True)
        self.progress.setVisible(False)

    def processamento_erro(self, mensagem):
        self.lbl_status.setText("Erro na conversão")
        self.btn_processar.setEnabled(True)
        self.btn_carregar.setEnabled(True)
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Erro na conversão", mensagem)

    def limpar_thread(self):
        self.worker = None
        self.thread = None
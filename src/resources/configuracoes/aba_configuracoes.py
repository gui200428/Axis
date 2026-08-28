"""
Módulo de interface gráfica para a aba de Configurações da plotter AXIS.

Contém os painéis de configuração detalhada de troca de canetas (com editor de G-code livre),
biblioteca de macros personalizadas e parâmetros do firmware GRBL.
"""

from typing import Optional, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QGroupBox, QDoubleSpinBox, QSpinBox, QScrollArea,
    QSplitter, QFrame, QMessageBox, QListWidget, QListWidgetItem,
    QTabWidget, QComboBox, QColorDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication

from resources.controle_da_maquina.logica_controle_da_maquina import ControladorGrbl
from resources.controle_da_maquina.gerenciador_canetas import (
    GerenciadorCanetas, SlotCaneta,
    gerar_template_pegar_padrao, gerar_template_soltar_padrao
)
from resources.controle_da_maquina.gerenciador_area_desenho import GerenciadorAreaDesenho
from resources.controle_da_maquina.gerenciador_nivelamento import GerenciadorNivelamento
from resources.configuracoes.painel_calibracao_zoffset import PainelCalibracaoZOffset
from resources.macros.logica_macros import GerenciadorMacros, MacroGcode
from resources.configuracoes.dicionario_grbl import DICIONARIO_PARAMETROS_GRBL, obter_info_parametro
from resources.estilo.tema_escuro import ESTILO_CARD_PADRAO


class PainelConfiguracaoCanetas(QWidget):
    """
    Painel de configuração e edição detalhada de G-code para as 10 canetas.
    """

    def __init__(
        self,
        gerenciador_canetas: GerenciadorCanetas,
        controlador_grbl: ControladorGrbl,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.gerenciador_canetas = gerenciador_canetas
        self.controlador_grbl = controlador_grbl
        self._slot_selecionado_id: int = 1

        self._configurar_ui()
        self._carregar_slot_selecionado(1)

    def _configurar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: Lista das 10 canetas
        widget_lista = QFrame()
        widget_lista.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_lista = QVBoxLayout(widget_lista)
        layout_lista.setContentsMargins(8, 10, 8, 8)
        layout_lista.setSpacing(6)

        rotulo_lista = QLabel("Selecione a Caneta (1..10):")
        rotulo_lista.setStyleSheet("font-weight: 700; color: #e8e8f0; font-size: 11px;")
        layout_lista.addWidget(rotulo_lista)

        self.lista_canetas = QListWidget()
        self.lista_canetas.itemClicked.connect(self._ao_clicar_item_lista)
        layout_lista.addWidget(self.lista_canetas, 1)

        self._preencher_lista_canetas()

        splitter.addWidget(widget_lista)

        # Painel Direito: Editor Detalhado da Caneta Selecionada
        widget_detalhes = QFrame()
        widget_detalhes.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_detalhes = QVBoxLayout(widget_detalhes)
        layout_detalhes.setContentsMargins(10, 10, 10, 10)
        layout_detalhes.setSpacing(8)

        # Cabeçalho da Caneta (Nome, Cor, Status e Macro G-code)
        layout_cabecalho = QHBoxLayout()
        layout_cabecalho.setSpacing(8)

        self.rotulo_pill_cor = QLabel("  1  ")
        self.rotulo_pill_cor.setFixedSize(36, 26)
        self.rotulo_pill_cor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_pill_cor.setStyleSheet("font-weight: 800; border-radius: 4px; color: white;")

        self.botao_escolher_cor = QPushButton("🎨 Alterar Cor...")
        self.botao_escolher_cor.clicked.connect(self._abrir_seletor_cor)

        self.input_nome = QLineEdit()
        self.input_nome.setPlaceholderText("Nome da Cor / Caneta")
        self.input_nome.setStyleSheet("font-weight: 600; font-size: 12px;")

        self.badge_macro_cmd = QLabel("TROCA_CANETA_01")
        self.badge_macro_cmd.setToolTip("Comando de macro automático que deve ser digitado no G-code para acionar a troca deste slot")
        self.badge_macro_cmd.setStyleSheet(
            "QLabel {"
            "  background-color: #1a1a35;"
            "  color: #7da4ff;"
            "  font-family: 'Consolas', 'Ubuntu Mono', monospace;"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "  border: 1px solid #3a3a65;"
            "  border-radius: 4px;"
            "  padding: 3px 8px;"
            "}"
        )

        rotulo_macro_tag = QLabel("Macro:")
        rotulo_macro_tag.setStyleSheet("color: #9090a8; font-size: 11px; font-weight: 600;")

        layout_cabecalho.addWidget(self.rotulo_pill_cor)
        layout_cabecalho.addWidget(self.botao_escolher_cor)
        layout_cabecalho.addWidget(self.input_nome, 1)
        layout_cabecalho.addWidget(rotulo_macro_tag)
        layout_cabecalho.addWidget(self.badge_macro_cmd)

        layout_detalhes.addLayout(layout_cabecalho)

        # Coordenadas Base (X, Y, Z, Z Seguro, Feed)
        grupo_coords = QGroupBox("Parâmetros Físicos da Baia")
        grupo_coords.setStyleSheet(ESTILO_CARD_PADRAO)
        grid_coords = QGridLayout(grupo_coords)
        grid_coords.setSpacing(6)

        grid_coords.addWidget(QLabel("X Baia:"), 0, 0)
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(-500.0, 1000.0)
        self.spin_x.setDecimals(2)
        grid_coords.addWidget(self.spin_x, 0, 1)

        grid_coords.addWidget(QLabel("Y Baia:"), 0, 2)
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(-500.0, 1000.0)
        self.spin_y.setDecimals(2)
        grid_coords.addWidget(self.spin_y, 0, 3)

        grid_coords.addWidget(QLabel("Z Pegar Baia:"), 1, 0)
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(-100.0, 100.0)
        self.spin_z.setDecimals(2)
        grid_coords.addWidget(self.spin_z, 1, 1)

        grid_coords.addWidget(QLabel("Z-Up (Seguro):"), 1, 2)
        self.spin_z_seguro = QDoubleSpinBox()
        self.spin_z_seguro.setRange(-100.0, 100.0)
        self.spin_z_seguro.setDecimals(2)
        grid_coords.addWidget(self.spin_z_seguro, 1, 3)

        grid_coords.addWidget(QLabel("Z-Down (Desenho):"), 2, 0)
        self.spin_z_down = QDoubleSpinBox()
        self.spin_z_down.setRange(-100.0, 100.0)
        self.spin_z_down.setDecimals(2)
        grid_coords.addWidget(self.spin_z_down, 2, 1)

        # Conectar sinais de alteração dos spinboxes e nome para auto-atualização do G-code
        self.spin_x.valueChanged.connect(self._ao_alterar_parametros_baia)
        self.spin_y.valueChanged.connect(self._ao_alterar_parametros_baia)
        self.spin_z.valueChanged.connect(self._ao_alterar_parametros_baia)
        self.spin_z_seguro.valueChanged.connect(self._ao_alterar_parametros_baia)
        self.spin_z_down.valueChanged.connect(self._ao_alterar_parametros_baia)
        self.input_nome.textChanged.connect(self._ao_alterar_parametros_baia)

        layout_detalhes.addWidget(grupo_coords)

        # Editor Completo de G-code de Troca
        abas_gcode = QTabWidget()

        # Aba Script Pegar
        widget_pegar = QWidget()
        layout_pegar = QVBoxLayout(widget_pegar)
        layout_pegar.setContentsMargins(4, 4, 4, 4)
        self.editor_gcode_pegar = QTextEdit()
        layout_pegar.addWidget(self.editor_gcode_pegar)
        abas_gcode.addTab(widget_pegar, "📥 Script G-code: Pegar Caneta")

        # Aba Script Soltar
        widget_soltar = QWidget()
        layout_soltar = QVBoxLayout(widget_soltar)
        layout_soltar.setContentsMargins(4, 4, 4, 4)
        self.editor_gcode_soltar = QTextEdit()
        layout_soltar.addWidget(self.editor_gcode_soltar)
        abas_gcode.addTab(widget_soltar, "📤 Script G-code: Devolver Caneta")

        layout_detalhes.addWidget(abas_gcode, 1)

        # Barra de Ações do Editor de Canetas
        layout_acoes = QHBoxLayout()
        layout_acoes.setSpacing(6)

        self.botao_salvar_slot = QPushButton("💾 Salvar Configurações da Caneta")
        self.botao_salvar_slot.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; padding: 6px 14px; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
        )
        self.botao_salvar_slot.clicked.connect(self._salvar_slot_atual)

        self.botao_restaurar_template = QPushButton("🔄 Restaurar G-code Padrão")
        self.botao_restaurar_template.clicked.connect(self._restaurar_template_slot)

        self.botao_testar_pegar_maquina = QPushButton("▶ Testar Pegar")
        self.botao_testar_pegar_maquina.clicked.connect(self._testar_pegar_maquina)

        self.botao_testar_soltar_maquina = QPushButton("▶ Testar Soltar")
        self.botao_testar_soltar_maquina.clicked.connect(self._testar_soltar_maquina)

        layout_acoes.addWidget(self.botao_salvar_slot, 1)
        layout_acoes.addWidget(self.botao_restaurar_template)
        layout_acoes.addWidget(self.botao_testar_pegar_maquina)
        layout_acoes.addWidget(self.botao_testar_soltar_maquina)

        layout_detalhes.addLayout(layout_acoes)

        splitter.addWidget(widget_detalhes)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _preencher_lista_canetas(self) -> None:
        self.lista_canetas.clear()
        item_para_selecionar = None
        for slot in self.gerenciador_canetas.obter_todos_slots():
            item = QListWidgetItem(f"[{slot.id:02d}] {slot.nome}  ➔ TROCA_CANETA_{slot.id:02d}")
            item.setData(Qt.ItemDataRole.UserRole, slot.id)
            self.lista_canetas.addItem(item)
            if slot.id == self._slot_selecionado_id:
                item_para_selecionar = item
        if item_para_selecionar:
            self.lista_canetas.setCurrentItem(item_para_selecionar)

    def _ao_clicar_item_lista(self, item: QListWidgetItem) -> None:
        id_slot = item.data(Qt.ItemDataRole.UserRole)
        self._carregar_slot_selecionado(id_slot)

    def _carregar_slot_selecionado(self, id_slot: int) -> None:
        self._bloqueando_sinais = True
        try:
            self._slot_selecionado_id = id_slot
            slot = self.gerenciador_canetas.obter_slot(id_slot)
            if not slot:
                return

            self.rotulo_pill_cor.setText(f"  {slot.id}  ")
            self.rotulo_pill_cor.setStyleSheet(
                f"background-color: {slot.cor_hex}; color: white; font-weight: 800; border-radius: 4px;"
            )
            self.input_nome.setText(slot.nome)
            self.badge_macro_cmd.setText(f"TROCA_CANETA_{slot.id:02d}")
            self.spin_x.setValue(slot.x_pegar)
            self.spin_y.setValue(slot.y_pegar)
            self.spin_z.setValue(slot.z_pegar)
            self.spin_z_seguro.setValue(getattr(slot, "z_up", slot.z_seguro))
            self.spin_z_down.setValue(getattr(slot, "z_down", 0.0))

            self.editor_gcode_pegar.setPlainText(slot.macro_pegar)
            self.editor_gcode_soltar.setPlainText(slot.macro_soltar)
        finally:
            self._bloqueando_sinais = False

    def _abrir_seletor_cor(self) -> None:
        slot = self.gerenciador_canetas.obter_slot(self._slot_selecionado_id)
        if not slot:
            return

        cor_inicial = QColor(slot.cor_hex)
        nova_cor = QColorDialog.getColor(cor_inicial, self, "Selecionar Cor da Caneta")
        if nova_cor.isValid():
            slot.cor_hex = nova_cor.name()
            self.rotulo_pill_cor.setStyleSheet(
                f"background-color: {slot.cor_hex}; color: white; font-weight: 800; border-radius: 4px;"
            )
            self.gerenciador_canetas.atualizar_slot(slot)
            self._preencher_lista_canetas()

    def _salvar_slot_atual(self) -> None:
        slot = self.gerenciador_canetas.obter_slot(self._slot_selecionado_id)
        if not slot:
            return

        slot.nome = self.input_nome.text().strip() or f"Caneta {slot.id}"
        slot.x_pegar = self.spin_x.value()
        slot.y_pegar = self.spin_y.value()
        slot.z_pegar = self.spin_z.value()
        slot.x_soltar = self.spin_x.value()
        slot.y_soltar = self.spin_y.value()
        slot.z_soltar = self.spin_z.value()
        slot.z_seguro = self.spin_z_seguro.value()
        slot.z_up = self.spin_z_seguro.value()
        slot.z_down = self.spin_z_down.value()
        slot.macro_pegar = self.editor_gcode_pegar.toPlainText().strip()
        slot.macro_soltar = self.editor_gcode_soltar.toPlainText().strip()

        self.gerenciador_canetas.atualizar_slot(slot)
        self._preencher_lista_canetas()
        QMessageBox.information(self, "Sucesso", f"Configurações da Caneta {slot.id} salvas com sucesso!")

    def _restaurar_template_slot(self) -> None:
        confirmacao = QMessageBox.question(
            self, "Restaurar Template",
            "Deseja restaurar os templates padrões de G-code para esta caneta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirmacao == QMessageBox.StandardButton.Yes:
            self.gerenciador_canetas.restaurar_macros_padrao_slot(self._slot_selecionado_id)
            self._carregar_slot_selecionado(self._slot_selecionado_id)

    def _ao_alterar_parametros_baia(self) -> None:
        """
        Regenera automaticamente os templates G-code de pegar/soltar caneta
        quando os parâmetros físicos da baia (X, Y, Z, Z Seguro) ou nome são alterados.
        """
        if getattr(self, "_bloqueando_sinais", False):
            return

        slot = self.gerenciador_canetas.obter_slot(self._slot_selecionado_id)
        if not slot:
            return

        # Novos valores dos spinboxes
        novo_x = self.spin_x.value()
        novo_y = self.spin_y.value()
        novo_z = self.spin_z.value()
        novo_z_seguro = self.spin_z_seguro.value()
        nome = self.input_nome.text().strip() or slot.nome

        # Template novo (gerado com os valores atuais dos spinboxes)
        template_pegar_novo = gerar_template_pegar_padrao(
            slot.id, nome, novo_x, novo_y, novo_z, novo_z_seguro, slot.velocidade
        )
        template_soltar_novo = gerar_template_soltar_padrao(
            slot.id, nome, novo_x, novo_y, novo_z, novo_z_seguro, slot.velocidade
        )

        self.editor_gcode_pegar.setPlainText(template_pegar_novo)
        self.editor_gcode_soltar.setPlainText(template_soltar_novo)

    def _testar_pegar_maquina(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de testar.")
            return

        gcode = self.editor_gcode_pegar.toPlainText().strip()
        slot_id = self._slot_selecionado_id
        self.controlador_grbl.enviar_script_gcode(
            gcode,
            nome=f"Pegar Caneta (Slot {slot_id:02d})",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(slot_id)
        )

    def _testar_soltar_maquina(self) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de testar.")
            return

        slot = self.gerenciador_canetas.obter_slot(self._slot_selecionado_id)
        z_seguro = slot.z_seguro if slot else 15.0
        velocidade = slot.velocidade if slot else 3000

        gcode = self.editor_gcode_soltar.toPlainText().strip()
        if not self.controlador_grbl.caneta_esta_alta(z_seguro):
            gcode = f"G90\nG21\nG0 Z{z_seguro:.2f} F{velocidade}\n" + gcode

        slot_id = self._slot_selecionado_id

        def _apos_soltar() -> None:
            if self.gerenciador_canetas.obter_caneta_ativa_id() == slot_id:
                self.gerenciador_canetas.definir_caneta_ativa(None)

        self.controlador_grbl.enviar_script_gcode(
            gcode,
            nome=f"Soltar Caneta (Slot {slot_id:02d})",
            callback_conclusao=_apos_soltar
        )


class PainelParametrosGrbl(QWidget):
    """
    Painel completo para visualização, monitoramento, busca e alteração
    de todos os parâmetros do firmware GRBL ($$).
    """

    def __init__(
        self,
        controlador_grbl: ControladorGrbl,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controlador_grbl = controlador_grbl
        self._parametros_atuais: Dict[str, str] = {}

        self._configurar_ui()
        self._conectar_sinais()
        self._inicializar_tabela_padrao()

    def _configurar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. Cards de Resumo no Topo
        layout_kpis = QHBoxLayout()
        layout_kpis.setSpacing(8)

        # Card 1: Dimensões de Mesa / Curso Útil
        card_limites = QFrame()
        card_limites.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_c1 = QVBoxLayout(card_limites)
        layout_c1.setContentsMargins(10, 8, 10, 8)
        layout_c1.setSpacing(4)
        rotulo_c1_tit = QLabel("📐 Área Útil ($130-$132)")
        rotulo_c1_tit.setStyleSheet("font-weight: 700; color: #7da4ff; font-size: 11px;")
        self.lbl_kpi_limites = QLabel("X: 300 mm  |  Y: 200 mm  |  Z: 50 mm")
        self.lbl_kpi_limites.setStyleSheet("font-weight: 600; font-size: 12px; color: #e8e8f0;")
        layout_c1.addWidget(rotulo_c1_tit)
        layout_c1.addWidget(self.lbl_kpi_limites)
        layout_kpis.addWidget(card_limites, 1)

        # Card 2: Resolução dos Eixos
        card_passos = QFrame()
        card_passos.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_c2 = QVBoxLayout(card_passos)
        layout_c2.setContentsMargins(10, 8, 10, 8)
        layout_c2.setSpacing(4)
        rotulo_c2_tit = QLabel("⚡ Resolução ($100-$102)")
        rotulo_c2_tit.setStyleSheet("font-weight: 700; color: #4ade80; font-size: 11px;")
        self.lbl_kpi_passos = QLabel("X: 250.0  |  Y: 250.0  |  Z: 250.0 steps/mm")
        self.lbl_kpi_passos.setStyleSheet("font-weight: 600; font-size: 12px; color: #e8e8f0;")
        layout_c2.addWidget(rotulo_c2_tit)
        layout_c2.addWidget(self.lbl_kpi_passos)
        layout_kpis.addWidget(card_passos, 1)

        # Card 3: Velocidade & Aceleração
        card_dinamica = QFrame()
        card_dinamica.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_c3 = QVBoxLayout(card_dinamica)
        layout_c3.setContentsMargins(10, 8, 10, 8)
        layout_c3.setSpacing(4)
        rotulo_c3_tit = QLabel("🚀 Dinâmica ($110-$122)")
        rotulo_c3_tit.setStyleSheet("font-weight: 700; color: #fbbf24; font-size: 11px;")
        self.lbl_kpi_dinamica = QLabel("Vel: 500 mm/min  |  Acel: 10 mm/s²")
        self.lbl_kpi_dinamica.setStyleSheet("font-weight: 600; font-size: 12px; color: #e8e8f0;")
        layout_c3.addWidget(rotulo_c3_tit)
        layout_c3.addWidget(self.lbl_kpi_dinamica)
        layout_kpis.addWidget(card_dinamica, 1)

        # Card 4: Recursos & Proteções
        card_recursos = QFrame()
        card_recursos.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_c4 = QVBoxLayout(card_recursos)
        layout_c4.setContentsMargins(10, 8, 10, 8)
        layout_c4.setSpacing(4)
        rotulo_c4_tit = QLabel("🛡️ Homing & Laser")
        rotulo_c4_tit.setStyleSheet("font-weight: 700; color: #a78bfa; font-size: 11px;")
        self.lbl_kpi_recursos = QLabel("Homing: Inativo  |  Laser: Inativo")
        self.lbl_kpi_recursos.setStyleSheet("font-weight: 600; font-size: 12px; color: #e8e8f0;")
        layout_c4.addWidget(rotulo_c4_tit)
        layout_c4.addWidget(self.lbl_kpi_recursos)
        layout_kpis.addWidget(card_recursos, 1)

        layout.addLayout(layout_kpis)

        # 2. Barra de Ações e Filtro de Pesquisa
        layout_barra = QHBoxLayout()
        layout_barra.setSpacing(8)

        self.botao_ler_config = QPushButton("⟳ Ler Configurações da Máquina ($$)")
        self.botao_ler_config.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; padding: 6px 14px; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
        )
        self.botao_ler_config.clicked.connect(self._solicitar_leitura_grbl)

        self.input_busca = QLineEdit()
        self.input_busca.setPlaceholderText("🔍 Filtrar parâmetros (ex: 130, passo, velocidade, aceleração, laser, homing)...")
        self.input_busca.textChanged.connect(self._filtrar_tabela)

        self.botao_copiar = QPushButton("📋 Copiar ($$)")
        self.botao_copiar.setToolTip("Copia todos os parâmetros lidos no formato de texto para a área de transferência")
        self.botao_copiar.clicked.connect(self._copiar_parametros_clipboard)

        self.badge_status = QLabel("Aguardando leitura ($$)")
        self.badge_status.setStyleSheet(
            "background-color: #1a1a35; color: #9090a8; border: 1px solid #33334d; "
            "border-radius: 4px; padding: 4px 8px; font-size: 11px;"
        )

        layout_barra.addWidget(self.botao_ler_config)
        layout_barra.addWidget(self.input_busca, 1)
        layout_barra.addWidget(self.botao_copiar)
        layout_barra.addWidget(self.badge_status)

        layout.addLayout(layout_barra)

        # 3. Tabela Principal de Parâmetros
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(6)
        self.tabela.setHorizontalHeaderLabels([
            "Parâmetro", "Valor", "Unidade", "Categoria", "Descrição & Função", "Ação"
        ])
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setStyleSheet(
            "QTableWidget { background-color: #1e1e35; alternate-background-color: #23233c; border: 1px solid #2e2e4a; }"
            "QHeaderView::section { background-color: #252540; color: #c0c0d0; font-weight: 700; border: 1px solid #33334d; padding: 6px; font-size: 11px; }"
            "QTableWidget::item { padding: 4px 8px; border: none; }"
            "QTableWidget::item:focus { border: 1px solid #5b7fff; }"
        )

        layout.addWidget(self.tabela, 1)

    def _conectar_sinais(self) -> None:
        self.controlador_grbl.sinal_parametros_grbl_recebidos.connect(self._ao_receber_parametros_grbl)
        self.controlador_grbl.sinal_configuracao_recebida.connect(self._ao_receber_limites)
        self.controlador_grbl.sinal_conexao_alterada.connect(self._ao_alterar_conexao)

    def _inicializar_tabela_padrao(self) -> None:
        valores_iniciais = {}
        for chave in DICIONARIO_PARAMETROS_GRBL:
            valores_iniciais[chave] = "-"
        params_existentes = self.controlador_grbl.obter_parametros_grbl()
        if params_existentes:
            valores_iniciais.update(params_existentes)
            self._parametros_atuais.update(params_existentes)
            self._atualizar_kpis(params_existentes)
        self._preencher_tabela(valores_iniciais)

    def _ao_receber_parametros_grbl(self, parametros: dict) -> None:
        self._parametros_atuais.update(parametros)
        self._preencher_tabela(self._parametros_atuais)
        self._atualizar_kpis(self._parametros_atuais)
        self.badge_status.setText(f"✓ {len(self._parametros_atuais)} parâmetros lidos")
        self.badge_status.setStyleSheet(
            "background-color: #163820; color: #4ade80; border: 1px solid #22c55e; "
            "border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 600;"
        )

    def _ao_receber_limites(self, x: float, y: float, z: float) -> None:
        self.lbl_kpi_limites.setText(f"X: {x:.1f} mm  |  Y: {y:.1f} mm  |  Z: {z:.1f} mm")

    def _ao_alterar_conexao(self, conectado: bool) -> None:
        if conectado:
            self.badge_status.setText("Conectado (lendo $$...)")
            self.badge_status.setStyleSheet(
                "background-color: #1a2a40; color: #7da4ff; border: 1px solid #3d5bc7; "
                "border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 600;"
            )
        else:
            self.badge_status.setText("Desconectado")
            self.badge_status.setStyleSheet(
                "background-color: #1a1a35; color: #9090a8; border: 1px solid #33334d; "
                "border-radius: 4px; padding: 4px 8px; font-size: 11px;"
            )

    def _solicitar_leitura_grbl(self) -> None:
        if self.controlador_grbl.esta_conectado():
            self.badge_status.setText("⟳ Solicitando $$...")
            self.badge_status.setStyleSheet(
                "background-color: #2a2a10; color: #fbbf24; border: 1px solid #e0a820; "
                "border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 600;"
            )
            self.controlador_grbl.obter_configuracao_area_trabalho()
        else:
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de ler as configurações.")

    def _preencher_tabela(self, parametros: dict) -> None:
        self.tabela.setRowCount(0)
        self.tabela.setSortingEnabled(False)

        def _ordem_chave(k: str) -> int:
            try:
                return int(k.replace("$", ""))
            except ValueError:
                return 9999

        chaves_ordenadas = sorted(parametros.keys(), key=_ordem_chave)
        self.tabela.setRowCount(len(chaves_ordenadas))

        for row, chave in enumerate(chaves_ordenadas):
            valor = str(parametros[chave])
            info = obter_info_parametro(chave)

            # Coluna 0: Parâmetro ($N)
            item_param = QTableWidgetItem(chave)
            item_param.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_param.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_param.setForeground(QColor("#7da4ff"))
            font_param = item_param.font()
            font_param.setBold(True)
            item_param.setFont(font_param)
            self.tabela.setItem(row, 0, item_param)

            # Coluna 1: Valor
            item_valor = QTableWidgetItem(valor)
            item_valor.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            item_valor.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_valor.setForeground(QColor("#ffffff"))
            font_val = item_valor.font()
            font_val.setBold(True)
            item_valor.setFont(font_val)
            self.tabela.setItem(row, 1, item_valor)

            # Coluna 2: Unidade
            item_unidade = QTableWidgetItem(info["unidade"])
            item_unidade.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_unidade.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_unidade.setForeground(QColor("#9090a8"))
            self.tabela.setItem(row, 2, item_unidade)

            # Coluna 3: Categoria
            item_cat = QTableWidgetItem(info["categoria"])
            item_cat.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_cat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cat.setForeground(QColor("#a78bfa"))
            self.tabela.setItem(row, 3, item_cat)

            # Coluna 4: Descrição & Função
            item_desc = QTableWidgetItem(f"{info['nome']} — {info['descricao']}")
            item_desc.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_desc.setForeground(QColor("#c0c0d0"))
            self.tabela.setItem(row, 4, item_desc)

            # Coluna 5: Ação (Botão Gravar)
            widget_acao = QWidget()
            layout_btn = QHBoxLayout(widget_acao)
            layout_btn.setContentsMargins(2, 2, 2, 2)
            btn_gravar = QPushButton("Gravar")
            btn_gravar.setStyleSheet(
                "QPushButton { background-color: #2c2c48; color: #4ade80; font-size: 11px; font-weight: 700; padding: 2px 8px; border: 1px solid #365c40; }"
                "QPushButton:hover { background-color: #1f4028; color: #ffffff; }"
            )
            btn_gravar.clicked.connect(lambda _, r=row, k=chave: self._gravar_linha(r, k))
            layout_btn.addWidget(btn_gravar)
            self.tabela.setCellWidget(row, 5, widget_acao)

        self._filtrar_tabela(self.input_busca.text())

    def _gravar_linha(self, row: int, chave: str) -> None:
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de gravar parâmetros no firmware.")
            return

        item_valor = self.tabela.item(row, 1)
        if not item_valor:
            return

        valor = item_valor.text().strip()
        if not valor or valor == "-":
            QMessageBox.warning(self, "Aviso", f"Insira um valor válido para {chave}.")
            return

        sucesso = self.controlador_grbl.gravar_parametro_grbl(chave, valor)
        if sucesso:
            self._parametros_atuais[chave] = valor
            self._atualizar_kpis(self._parametros_atuais)
            QMessageBox.information(self, "Sucesso", f"Comando '{chave}={valor}' enviado ao GRBL!")

    def _atualizar_kpis(self, params: dict) -> None:
        # 1. Limites
        lx = params.get("$130", "300")
        ly = params.get("$131", "200")
        lz = params.get("$132", "50")
        self.lbl_kpi_limites.setText(f"X: {lx} mm  |  Y: {ly} mm  |  Z: {lz} mm")

        # 2. Resolução
        sx = params.get("$100", "250")
        sy = params.get("$101", "250")
        sz = params.get("$102", "250")
        self.lbl_kpi_passos.setText(f"X: {sx}  |  Y: {sy}  |  Z: {sz} steps/mm")

        # 3. Dinâmica
        vx = params.get("$110", "500")
        ax = params.get("$120", "10")
        self.lbl_kpi_dinamica.setText(f"Vel: {vx} mm/min  |  Acel: {ax} mm/s²")

        # 4. Homing & Laser
        h_ativo = params.get("$22", "0") == "1"
        l_ativo = params.get("$32", "0") == "1"
        h_txt = "Ativo ($22=1)" if h_ativo else "Inativo ($22=0)"
        l_txt = "Ativo ($32=1)" if l_ativo else "Inativo ($32=0)"
        self.lbl_kpi_recursos.setText(f"Homing: {h_txt}  |  Laser: {l_txt}")

    def _copiar_parametros_clipboard(self) -> None:
        if not self._parametros_atuais:
            QMessageBox.information(self, "Aviso", "Nenhum parâmetro foi lido da máquina ainda.")
            return

        def _ordem_chave(k: str) -> int:
            try:
                return int(k.replace("$", ""))
            except ValueError:
                return 9999

        linhas = []
        for chave in sorted(self._parametros_atuais.keys(), key=_ordem_chave):
            valor = self._parametros_atuais[chave]
            info = obter_info_parametro(chave)
            linhas.append(f"{chave}={valor} ({info['nome']})")

        texto_completo = "\n".join(linhas)
        QGuiApplication.clipboard().setText(texto_completo)
        QMessageBox.information(self, "Copiado", f"{len(linhas)} parâmetros copiados para a área de transferência!")

    def _filtrar_tabela(self, texto: str) -> None:
        termo = texto.strip().lower()
        for row in range(self.tabela.rowCount()):
            if not termo:
                self.tabela.setRowHidden(row, False)
                continue

            item_p = self.tabela.item(row, 0)
            item_v = self.tabela.item(row, 1)
            item_c = self.tabela.item(row, 3)
            item_d = self.tabela.item(row, 4)

            conteudo = " ".join([
                item_p.text() if item_p else "",
                item_v.text() if item_v else "",
                item_c.text() if item_c else "",
                item_d.text() if item_d else "",
            ]).lower()

            self.tabela.setRowHidden(row, termo not in conteudo)


class PainelConfiguracaoAreaDesenho(QWidget):
    """
    Painel de configuração direta das coordenadas da Área de Desenho da Caneta (X e Y início/fim).
    """

    def __init__(
        self,
        gerenciador_area: GerenciadorAreaDesenho,
        controlador_grbl: Optional[ControladorGrbl] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.gerenciador_area = gerenciador_area
        self.controlador_grbl = controlador_grbl
        self._bloqueando_sinais = False

        self._configurar_ui()
        self._carregar_valores()

    def _configurar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Card Principal de Coordenadas
        card_coords = QFrame()
        card_coords.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_card = QVBoxLayout(card_coords)
        layout_card.setContentsMargins(16, 16, 16, 16)
        layout_card.setSpacing(12)

        rotulo_titulo = QLabel("📐 Coordenadas da Área de Desenho")
        rotulo_titulo.setStyleSheet("font-weight: 700; color: #7da4ff; font-size: 13px;")
        layout_card.addWidget(rotulo_titulo)

        rotulo_desc = QLabel(
            "Defina as coordenadas de início e fim (em milímetros) da área útil onde a caneta desenhará.\n"
            "Essas coordenadas formam o retângulo delimitador exibido em tempo real no Mapa 2D."
        )
        rotulo_desc.setStyleSheet("color: #9090a8; font-size: 11px; margin-bottom: 6px;")
        layout_card.addWidget(rotulo_desc)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # X Início
        lbl_xi = QLabel("X Início (mm):")
        lbl_xi.setStyleSheet("font-weight: 600; color: #e8e8f0;")
        self.spin_x_inicio = QDoubleSpinBox()
        self.spin_x_inicio.setRange(-500.0, 1500.0)
        self.spin_x_inicio.setDecimals(2)
        self.spin_x_inicio.setSingleStep(1.0)
        self.spin_x_inicio.valueChanged.connect(self._ao_alterar_valores)

        # Y Início
        lbl_yi = QLabel("Y Início (mm):")
        lbl_yi.setStyleSheet("font-weight: 600; color: #e8e8f0;")
        self.spin_y_inicio = QDoubleSpinBox()
        self.spin_y_inicio.setRange(-500.0, 1500.0)
        self.spin_y_inicio.setDecimals(2)
        self.spin_y_inicio.setSingleStep(1.0)
        self.spin_y_inicio.valueChanged.connect(self._ao_alterar_valores)

        # X Fim
        lbl_xf = QLabel("X Fim (mm):")
        lbl_xf.setStyleSheet("font-weight: 600; color: #e8e8f0;")
        self.spin_x_fim = QDoubleSpinBox()
        self.spin_x_fim.setRange(-500.0, 1500.0)
        self.spin_x_fim.setDecimals(2)
        self.spin_x_fim.setSingleStep(1.0)
        self.spin_x_fim.valueChanged.connect(self._ao_alterar_valores)

        # Y Fim
        lbl_yf = QLabel("Y Fim (mm):")
        lbl_yf.setStyleSheet("font-weight: 600; color: #e8e8f0;")
        self.spin_y_fim = QDoubleSpinBox()
        self.spin_y_fim.setRange(-500.0, 1500.0)
        self.spin_y_fim.setDecimals(2)
        self.spin_y_fim.setSingleStep(1.0)
        self.spin_y_fim.valueChanged.connect(self._ao_alterar_valores)

        grid.addWidget(lbl_xi, 0, 0)
        grid.addWidget(self.spin_x_inicio, 0, 1)
        grid.addWidget(lbl_yi, 0, 2)
        grid.addWidget(self.spin_y_inicio, 0, 3)

        grid.addWidget(lbl_xf, 1, 0)
        grid.addWidget(self.spin_x_fim, 1, 1)
        grid.addWidget(lbl_yf, 1, 2)
        grid.addWidget(self.spin_y_fim, 1, 3)

        layout_card.addLayout(grid)

        # Card de Resumo de Dimensões
        layout_info = QHBoxLayout()
        layout_info.setSpacing(12)

        self.lbl_dimensoes = QLabel("Largura (X): 210.00 mm  |  Altura (Y): 297.00 mm")
        self.lbl_dimensoes.setStyleSheet(
            "background-color: #1a1a35; color: #4ade80; border: 1px solid #285535; "
            "border-radius: 4px; padding: 6px 12px; font-weight: 700; font-size: 11px;"
        )
        layout_info.addWidget(self.lbl_dimensoes)
        layout_info.addStretch()

        layout_card.addLayout(layout_info)

        # Botão Salvar
        layout_botoes = QHBoxLayout()
        self.botao_salvar = QPushButton("💾 Salvar Área de Desenho")
        self.botao_salvar.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; padding: 8px 18px; border: 1px solid #7090ff; font-size: 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
        )
        self.botao_salvar.clicked.connect(self._salvar_configuracao)
        layout_botoes.addWidget(self.botao_salvar)
        layout_botoes.addStretch()

        layout_card.addLayout(layout_botoes)
        layout.addWidget(card_coords)
        layout.addStretch()

    def _carregar_valores(self) -> None:
        self._bloqueando_sinais = True
        try:
            cfg = self.gerenciador_area.obter_configuracao()
            self.spin_x_inicio.setValue(cfg.x_inicio)
            self.spin_y_inicio.setValue(cfg.y_inicio)
            self.spin_x_fim.setValue(cfg.x_fim)
            self.spin_y_fim.setValue(cfg.y_fim)
            self._atualizar_rotulo_dimensoes()
        finally:
            self._bloqueando_sinais = False

    def _ao_alterar_valores(self) -> None:
        if self._bloqueando_sinais:
            return
        self._atualizar_rotulo_dimensoes()

    def _atualizar_rotulo_dimensoes(self) -> None:
        largura = abs(self.spin_x_fim.value() - self.spin_x_inicio.value())
        altura = abs(self.spin_y_fim.value() - self.spin_y_inicio.value())
        self.lbl_dimensoes.setText(f"Largura (X): {largura:.2f} mm  |  Altura (Y): {altura:.2f} mm")

    def _salvar_configuracao(self) -> None:
        xi = self.spin_x_inicio.value()
        yi = self.spin_y_inicio.value()
        xf = self.spin_x_fim.value()
        yf = self.spin_y_fim.value()

        self.gerenciador_area.atualizar_area(xi, yi, xf, yf)
        QMessageBox.information(
            self,
            "Sucesso",
            f"Área de desenho salva com sucesso!\n\n"
            f"X: {xi:.2f} mm até {xf:.2f} mm\n"
            f"Y: {yi:.2f} mm até {yf:.2f} mm\n"
            f"Dimensões: {abs(xf - xi):.2f} × {abs(yf - yi):.2f} mm"
        )


class AbaConfiguracoes(QWidget):
    """
    Aba principal de Configurações da Plotter AXIS.
    """

    def __init__(
        self,
        controlador_grbl: Optional[ControladorGrbl] = None,
        gerenciador_canetas: Optional[GerenciadorCanetas] = None,
        gerenciador_macros: Optional[GerenciadorMacros] = None,
        gerenciador_area: Optional[GerenciadorAreaDesenho] = None,
        gerenciador_nivelamento: Optional[GerenciadorNivelamento] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controlador_grbl = controlador_grbl or ControladorGrbl()
        self.gerenciador_canetas = gerenciador_canetas or GerenciadorCanetas()
        self.gerenciador_macros = gerenciador_macros or GerenciadorMacros()
        self.gerenciador_area = gerenciador_area or GerenciadorAreaDesenho()
        self.gerenciador_nivelamento = gerenciador_nivelamento or GerenciadorNivelamento(
            gerenciador_area=self.gerenciador_area,
            gerenciador_canetas=self.gerenciador_canetas
        )

        self._configurar_ui()

    def _configurar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        tab_config = QTabWidget()

        # Sub-Aba 1: Troca de Canetas & G-code
        self.painel_canetas = PainelConfiguracaoCanetas(
            gerenciador_canetas=self.gerenciador_canetas,
            controlador_grbl=self.controlador_grbl,
            parent=self
        )
        tab_config.addTab(self.painel_canetas, "🎨 Troca de Canetas (10 Cores) & G-code")

        # Sub-Aba 2: Área de Desenho
        self.painel_area_desenho = PainelConfiguracaoAreaDesenho(
            gerenciador_area=self.gerenciador_area,
            controlador_grbl=self.controlador_grbl,
            parent=self
        )
        tab_config.addTab(self.painel_area_desenho, "📐 Área de Desenho")

        # Sub-Aba 3: Calibrar Z-Offset das Canetas (Nivelamento)
        self.painel_calibracao_z = PainelCalibracaoZOffset(
            gerenciador_nivelamento=self.gerenciador_nivelamento,
            gerenciador_canetas=self.gerenciador_canetas,
            gerenciador_area=self.gerenciador_area,
            controlador_grbl=self.controlador_grbl,
            parent=self
        )
        tab_config.addTab(self.painel_calibracao_z, "🎯 Calibrar Z-Offset das Canetas")

        # Sub-Aba 4: Biblioteca de Macros Customizadas
        tab_config.addTab(self._criar_subaba_macros(), "⚡ Biblioteca de Macros G-code")

        # Sub-Aba 5: Parâmetros da Máquina (GRBL)
        self.painel_grbl = PainelParametrosGrbl(
            controlador_grbl=self.controlador_grbl,
            parent=self
        )
        tab_config.addTab(self.painel_grbl, "🔧 Parâmetros do Firmware GRBL")

        layout.addWidget(tab_config)

    def _criar_subaba_macros(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        divisor = QSplitter(Qt.Orientation.Horizontal)

        # Lista de Macros
        widget_lista = QFrame()
        widget_lista.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_lista = QVBoxLayout(widget_lista)
        layout_lista.setContentsMargins(8, 8, 8, 8)

        self.lista_macros = QListWidget()
        self.lista_macros.itemClicked.connect(self._ao_selecionar_macro)

        layout_botoes = QHBoxLayout()
        self.botao_nova_macro = QPushButton("➕ Nova Macro")
        self.botao_nova_macro.clicked.connect(self._criar_nova_macro)
        self.botao_excluir_macro = QPushButton("🗑️ Excluir")
        self.botao_excluir_macro.clicked.connect(self._excluir_macro)

        layout_botoes.addWidget(self.botao_nova_macro)
        layout_botoes.addWidget(self.botao_excluir_macro)

        layout_lista.addWidget(QLabel("Macros Cadastradas:"))
        layout_lista.addWidget(self.lista_macros, 1)
        layout_lista.addLayout(layout_botoes)

        divisor.addWidget(widget_lista)

        # Editor de Macro
        widget_editor = QFrame()
        widget_editor.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_editor = QVBoxLayout(widget_editor)
        layout_editor.setContentsMargins(8, 8, 8, 8)
        layout_editor.setSpacing(6)

        layout_meta = QHBoxLayout()
        layout_meta.setSpacing(6)

        self.input_macro_nome = QLineEdit()
        self.input_macro_nome.setPlaceholderText("Ex: Homing Seguro")

        self.input_macro_comando = QLineEdit()
        self.input_macro_comando.setPlaceholderText("Ex: HOME, TROCA_CANETA_1")
        self.input_macro_comando.setToolTip("Comando que será reconhecido e expandido no editor de G-code")

        self.input_macro_cat = QLineEdit()
        self.input_macro_cat.setPlaceholderText("Categoria")
        self.input_macro_cat.setMaximumWidth(110)

        layout_meta.addWidget(QLabel("Nome:"))
        layout_meta.addWidget(self.input_macro_nome, 2)
        layout_meta.addWidget(QLabel("Comando G-code:"))
        layout_meta.addWidget(self.input_macro_comando, 2)
        layout_meta.addWidget(QLabel("Cat:"))
        layout_meta.addWidget(self.input_macro_cat, 1)

        self.input_macro_desc = QLineEdit()
        self.input_macro_desc.setPlaceholderText("Descrição da ação da macro...")

        self.editor_macro_gcode = QTextEdit()
        self.editor_macro_gcode.setPlaceholderText("Insira as linhas de G-code da macro aqui...")

        layout_acoes_macro = QHBoxLayout()
        self.botao_salvar_macro = QPushButton("💾 Salvar Macro")
        self.botao_salvar_macro.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; }"
        )
        self.botao_salvar_macro.clicked.connect(self._salvar_macro)

        self.botao_executar_macro = QPushButton("▶ Executar na Máquina")
        self.botao_executar_macro.setStyleSheet(
            "QPushButton { background-color: #22c55e; color: white; font-weight: bold; border: 1px solid #4ade80; }"
        )
        self.botao_executar_macro.clicked.connect(self._executar_macro)

        layout_acoes_macro.addWidget(self.botao_salvar_macro, 1)
        layout_acoes_macro.addWidget(self.botao_executar_macro)

        layout_editor.addLayout(layout_meta)
        layout_editor.addWidget(self.input_macro_desc)
        layout_editor.addWidget(self.editor_macro_gcode, 1)
        layout_editor.addLayout(layout_acoes_macro)

        divisor.addWidget(widget_editor)
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 2)

        layout.addWidget(divisor)
        self._carregar_lista_macros()
        return widget

    def _carregar_lista_macros(self) -> None:
        self.lista_macros.clear()
        macros = self.gerenciador_macros.obter_todas_macros()
        for macro in macros:
            cmd = macro.comando_gcode or macro.id.upper()
            item = QListWidgetItem(f"{macro.nome}  [{cmd}]")
            item.setData(Qt.ItemDataRole.UserRole, macro.id)
            self.lista_macros.addItem(item)
        if macros:
            self._carregar_macro_editor(macros[0])

    def _ao_selecionar_macro(self, item: QListWidgetItem) -> None:
        id_macro = item.data(Qt.ItemDataRole.UserRole)
        macro = self.gerenciador_macros.obter_macro(id_macro)
        if macro:
            self._carregar_macro_editor(macro)

    def _carregar_macro_editor(self, macro: MacroGcode) -> None:
        self.input_macro_nome.setText(macro.nome)
        self.input_macro_comando.setText(macro.comando_gcode or macro.id.upper())
        self.input_macro_cat.setText(macro.categoria)
        self.input_macro_desc.setText(macro.descricao)
        self.editor_macro_gcode.setPlainText(macro.gcode)
        self.editor_macro_gcode.setProperty("macro_id", macro.id)

    def _criar_nova_macro(self) -> None:
        self.input_macro_nome.setText("Nova Macro")
        self.input_macro_comando.setText("MINHA_MACRO")
        self.input_macro_cat.setText("Geral")
        self.input_macro_desc.setText("")
        self.editor_macro_gcode.setPlainText("G90\nG0 Z15 F2000\n")
        self.editor_macro_gcode.setProperty("macro_id", None)

    def _salvar_macro(self) -> None:
        macro_id = self.editor_macro_gcode.property("macro_id")
        nome = self.input_macro_nome.text().strip() or "Nova Macro"
        comando = self.input_macro_comando.text().strip().upper().replace(" ", "_")
        cat = self.input_macro_cat.text().strip() or "Geral"
        desc = self.input_macro_desc.text().strip()
        gcode = self.editor_macro_gcode.toPlainText().strip()

        if not macro_id:
            import time
            macro_id = f"macro_{int(time.time())}"

        if not comando:
            comando = macro_id.upper()

        nova = MacroGcode(
            id=macro_id,
            nome=nome,
            descricao=desc,
            gcode=gcode,
            categoria=cat,
            comando_gcode=comando
        )
        self.gerenciador_macros.salvar_ou_atualizar_macro(nova)
        self._carregar_lista_macros()
        QMessageBox.information(self, "Sucesso", f"Macro '{nome}' [{comando}] salva!")

    def _excluir_macro(self) -> None:
        item = self.lista_macros.currentItem()
        if not item:
            return
        id_m = item.data(Qt.ItemDataRole.UserRole)
        self.gerenciador_macros.remover_macro(id_m)
        self._carregar_lista_macros()

    def _executar_macro(self) -> None:
        item = self.lista_macros.currentItem()
        if not item:
            return
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de executar.")
            return
        id_m = item.data(Qt.ItemDataRole.UserRole)
        self.gerenciador_macros.executar_macro(id_m, self.controlador_grbl)

    def _solicitar_config_grbl(self) -> None:
        if hasattr(self, "painel_grbl"):
            self.painel_grbl._solicitar_leitura_grbl()
        elif self.controlador_grbl.esta_conectado():
            self.controlador_grbl.obter_configuracao_area_trabalho()
            QMessageBox.information(self, "GRBL", "Solicitação de configurações ($$) enviada.")
        else:
            QMessageBox.warning(self, "Aviso", "Máquina não conectada.")

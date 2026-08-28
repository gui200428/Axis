"""
Módulo de interface gráfica para a aba de Macros e Troca de Canetas (10 Cores).

Permite calibrar as posições X, Y, Z de cada um dos 10 slots de canetas,
disparar trocas de ferramentas com 1 clique, testar rotinas de engate/descarte,
e gerenciar uma biblioteca de macros G-code personalizadas.
"""

from typing import Optional, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QGroupBox, QDoubleSpinBox, QSpinBox, QScrollArea,
    QSplitter, QFrame, QMessageBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont
from resources.controle_da_maquina.logica_controle_da_maquina import ControladorGrbl
from resources.controle_da_maquina.gerenciador_canetas import (
    GerenciadorCanetas, SlotCaneta,
    gerar_template_pegar_padrao, gerar_template_soltar_padrao
)
from resources.macros.logica_macros import GerenciadorMacros, MacroGcode
from resources.estilo.tema_escuro import ESTILO_CARD_PADRAO


class CardSlotCaneta(QFrame):
    """
    Card visual individual para calibração e ação rápida de um dos 10 slots de caneta.
    """

    def __init__(
        self,
        slot_caneta: SlotCaneta,
        gerenciador_canetas: GerenciadorCanetas,
        controlador_grbl: ControladorGrbl,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.slot = slot_caneta
        self.gerenciador_canetas = gerenciador_canetas
        self.controlador_grbl = controlador_grbl

        self._configurar_ui()
        self._atualizar_estado_visual()

    def _configurar_ui(self) -> None:
        """Monta a estrutura visual do card com inputs compactos e botões táteis."""
        self.setStyleSheet(
            "CardSlotCaneta {"
            "  background-color: #222240;"
            "  border: 1px solid #2e2e4a;"
            "  border-radius: 8px;"
            "}"
            "CardSlotCaneta:hover {"
            "  border-color: #5b7fff;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Cabeçalho com indicador de cor e ID
        layout_cabecalho = QHBoxLayout()
        layout_cabecalho.setSpacing(6)

        self.rotulo_cor_pill = QLabel(f"  {self.slot.id}  ")
        self.rotulo_cor_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_cor_pill.setFixedHeight(20)
        self.rotulo_cor_pill.setStyleSheet(
            f"background-color: {self.slot.cor_hex}; color: #ffffff; "
            f"font-weight: 800; font-size: 11px; border-radius: 4px; border: 1px solid #ffffff33;"
        )

        self.input_nome = QLineEdit(self.slot.nome)
        self.input_nome.setPlaceholderText("Nome da cor")
        self.input_nome.setStyleSheet("font-weight: 600; font-size: 11px; padding: 2px 4px;")

        self.badge_status = QLabel("BAIA")
        self.badge_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_status.setFixedHeight(18)
        self.badge_status.setStyleSheet(
            "background-color: #252540; color: #9090a8; font-size: 9px; "
            "font-weight: bold; border-radius: 3px; padding: 0 4px;"
        )

        self.rotulo_cor_pill.setToolTip(f"Macro G-code: TROCA_CANETA_{self.slot.id:02d}")

        self.badge_macro = QLabel(f"TROCA_CANETA_{self.slot.id:02d}")
        self.badge_macro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_macro.setStyleSheet(
            "color: #7da4ff; font-family: 'Consolas', monospace; font-size: 8px; font-weight: 700; background: #1a1a30; border-radius: 2px; padding: 1px 3px;"
        )

        layout_cabecalho.addWidget(self.rotulo_cor_pill)
        layout_cabecalho.addWidget(self.input_nome, 1)
        layout_cabecalho.addWidget(self.badge_status)
        layout_cabecalho.addWidget(self.badge_macro)
        layout.addLayout(layout_cabecalho)

        # Botão Principal de Troca Rápida
        self.botao_pegar = QPushButton(f"🖌️ Trocar (TROCA_CANETA_{self.slot.id:02d})")
        self.botao_pegar.setToolTip(f"Executa a rotina completa TROCA_CANETA_{self.slot.id:02d} (soltar atual + pegar)")
        self.botao_pegar.setFixedHeight(28)
        self.botao_pegar.setStyleSheet(
            "QPushButton {"
            "  background-color: #252540; color: #e8e8f0; font-weight: 600; font-size: 11px;"
            "  border: 1px solid #33334d; border-radius: 5px;"
            "}"
            "QPushButton:hover { background-color: #5b7fff; color: #ffffff; border-color: #7090ff; }"
        )
        self.botao_pegar.clicked.connect(self._ao_clicar_trocar_caneta)
        layout.addWidget(self.botao_pegar)

        # Grid compacto de Coordenadas (X, Y, Z de captura e descarte)
        grid_coords = QGridLayout()
        grid_coords.setSpacing(4)

        # X Pegar
        grid_coords.addWidget(QLabel("X:"), 0, 0)
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(-500.0, 1000.0)
        self.spin_x.setDecimals(1)
        self.spin_x.setValue(self.slot.x_pegar)
        grid_coords.addWidget(self.spin_x, 0, 1)

        # Y Pegar
        grid_coords.addWidget(QLabel("Y:"), 0, 2)
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(-500.0, 1000.0)
        self.spin_y.setDecimals(1)
        self.spin_y.setValue(self.slot.y_pegar)
        grid_coords.addWidget(self.spin_y, 0, 3)

        # Z Pegar
        grid_coords.addWidget(QLabel("Z:"), 1, 0)
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(-100.0, 100.0)
        self.spin_z.setDecimals(1)
        self.spin_z.setValue(self.slot.z_pegar)
        grid_coords.addWidget(self.spin_z, 1, 1)

        # Z Seguro
        grid_coords.addWidget(QLabel("Z Seg:"), 1, 2)
        self.spin_z_seguro = QDoubleSpinBox()
        self.spin_z_seguro.setRange(-100.0, 100.0)
        self.spin_z_seguro.setDecimals(1)
        self.spin_z_seguro.setValue(self.slot.z_seguro)
        grid_coords.addWidget(self.spin_z_seguro, 1, 3)

        layout.addLayout(grid_coords)

        # Rodapé de Ações do Card
        layout_acoes = QHBoxLayout()
        layout_acoes.setSpacing(4)

        self.botao_salvar = QPushButton("💾 Salvar")
        self.botao_salvar.setToolTip("Salvar calibração desta caneta")
        self.botao_salvar.setFixedHeight(22)
        self.botao_salvar.clicked.connect(self._salvar_dados_slot)

        self.botao_testar_pegar = QPushButton("Pegar")
        self.botao_testar_pegar.setToolTip("Executar macro de engate isolada")
        self.botao_testar_pegar.setFixedHeight(22)
        self.botao_testar_pegar.clicked.connect(self._testar_pegar)

        self.botao_testar_soltar = QPushButton("Soltar")
        self.botao_testar_soltar.setToolTip("Executar macro de descarte isolada")
        self.botao_testar_soltar.setFixedHeight(22)
        self.botao_testar_soltar.clicked.connect(self._testar_soltar)

        layout_acoes.addWidget(self.botao_salvar)
        layout_acoes.addWidget(self.botao_testar_pegar)
        layout_acoes.addWidget(self.botao_testar_soltar)
        layout.addLayout(layout_acoes)

    def recarregar_dados(self) -> None:
        """Recarrega os dados do slot a partir do gerenciador de canetas."""
        slot = self.gerenciador_canetas.obter_slot(self.slot.id)
        if slot:
            self.slot = slot
            self.input_nome.setText(slot.nome)
            self.rotulo_cor_pill.setStyleSheet(
                f"background-color: {slot.cor_hex}; color: white; "
                f"font-weight: 800; font-size: 11px; border-radius: 4px; border: 1px solid #ffffff33;"
            )
            self.spin_x.setValue(slot.x_pegar)
            self.spin_y.setValue(slot.y_pegar)
            self.spin_z.setValue(slot.z_pegar)
            self.spin_z_seguro.setValue(slot.z_seguro)
            self._atualizar_estado_visual()

    def _atualizar_estado_visual(self) -> None:
        """Atualiza os badges caso a caneta esteja ativa no cabeçote."""
        ativa_id = self.gerenciador_canetas.obter_caneta_ativa_id()
        if ativa_id == self.slot.id:
            self.badge_status.setText("ACOPLADA")
            self.badge_status.setStyleSheet(
                "background-color: #1a3a2a; color: #4ade80; font-size: 9px; "
                "font-weight: bold; border-radius: 3px; padding: 0 4px;"
            )
            self.setStyleSheet(
                "CardSlotCaneta {"
                "  background-color: #1e1e35;"
                "  border: 2px solid #5b7fff;"
                "  border-radius: 8px;"
                "}"
            )
        else:
            self.badge_status.setText("NA BAIA")
            self.badge_status.setStyleSheet(
                "background-color: #252540; color: #9090a8; font-size: 9px; "
                "font-weight: bold; border-radius: 3px; padding: 0 4px;"
            )
            self.setStyleSheet(
                "CardSlotCaneta {"
                "  background-color: #222240;"
                "  border: 1px solid #2e2e4a;"
                "  border-radius: 8px;"
                "}"
                "CardSlotCaneta:hover {"
                "  border-color: #5b7fff;"
                "}"
            )

    def _ao_clicar_trocar_caneta(self) -> None:
        """Dispara a troca inteligente para esta caneta no controlador GRBL."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de trocar de caneta.")
            return

        ativa_id = self.gerenciador_canetas.obter_caneta_ativa_id()
        gcode_troca = self.gerenciador_canetas.gerar_gcode_troca_completa(self.slot.id)

        # Se houver caneta ativa sendo devolvida e Z estiver baixo, garantir elevação prévia
        if ativa_id and ativa_id != self.slot.id:
            slot_ativo = self.gerenciador_canetas.obter_slot(ativa_id)
            z_seguro = slot_ativo.z_seguro if slot_ativo else -4.0
            velocidade = slot_ativo.velocidade if slot_ativo else 3000
            if not self.controlador_grbl.caneta_esta_alta(z_seguro):
                gcode_troca = f"G90\nG21\nG0 Z{z_seguro:.2f} F{velocidade}\n" + gcode_troca

        slot_id = self.slot.id
        self.controlador_grbl.enviar_script_gcode(
            gcode_troca,
            nome=f"Trocar Caneta → Slot {slot_id} ({self.slot.nome})",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(slot_id)
        )

    def _testar_pegar(self) -> None:
        """Executa apenas a rotina de pegar a caneta."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de testar.")
            return

        gcode = self.gerenciador_canetas.gerar_gcode_pegar_caneta(self.slot.id)
        slot_id = self.slot.id
        self.controlador_grbl.enviar_script_gcode(
            gcode,
            nome=f"Pegar Caneta → Slot {slot_id} ({self.slot.nome})",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(slot_id)
        )

    def _testar_soltar(self) -> None:
        """Executa apenas a rotina de soltar a caneta."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de testar.")
            return

        z_seguro = self.slot.z_seguro
        velocidade = self.slot.velocidade
        gcode = self.gerenciador_canetas.gerar_gcode_soltar_caneta(self.slot.id)

        # Garantir caneta alta antes de mover para a baia
        if not self.controlador_grbl.caneta_esta_alta(z_seguro):
            gcode = f"G90\nG21\nG0 Z{z_seguro:.2f} F{velocidade}\n" + gcode

        slot_id = self.slot.id

        def _apos_soltar() -> None:
            if self.gerenciador_canetas.obter_caneta_ativa_id() == slot_id:
                self.gerenciador_canetas.definir_caneta_ativa(None)

        self.controlador_grbl.enviar_script_gcode(
            gcode,
            nome=f"Soltar Caneta → Slot {slot_id} ({self.slot.nome})",
            callback_conclusao=_apos_soltar
        )

    def _salvar_dados_slot(self) -> None:
        """Salva as coordenadas e nome digitados e atualiza os scripts G-code."""
        self.slot.nome = self.input_nome.text().strip() or f"Caneta {self.slot.id}"
        self.slot.x_pegar = self.spin_x.value()
        self.slot.y_pegar = self.spin_y.value()
        self.slot.z_pegar = self.spin_z.value()
        self.slot.x_soltar = self.spin_x.value()
        self.slot.y_soltar = self.spin_y.value()
        self.slot.z_soltar = self.spin_z.value()
        self.slot.z_seguro = self.spin_z_seguro.value()
        self.slot.macro_pegar = gerar_template_pegar_padrao(
            self.slot.id, self.slot.nome, self.slot.x_pegar, self.slot.y_pegar,
            self.slot.z_pegar, self.slot.z_seguro, self.slot.velocidade
        )
        self.slot.macro_soltar = gerar_template_soltar_padrao(
            self.slot.id, self.slot.nome, self.slot.x_soltar, self.slot.y_soltar,
            self.slot.z_soltar, self.slot.z_seguro, self.slot.velocidade
        )

        self.gerenciador_canetas.atualizar_slot(self.slot)


class AbaMacros(QWidget):
    """
    Aba principal de gerenciamento de Macros e Troca de Canetas.
    """

    def __init__(
        self,
        controlador_grbl: Optional[ControladorGrbl] = None,
        gerenciador_canetas: Optional[GerenciadorCanetas] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controlador_grbl = controlador_grbl or ControladorGrbl()
        self.gerenciador_canetas = gerenciador_canetas or GerenciadorCanetas()
        self.gerenciador_macros = GerenciadorMacros()

        self._cards_canetas: Dict[int, CardSlotCaneta] = {}
        self._configurar_layout()
        self._conectar_sinais()

    def _configurar_layout(self) -> None:
        """Monta o layout com o rack superior de 10 canetas e a biblioteca de macros."""
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(10, 10, 10, 10)
        layout_principal.setSpacing(10)

        # Divisor Vertical: Topo = 10 Canetas | Base = Macros Customizadas
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Seção 1: Rack das 10 Canetas
        splitter.addWidget(self._criar_secao_rack_canetas())

        # Seção 2: Biblioteca de Macros G-code
        splitter.addWidget(self._criar_secao_macros())

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout_principal.addWidget(splitter)

    def _criar_secao_rack_canetas(self) -> QGroupBox:
        """Cria o container com os 10 cards das canetas dispostos em scroll responsivo."""
        grupo = QGroupBox("Rack de Canetas da Plotter (10 Cores)")
        grupo.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_grupo = QVBoxLayout(grupo)
        layout_grupo.setContentsMargins(8, 12, 8, 8)
        layout_grupo.setSpacing(6)

        # Barra de Ações Rápidas Globais do Rack
        layout_acoes_topo = QHBoxLayout()
        layout_acoes_topo.setSpacing(8)

        self.rotulo_caneta_ativa_status = QLabel("Caneta Ativa no Cabeçote: Nenhuma")
        self.rotulo_caneta_ativa_status.setStyleSheet("font-weight: bold; color: #7da4ff; font-size: 11px;")

        self.botao_devolver_atual = QPushButton("📥 Devolver Caneta Atual")
        self.botao_devolver_atual.setStyleSheet(
            "QPushButton { background-color: #252540; color: #e8e8f0; font-weight: 600; border: 1px solid #33334d; }"
            "QPushButton:hover { background-color: #33334d; border-color: #55556e; }"
        )
        self.botao_devolver_atual.clicked.connect(self._devolver_caneta_ativa)

        self.botao_desacoplar_manual = QPushButton("🔓 Declarar Cabeçote Livre")
        self.botao_desacoplar_manual.setToolTip("Define o estado como sem caneta no cabeçote sem mover motores")
        self.botao_desacoplar_manual.clicked.connect(lambda: self.gerenciador_canetas.definir_caneta_ativa(None))

        layout_acoes_topo.addWidget(self.rotulo_caneta_ativa_status)
        layout_acoes_topo.addStretch()
        layout_acoes_topo.addWidget(self.botao_devolver_atual)
        layout_acoes_topo.addWidget(self.botao_desacoplar_manual)

        layout_grupo.addLayout(layout_acoes_topo)

        # Scroll com Grid de 10 Cards (5 colunas x 2 linhas)
        area_scroll = QScrollArea()
        area_scroll.setWidgetResizable(True)
        area_scroll.setStyleSheet("background: transparent; border: none;")

        container_cards = QWidget()
        container_cards.setStyleSheet("background: transparent;")
        grid_cards = QGridLayout(container_cards)
        grid_cards.setSpacing(8)
        grid_cards.setContentsMargins(2, 2, 2, 2)

        slots = self.gerenciador_canetas.obter_todos_slots()
        for indice, slot in enumerate(slots):
            linha = indice // 5
            coluna = indice % 5
            card = CardSlotCaneta(slot, self.gerenciador_canetas, self.controlador_grbl, self)
            self._cards_canetas[slot.id] = card
            grid_cards.addWidget(card, linha, coluna)

        area_scroll.setWidget(container_cards)
        layout_grupo.addWidget(area_scroll, 1)

        return grupo

    def _criar_secao_macros(self) -> QGroupBox:
        """Cria a seção de biblioteca e edição de macros personalizadas."""
        grupo = QGroupBox("Biblioteca de Macros G-code Personalizadas")
        grupo.setStyleSheet(ESTILO_CARD_PADRAO)
        layout_grupo = QVBoxLayout(grupo)
        layout_grupo.setContentsMargins(8, 12, 8, 8)
        layout_grupo.setSpacing(6)

        divisor_horizontal = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: Lista de Macros e Disparo Rápido
        widget_lista = QWidget()
        layout_lista = QVBoxLayout(widget_lista)
        layout_lista.setContentsMargins(0, 0, 0, 0)
        layout_lista.setSpacing(6)

        self.lista_macros = QListWidget()
        self.lista_macros.itemClicked.connect(self._ao_selecionar_macro)

        layout_botoes_lista = QHBoxLayout()
        layout_botoes_lista.setSpacing(6)

        self.botao_executar_macro = QPushButton("▶ Executar Macro")
        self.botao_executar_macro.setStyleSheet(
            "QPushButton { background-color: #22c55e; color: white; font-weight: bold; border: 1px solid #4ade80; }"
            "QPushButton:hover { background-color: #16a34a; }"
        )
        self.botao_executar_macro.clicked.connect(self._executar_macro_selecionada)

        self.botao_nova_macro = QPushButton("➕ Nova Macro")
        self.botao_nova_macro.clicked.connect(self._criar_nova_macro)

        self.botao_excluir_macro = QPushButton("🗑️ Excluir")
        self.botao_excluir_macro.clicked.connect(self._excluir_macro_selecionada)

        layout_botoes_lista.addWidget(self.botao_executar_macro, 1)
        layout_botoes_lista.addWidget(self.botao_nova_macro)
        layout_botoes_lista.addWidget(self.botao_excluir_macro)

        layout_lista.addWidget(QLabel("Macros Cadastradas:"))
        layout_lista.addWidget(self.lista_macros, 1)
        layout_lista.addLayout(layout_botoes_lista)

        # Painel Direito: Editor da Macro Selecionada
        widget_editor = QWidget()
        layout_editor = QVBoxLayout(widget_editor)
        layout_editor.setContentsMargins(0, 0, 0, 0)
        layout_editor.setSpacing(6)

        layout_meta = QHBoxLayout()
        layout_meta.setSpacing(6)

        self.input_nome_macro = QLineEdit()
        self.input_nome_macro.setPlaceholderText("Ex: Limpeza Rápida")

        self.input_comando_macro = QLineEdit()
        self.input_comando_macro.setPlaceholderText("Ex: HOME, TROCA_CANETA_1")
        self.input_comando_macro.setToolTip("Comando que será reconhecido e expandido no editor de G-code")

        self.input_cat_macro = QLineEdit()
        self.input_cat_macro.setPlaceholderText("Categoria")
        self.input_cat_macro.setMaximumWidth(110)

        layout_meta.addWidget(QLabel("Nome:"))
        layout_meta.addWidget(self.input_nome_macro, 2)
        layout_meta.addWidget(QLabel("Comando G-code:"))
        layout_meta.addWidget(self.input_comando_macro, 2)
        layout_meta.addWidget(QLabel("Cat:"))
        layout_meta.addWidget(self.input_cat_macro, 1)

        self.input_desc_macro = QLineEdit()
        self.input_desc_macro.setPlaceholderText("Descrição rápida da ação da macro...")

        self.editor_gcode_macro = QTextEdit()
        self.editor_gcode_macro.setPlaceholderText("Insira as linhas de G-code da macro aqui...")

        self.botao_salvar_macro = QPushButton("💾 Salvar Alterações na Macro")
        self.botao_salvar_macro.setStyleSheet(
            "QPushButton { background-color: #5b7fff; color: white; font-weight: bold; border: 1px solid #7090ff; }"
            "QPushButton:hover { background-color: #4a6ae0; }"
        )
        self.botao_salvar_macro.clicked.connect(self._salvar_macro_editor)

        layout_editor.addLayout(layout_meta)
        layout_editor.addWidget(self.input_desc_macro)
        layout_editor.addWidget(self.editor_gcode_macro, 1)
        layout_editor.addWidget(self.botao_salvar_macro)

        divisor_horizontal.addWidget(widget_lista)
        divisor_horizontal.addWidget(widget_editor)
        divisor_horizontal.setStretchFactor(0, 2)
        divisor_horizontal.setStretchFactor(1, 3)

        layout_grupo.addWidget(divisor_horizontal)
        self._carregar_lista_macros()
        return grupo

    # ------------------------------------------------------------------ #
    #                      CONEXÃO DE SINAIS                              #
    # ------------------------------------------------------------------ #

    def _conectar_sinais(self) -> None:
        """Conecta sinais entre gerenciadores e os cards visuais."""
        self.gerenciador_canetas.sinal_caneta_alterada.connect(self._ao_alterar_caneta_ativa)
        self.gerenciador_canetas.sinal_slots_atualizados.connect(self._atualizar_todos_cards)
        self.gerenciador_macros.sinal_macros_atualizadas.connect(self._carregar_lista_macros)

    # ------------------------------------------------------------------ #
    #                           AÇÕES / SLOTS                            #
    # ------------------------------------------------------------------ #

    @Slot(int, str, str)
    def _ao_alterar_caneta_ativa(self, id_caneta: int, nome: str, cor_hex: str) -> None:
        """Atualiza a exibição de status quando a caneta no cabeçote muda."""
        if id_caneta > 0:
            self.rotulo_caneta_ativa_status.setText(f"Caneta Ativa no Cabeçote: [{id_caneta}] {nome}")
            self.rotulo_caneta_ativa_status.setStyleSheet(f"font-weight: 800; color: {cor_hex}; font-size: 11px;")
        else:
            self.rotulo_caneta_ativa_status.setText("Caneta Ativa no Cabeçote: Nenhuma (Livre)")
            self.rotulo_caneta_ativa_status.setStyleSheet("font-weight: bold; color: #9090a8; font-size: 11px;")

        self._atualizar_todos_cards()

    def _atualizar_todos_cards(self) -> None:
        """Atualiza visualmente e recarrega os dados de todos os 10 cards de canetas."""
        for card in self._cards_canetas.values():
            card.recarregar_dados()

    def _devolver_caneta_ativa(self) -> None:
        """Dispara a rotina de devolver a caneta que estiver acoplada."""
        ativa_id = self.gerenciador_canetas.obter_caneta_ativa_id()
        if not ativa_id:
            QMessageBox.information(self, "Aviso", "Nenhuma caneta está acoplada no cabeçote.")
            return

        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de soltar a caneta.")
            return

        slot = self.gerenciador_canetas.obter_slot(ativa_id)
        z_seguro = slot.z_seguro if slot else -4.0
        vel = slot.velocidade if slot else 3000

        gcode = self.gerenciador_canetas.gerar_gcode_soltar_caneta(ativa_id)
        if not self.controlador_grbl.caneta_esta_alta(z_seguro):
            gcode = f"G90\nG21\nG0 Z{z_seguro:.2f} F{vel}\n" + gcode

        self.controlador_grbl.enviar_script_gcode(
            gcode,
            nome=f"Devolver Caneta [{ativa_id:02d}]",
            callback_conclusao=lambda: self.gerenciador_canetas.definir_caneta_ativa(None)
        )

    # ---- Gerenciamento da Biblioteca de Macros ---- #

    def _carregar_lista_macros(self) -> None:
        """Preenche a lista visual com as macros registradas."""
        self.lista_macros.clear()
        macros = self.gerenciador_macros.obter_todas_macros()
        for macro in macros:
            cmd = macro.comando_gcode or macro.id.upper()
            item = QListWidgetItem(f"{macro.nome}  [{cmd}]")
            item.setData(Qt.ItemDataRole.UserRole, macro.id)
            self.lista_macros.addItem(item)

        if macros and not self.input_nome_macro.text():
            self._carregar_macro_no_editor(macros[0])

    def _ao_selecionar_macro(self, item: QListWidgetItem) -> None:
        """Ao clicar em um item da lista, carrega seus dados no editor."""
        id_macro = item.data(Qt.ItemDataRole.UserRole)
        macro = self.gerenciador_macros.obter_macro(id_macro)
        if macro:
            self._carregar_macro_no_editor(macro)

    def _carregar_macro_no_editor(self, macro: MacroGcode) -> None:
        """Preenche os campos do editor com os dados da macro."""
        self.input_nome_macro.setText(macro.nome)
        self.input_comando_macro.setText(macro.comando_gcode or macro.id.upper())
        self.input_cat_macro.setText(macro.categoria)
        self.input_desc_macro.setText(macro.descricao)
        self.editor_gcode_macro.setPlainText(macro.gcode)
        self.editor_gcode_macro.setProperty("macro_id_atual", macro.id)

    def _criar_nova_macro(self) -> None:
        """Limpa o editor para criar uma nova macro."""
        self.input_nome_macro.setText("Nova Macro")
        self.input_comando_macro.setText("MINHA_MACRO")
        self.input_cat_macro.setText("Geral")
        self.input_desc_macro.setText("Descrição da nova macro")
        self.editor_gcode_macro.setPlainText("; Digite o código G-code aqui\nG90\nG0 Z10\n")
        self.editor_gcode_macro.setProperty("macro_id_atual", None)

    def _salvar_macro_editor(self) -> None:
        """Salva a macro em edição no gerenciador."""
        macro_id = self.editor_gcode_macro.property("macro_id_atual")
        nome = self.input_nome_macro.text().strip() or "Macro Sem Nome"
        comando = self.input_comando_macro.text().strip().upper().replace(" ", "_")
        categoria = self.input_cat_macro.text().strip() or "Geral"
        descricao = self.input_desc_macro.text().strip()
        gcode = self.editor_gcode_macro.toPlainText().strip()

        if not macro_id:
            import time
            macro_id = f"macro_{int(time.time())}"

        if not comando:
            comando = macro_id.upper()

        nova_macro = MacroGcode(
            id=macro_id,
            nome=nome,
            descricao=descricao,
            gcode=gcode,
            categoria=categoria,
            comando_gcode=comando
        )
        self.gerenciador_macros.salvar_ou_atualizar_macro(nova_macro)
        self.editor_gcode_macro.setProperty("macro_id_atual", macro_id)
        QMessageBox.information(self, "Sucesso", f"Macro '{nome}' [{comando}] salva com sucesso!")

    def _excluir_macro_selecionada(self) -> None:
        """Exclui a macro atualmente selecionada."""
        item = self.lista_macros.currentItem()
        if not item:
            return

        id_macro = item.data(Qt.ItemDataRole.UserRole)
        confirmacao = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Deseja realmente excluir a macro selecionada?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirmacao == QMessageBox.StandardButton.Yes:
            self.gerenciador_macros.remover_macro(id_macro)
            self._criar_nova_macro()

    def _executar_macro_selecionada(self) -> None:
        """Dispara a execução da macro selecionada no controlador GRBL."""
        if not self.controlador_grbl.esta_conectado():
            QMessageBox.warning(self, "Aviso", "Conecte a máquina à porta serial antes de executar macros.")
            return

        item = self.lista_macros.currentItem()
        if not item:
            return

        id_macro = item.data(Qt.ItemDataRole.UserRole)
        self.gerenciador_macros.executar_macro(id_macro, self.controlador_grbl)

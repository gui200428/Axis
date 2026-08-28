"""
Módulo de gerenciamento detalhado das 10 canetas da plotter AXIS.

Permite calibração de parâmetros físicos e personalização livre do script
G-code de engate (pegar) e descarte (soltar) para cada uma das 10 canetas.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal


def _format_coord(valor_coordenada: float) -> str:
    """
    Formata coordenadas numéricas de forma limpa para comandos G-code.

    Args:
        valor_coordenada (float): Valor numérico da coordenada em milímetros.

    Returns:
        str: String formatada sem zeros à direita desnecessários.
    """
    if valor_coordenada == int(valor_coordenada):
        return str(int(valor_coordenada))
    return f"{valor_coordenada:.4f}".rstrip('0').rstrip('.')


def gerar_template_pegar_padrao(
    id_slot: int,
    nome: str,
    x: float,
    y: float,
    z: float,
    z_seguro: float,
    velocidade: int
) -> str:
    """
    Gera o script G-code padrão de engate de caneta / estojo.

    Args:
        id_slot (int): Identificador do slot (1 a 10).
        nome (str): Nome descritivo da caneta.
        x (float): Coordenada X física da baia em milímetros.
        y (float): Coordenada Y física da baia em milímetros.
        z (float): Coordenada Z de acoplamento da caneta.
        z_seguro (float): Altura Z segura no ar para trânsito livre.
        velocidade (int): Velocidade de avanço (feed rate) em mm/min.

    Returns:
        str: Bloco de comandos G-code formatado para engate.
    """
    slot_num = f"Slot{id_slot - 1:02d}"
    x_str = _format_coord(x)
    y_str = _format_coord(y)
    z_str = _format_coord(z)
    z_seg_str = _format_coord(z_seguro)
    y_field = f"Y{y_str:<10}"
    return (
        f"; === PEGAR CANETA {id_slot} ({nome}) - {slot_num} ===\n"
        f"G90 ; Coordenadas absolutas\n"
        f"G21 ; Unidades em milimetros\n\n"
        f"G1 F{velocidade} X250      ; Posiciona em X seguro, longe do estojo\n"
        f"G1 F{velocidade} {y_field}; Ajusta Y alinhado ao {slot_num.lower()} (ainda em X seguro)\n"
        f"G1 F{velocidade} X300        ; Avanca em X ate a posicao de acoplamento\n"
        f"G1 F150  Z{z_str}          ; Desce ate a profundidade de acoplamento\n"
        f"G1 F2500 X{x_str}        ; Desliza em X, acopla magneticamente na caneta\n"
        f"G4 P0.3                 ; Tempo de acomodacao mecanica\n"
        f"G1 F150  Z{z_seg_str}               ; Levanta com a caneta acoplada, sai do slot\n"
        f"G1 F{velocidade} X250              ; Recua totalmente em X, distancia segura do estojo\n"
        f"; Fim do engate da caneta {id_slot} ({nome} - {slot_num.lower()})"
    )


def gerar_template_soltar_padrao(
    id_slot: int,
    nome: str,
    x: float,
    y: float,
    z: float,
    z_seguro: float,
    velocidade: int
) -> str:
    """
    Gera o script G-code padrão de descarte / guardar caneta / estojo.

    Args:
        id_slot (int): Identificador do slot (1 a 10).
        nome (str): Nome descritivo da caneta.
        x (float): Coordenada X física da baia em milímetros.
        y (float): Coordenada Y física da baia em milímetros.
        z (float): Coordenada Z de desacoplamento no slot.
        z_seguro (float): Altura Z segura no ar para trânsito livre.
        velocidade (int): Velocidade de avanço (feed rate) em mm/min.

    Returns:
        str: Bloco de comandos G-code formatado para devolução.
    """
    slot_num = f"Slot{id_slot - 1:02d}"
    x_str = _format_coord(x)
    y_str = _format_coord(y)
    z_str = _format_coord(z)
    z_seg_str = _format_coord(z_seguro)
    y_field = f"Y{y_str:<10}"
    return (
        f"; === GUARDAR CANETA {id_slot} ({nome}) - {slot_num} ===\n"
        f"G90 ; Coordenadas absolutas\n"
        f"G21 ; Unidades em milimetros\n\n"
        f"G1 F{velocidade} X250      ; Posiciona em X seguro, longe do estojo\n"
        f"G1 F{velocidade} {y_field}; Ajusta Y alinhado ao {slot_num.lower()} (ainda em X seguro)\n"
        f"G1 F{velocidade} X300        ; Avanca em X ate a posicao alinhada\n"
        f"G1 F250  X{x_str}       ; Avanco fino, insere a caneta no slot\n"
        f"G1 F150  Z{z_str}           ; Desce, acopla/trava a caneta no slot\n"
        f"G4 P0.3                 ; Tempo de acomodacao mecanica\n"
        f"G1 F2500 X300             ; Retrai X, desacopla o gripper da caneta\n"
        f"G1 F150  Z{z_seg_str}                ; Sobe para altura segura (gripper vazio)\n"
        f"G1 F{velocidade} X250                ; Recua totalmente em X, distancia segura do estojo\n"
        f"; Fim do desengate da caneta {id_slot} ({nome} - {slot_num.lower()})"
    )


@dataclass
class SlotCaneta:
    """Representa a configuração completa e o script G-code de um slot de caneta."""
    id: int
    nome: str
    cor_hex: str
    x_pegar: float
    y_pegar: float
    z_pegar: float
    x_soltar: float
    y_soltar: float
    z_soltar: float
    z_seguro: float = 0.0
    velocidade: int = 3000
    macro_pegar: str = ""
    macro_soltar: str = ""
    z_up: float = 0.0      # Altura da caneta levantada (trânsito seguro no ar) em mm
    z_down: float = 25.0   # Altura da caneta abaixada (contato/desenho nominal) em mm


CANETAS_PADRAO: List[Dict] = [
    {"id": 1, "nome": "Preto", "cor_hex": "#0f172a", "x_pegar": 327.7, "y_pegar": 326.0, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 326.0, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 2, "nome": "Azul", "cor_hex": "#2563eb", "x_pegar": 327.7, "y_pegar": 290.3, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 290.3, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 3, "nome": "Vermelho", "cor_hex": "#ef4444", "x_pegar": 327.7, "y_pegar": 253.7, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 253.7, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 4, "nome": "Verde", "cor_hex": "#10b981", "x_pegar": 327.7, "y_pegar": 217.4, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 217.4, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 5, "nome": "Amarelo", "cor_hex": "#eab308", "x_pegar": 327.7, "y_pegar": 181.1, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 181.1, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 6, "nome": "Laranja", "cor_hex": "#f97316", "x_pegar": 327.7, "y_pegar": 144.8, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 144.8, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 7, "nome": "Roxo", "cor_hex": "#a855f7", "x_pegar": 327.7, "y_pegar": 108.5, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 108.5, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 8, "nome": "Rosa", "cor_hex": "#ec4899", "x_pegar": 327.7, "y_pegar": 72.2, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 72.2, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 9, "nome": "Marrom", "cor_hex": "#854d0e", "x_pegar": 327.7, "y_pegar": 35.9, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 35.9, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
    {"id": 10, "nome": "Ciano", "cor_hex": "#06b6d4", "x_pegar": 327.7, "y_pegar": 0.0, "z_pegar": 25.0, "x_soltar": 327.7, "y_soltar": 0.0, "z_soltar": 25.0, "z_seguro": 0.0, "velocidade": 3000, "z_up": 0.0, "z_down": 25.0},
]


class GerenciadorCanetas(QObject):
    """
    Controlador centralizado do sistema de canetas e tool changer com G-code customizável.
    """

    sinal_caneta_alterada = Signal(int, str, str)  # (id_caneta, nome_caneta, cor_hex)
    sinal_slots_atualizados = Signal()

    def __init__(self, caminho_arquivo_config: Optional[str] = None) -> None:
        """
        Inicializa o gerenciador de canetas e carrega as configurações salvas.

        Args:
            caminho_arquivo_config (str, optional): Caminho para o arquivo JSON de canetas.
        """
        super().__init__()
        self._caminho_config = caminho_arquivo_config or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "canetas_plotter.json"
        )
        self._canetas: Dict[int, SlotCaneta] = {}
        self._caneta_ativa_id: Optional[int] = None

        self._carregar_configuracao()

    def obter_todos_slots(self) -> List[SlotCaneta]:
        """
        Retorna a lista ordenada com todos os 10 slots de canetas.

        Returns:
            List[SlotCaneta]: Lista de objetos SlotCaneta.
        """
        return [self._canetas[i] for i in sorted(self._canetas.keys())]

    def obter_slot(self, id_caneta: int) -> Optional[SlotCaneta]:
        """
        Retorna as configurações do slot de caneta pelo ID.

        Args:
            id_caneta (int): Identificador da caneta (1 a 10).

        Returns:
            Optional[SlotCaneta]: Objeto SlotCaneta ou None se não encontrado.
        """
        return self._canetas.get(id_caneta)

    def obter_caneta_ativa(self) -> Optional[SlotCaneta]:
        """
        Retorna o slot da caneta atualmente engatada no cabeçote físico.

        Returns:
            Optional[SlotCaneta]: Objeto da caneta ativa ou None se cabeçote estiver livre.
        """
        if self._caneta_ativa_id is not None:
            return self._canetas.get(self._caneta_ativa_id)
        return None

    def obter_caneta_ativa_id(self) -> Optional[int]:
        """
        Retorna o ID numérico da caneta atualmente engatada no cabeçote.

        Returns:
            Optional[int]: Número da caneta (1 a 10) ou None se não houver caneta engatada.
        """
        return self._caneta_ativa_id

    def definir_caneta_ativa(self, id_caneta: Optional[int]) -> None:
        """
        Define logicamente qual caneta está no cabeçote e emite o sinal de atualização.

        Args:
            id_caneta (int, optional): ID da caneta ou None para declarar cabeçote livre.
        """
        self._caneta_ativa_id = id_caneta
        if id_caneta is not None and id_caneta in self._canetas:
            caneta = self._canetas[id_caneta]
            self.sinal_caneta_alterada.emit(caneta.id, caneta.nome, caneta.cor_hex)
        else:
            self._caneta_ativa_id = None
            self.sinal_caneta_alterada.emit(0, "Nenhuma Caneta", "#6a6a82")

    def atualizar_slot(self, slot: SlotCaneta) -> None:
        """
        Atualiza as configurações de um slot de caneta e persiste no arquivo JSON.

        Args:
            slot (SlotCaneta): Objeto com as configurações atualizadas.
        """
        self._canetas[slot.id] = slot
        self._salvar_configuracao()
        self.sinal_slots_atualizados.emit()
        if self._caneta_ativa_id == slot.id:
            self.sinal_caneta_alterada.emit(slot.id, slot.nome, slot.cor_hex)

    def restaurar_macros_padrao_slot(self, id_slot: int) -> None:
        """
        Restaura os templates de G-code padrão de engate e descarte para o slot.

        Args:
            id_slot (int): Identificador do slot a ser restaurado.
        """
        slot = self._canetas.get(id_slot)
        if slot:
            slot.macro_pegar = gerar_template_pegar_padrao(
                slot.id, slot.nome, slot.x_pegar, slot.y_pegar, slot.z_pegar, slot.z_seguro, slot.velocidade
            )
            slot.macro_soltar = gerar_template_soltar_padrao(
                slot.id, slot.nome, slot.x_soltar, slot.y_soltar, slot.z_soltar, slot.z_seguro, slot.velocidade
            )
            self.atualizar_slot(slot)

    # ------------------------------------------------------------------ #
    #             GERAÇÃO DE G-CODE PARA TROCA DE CANETA                 #
    # ------------------------------------------------------------------ #

    def gerar_gcode_pegar_caneta(self, id_caneta: int) -> str:
        """
        Gera o script G-code para engate de uma caneta específica.

        Args:
            id_caneta (int): Número da caneta desejada (1 a 10).

        Returns:
            str: Bloco de comandos G-code de engate.
        """
        slot = self._canetas.get(id_caneta)
        if not slot:
            return ""

        if slot.macro_pegar and slot.macro_pegar.strip():
            return slot.macro_pegar.strip()

        return gerar_template_pegar_padrao(
            slot.id, slot.nome, slot.x_pegar, slot.y_pegar, slot.z_pegar, slot.z_seguro, slot.velocidade
        )

    def gerar_gcode_soltar_caneta(self, id_caneta: int) -> str:
        """
        Gera o script G-code para devolução de uma caneta específica na baia.

        Args:
            id_caneta (int): Número da caneta a devolver (1 a 10).

        Returns:
            str: Bloco de comandos G-code de descarte.
        """
        slot = self._canetas.get(id_caneta)
        if not slot:
            return ""

        if slot.macro_soltar and slot.macro_soltar.strip():
            return slot.macro_soltar.strip()

        return gerar_template_soltar_padrao(
            slot.id, slot.nome, slot.x_soltar, slot.y_soltar, slot.z_soltar, slot.z_seguro, slot.velocidade
        )

    def gerar_gcode_troca_completa(self, novo_id_caneta: int) -> str:
        """
        Gera a sequência G-code completa de troca (devolver a atual se houver + pegar a nova).

        Args:
            novo_id_caneta (int): Número da nova caneta a ser engatada.

        Returns:
            str: Sequência completa de instruções G-code encadeadas.
        """
        if self._caneta_ativa_id == novo_id_caneta:
            return f"; Caneta {novo_id_caneta} já está ativa no cabeçote."

        bloco_gcode = []

        # Passo 1: Devolver caneta atual caso exista
        if self._caneta_ativa_id is not None and self._caneta_ativa_id > 0:
            bloco_gcode.append(self.gerar_gcode_soltar_caneta(self._caneta_ativa_id))
            bloco_gcode.append("G4 P0.2")

        # Passo 2: Pegar nova caneta
        bloco_gcode.append(self.gerar_gcode_pegar_caneta(novo_id_caneta))

        return "\n\n".join(bloco_gcode)

    # ------------------------------------------------------------------ #
    #                       PERSISTÊNCIA JSON                            #
    # ------------------------------------------------------------------ #

    def _carregar_configuracao(self) -> None:
        """
        Carrega as configurações das canetas a partir do arquivo JSON ou popula com valores de fábrica.
        """
        if os.path.exists(self._caminho_config):
            try:
                with open(self._caminho_config, "r", encoding="utf-8") as arquivo_config:
                    dados = json.load(arquivo_config)
                    for item in dados:
                        slot = SlotCaneta(**item)
                        # Garante macros preenchidas
                        if not slot.macro_pegar:
                            slot.macro_pegar = gerar_template_pegar_padrao(
                                slot.id, slot.nome, slot.x_pegar, slot.y_pegar, slot.z_pegar, slot.z_seguro, slot.velocidade
                            )
                        if not slot.macro_soltar:
                            slot.macro_soltar = gerar_template_soltar_padrao(
                                slot.id, slot.nome, slot.x_soltar, slot.y_soltar, slot.z_soltar, slot.z_seguro, slot.velocidade
                            )
                        self._canetas[slot.id] = slot
                return
            except Exception:
                pass

        for item in CANETAS_PADRAO:
            slot = SlotCaneta(**item)
            slot.macro_pegar = gerar_template_pegar_padrao(
                slot.id, slot.nome, slot.x_pegar, slot.y_pegar, slot.z_pegar, slot.z_seguro, slot.velocidade
            )
            slot.macro_soltar = gerar_template_soltar_padrao(
                slot.id, slot.nome, slot.x_soltar, slot.y_soltar, slot.z_soltar, slot.z_seguro, slot.velocidade
            )
            self._canetas[slot.id] = slot
        self._salvar_configuracao()

    def _salvar_configuracao(self) -> None:
        """
        Persiste os dados de todas as 10 canetas no arquivo JSON.
        """
        try:
            pasta = os.path.dirname(self._caminho_config)
            if pasta and not os.path.exists(pasta):
                os.makedirs(pasta, exist_ok=True)

            dados = [asdict(self._canetas[i]) for i in sorted(self._canetas.keys())]
            with open(self._caminho_config, "w", encoding="utf-8") as arquivo_config:
                json.dump(dados, arquivo_config, indent=2, ensure_ascii=False)
        except OSError:
            pass

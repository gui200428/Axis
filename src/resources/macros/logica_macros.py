"""
Módulo de lógica para gerenciamento e execução de macros da plotter AXIS.

Permite registrar, editar, salvar e disparar rotinas G-code automatizadas
(como homing seguro, rotinas de limpeza, teste de cores, estacionamento, etc.).
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Signal

from resources.controle_da_maquina.logica_controle_da_maquina import ControladorGrbl


@dataclass
class MacroGcode:
    """
    Representa uma macro com identificador, nome, descrição,
    comando de acionamento no G-code (estilo Klipper) e código G-code.
    """
    id: str
    nome: str
    descricao: str
    gcode: str
    categoria: str = "Geral"
    comando_gcode: str = ""


MACROS_PADRAO: List[Dict] = [
    {
        "id": "homing_seguro",
        "nome": "🏠 Homing Seguro",
        "descricao": "Eleva o eixo Z e executa o ciclo de homing completo em todos os eixos.",
        "categoria": "Sistema",
        "comando_gcode": "HOME",
        "gcode": (
            "; === HOMING SEGURO ===\n"
            "G90 ; Coordenadas absolutas\n"
            "G21 ; Milímetros\n"
            "$H ; Ciclo de Homing GRBL\n"
            "G10 L20 P1 X0 Y0 Z0 ; Definir origem\n"
            "G0 Z15 F2000 ; Elevar Z seguro\n"
        )
    },
    {
        "id": "park_plotter",
        "nome": "🅿️ Estacionar Plotter",
        "descricao": "Eleva a caneta e move o cabeçote para o canto seguro de espera.",
        "categoria": "Movimento",
        "comando_gcode": "PARK",
        "gcode": (
            "; === ESTACIONAR MÁQUINA ===\n"
            "G90\n"
            "G0 Z20 F2000 ; Subir Z\n"
            "G0 X0 Y200 F4000 ; Mover para o fundo\n"
        )
    },
    {
        "id": "ponto_troca",
        "nome": "🔄 Ponto de Troca Rápida",
        "descricao": "Move o cabeçote para o centro da área de troca de canetas.",
        "categoria": "Canetas",
        "comando_gcode": "PONTO_TROCA",
        "gcode": (
            "; === PONTO DE TROCA ===\n"
            "G90\n"
            "G0 Z15 F2500\n"
            "G0 X150 Y180 F3500\n"
        )
    },
    {
        "id": "limpar_caneta",
        "nome": "🧹 Limpeza / Rabisco",
        "descricao": "Executa pequenos círculos de teste para desentupir e testar o fluxo da tinta.",
        "categoria": "Canetas",
        "comando_gcode": "LIMPAR_CANETA",
        "gcode": (
            "; === TESTE DE FLUXO / LIMPEZA ===\n"
            "G91 ; Coordenadas relativas\n"
            "G1 Z-5 F500 ; Baixar caneta\n"
            "G2 X10 Y0 I5 J0 F1500 ; Círculo 1\n"
            "G2 X-10 Y0 I-5 J0 F1500 ; Círculo 2\n"
            "G0 Z5 F2000 ; Levantar caneta\n"
            "G90 ; Voltar para absolutas\n"
        )
    },
    {
        "id": "teste_10_cores",
        "nome": "🎨 Teste das 10 Cores",
        "descricao": "Gera um traço reto de demonstração de 50mm para testar a caneta atual.",
        "categoria": "Canetas",
        "comando_gcode": "TESTE_10_CORES",
        "gcode": (
            "; === TRAÇO DE TESTE DA CANETA ===\n"
            "G90\n"
            "G0 Z5 F2000\n"
            "G0 X50 Y50 F3000\n"
            "G1 Z0 F800 ; Caneta no papel\n"
            "G1 X100 Y50 F1200 ; Traço de 50mm\n"
            "G0 Z5 F2000 ; Levantar caneta\n"
        )
    },
    {
        "id": "pen_down",
        "nome": "⬇ Abaixar Caneta",
        "descricao": "Abaixa a caneta ativa suavemente até a altura de contato com auto-nivelamento compensado.",
        "categoria": "Canetas",
        "comando_gcode": "PEN_DOWN",
        "gcode": (
            "; === ABAIXAR CANETA (PEN DOWN) ===\n"
            "PEN_DOWN\n"
        )
    },
    {
        "id": "pen_up",
        "nome": "⬆ Levantar Caneta",
        "descricao": "Eleva a caneta ativa para a altura segura de ar (Z-Up).",
        "categoria": "Canetas",
        "comando_gcode": "PEN_UP",
        "gcode": (
            "; === LEVANTAR CANETA (PEN UP) ===\n"
            "PEN_UP\n"
        )
    },
    {
        "id": "pen_hop",
        "nome": "⇪ Salto / Hop Caneta",
        "descricao": "Eleva a caneta apenas 2mm (PEN_HOP) para troca rápida de traço na escrita sem subir o caminho todo.",
        "categoria": "Canetas",
        "comando_gcode": "PEN_HOP",
        "gcode": (
            "; === SALTO INTERMEDIÁRIO DA CANETA (PEN HOP) ===\n"
            "PEN_HOP\n"
        )
    },
    {
        "id": "teste_nivelamento",
        "nome": "🎯 Teste de Nivelamento",
        "descricao": "Executa um traço diagonal de ponta a ponta para validar a oscilação do Z e o auto-nivelamento.",
        "categoria": "Canetas",
        "comando_gcode": "TESTE_NIVELAMENTO",
        "gcode": (
            "; === TESTE DE AUTO-NIVELAMENTO DA MESA ===\n"
            "G90 ; Coordenadas absolutas\n"
            "G21 ; Milímetros\n"
            "PEN_UP\n"
            "G0 X50 Y50 F3000 ; Início da área de desenho\n"
            "PEN_DOWN ; Abaixa com compensação da malha\n"
            "G1 X220 Y220 F1500 ; Traço diagonal cruzando a mesa\n"
            "PEN_UP ; Eleva com segurança\n"
            "G0 X50 Y50 F3500 ; Retorna ao ponto de partida\n"
        )
    },
    {
        "id": "elevar_z",
        "nome": "⬆️ Elevar Eixo Z (+15mm)",
        "descricao": "Eleva a caneta imediatamente em 15mm para segurança.",
        "categoria": "Movimento",
        "comando_gcode": "ELEVAR_Z",
        "gcode": (
            "G91\n"
            "G0 Z15 F2000\n"
            "G90\n"
        )
    }
]


class GerenciadorMacros(QObject):
    """
    Gerencia a biblioteca de macros do usuário e sua execução.
    """

    sinal_macros_atualizadas = Signal()
    sinal_macro_executada = Signal(str)

    def __init__(self, caminho_config: Optional[str] = None) -> None:
        """
        Inicializa o gerenciador carregando macros salvas.

        Args:
            caminho_config (str, optional): Caminho para o arquivo JSON de macros.
        """
        super().__init__()
        self._caminho_config = caminho_config or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "macros_usuario.json"
        )
        self._macros: Dict[str, MacroGcode] = {}
        self._carregar_macros()

    def obter_todas_macros(self) -> List[MacroGcode]:
        """
        Retorna lista de todas as macros cadastradas.

        Returns:
            List[MacroGcode]: Lista de todas as instâncias de MacroGcode.
        """
        return list(self._macros.values())

    def obter_macro(self, id_macro: str) -> Optional[MacroGcode]:
        """
        Retorna os dados de uma macro pelo ID.

        Args:
            id_macro (str): Identificador único da macro.

        Returns:
            Optional[MacroGcode]: Objeto MacroGcode ou None caso não exista.
        """
        return self._macros.get(id_macro)

    def salvar_ou_atualizar_macro(self, macro: MacroGcode) -> None:
        """
        Adiciona ou atualiza uma macro e salva no disco.

        Args:
            macro (MacroGcode): Objeto da macro a ser gravado.
        """
        self._macros[macro.id] = macro
        self._salvar_macros()
        self.sinal_macros_atualizadas.emit()

    def remover_macro(self, id_macro: str) -> bool:
        """
        Remove uma macro pelo ID.

        Args:
            id_macro (str): Identificador único da macro a ser excluída.

        Returns:
            bool: True se a macro existia e foi removida, False caso contrário.
        """
        if id_macro in self._macros:
            del self._macros[id_macro]
            self._salvar_macros()
            self.sinal_macros_atualizadas.emit()
            return True
        return False

    def executar_macro(
        self,
        id_macro: str,
        controlador_grbl: ControladorGrbl,
        callback_conclusao: Optional[callable] = None
    ) -> bool:
        """
        Envia o código G-code da macro para o controlador GRBL conectado
        utilizando transmissão gerenciada com controle de fluxo e sincronização.

        Args:
            id_macro (str): Identificador da macro.
            controlador_grbl (ControladorGrbl): Controlador ativo.
            callback_conclusao (callable, optional): Callback disparado após conclusão física.

        Returns:
            bool: True se iniciou com sucesso.
        """
        macro = self._macros.get(id_macro)
        if not macro:
            return False

        if not controlador_grbl.esta_conectado():
            return False

        def _ao_concluir() -> None:
            self.sinal_macro_executada.emit(macro.nome)
            if callback_conclusao:
                callback_conclusao()

        return controlador_grbl.enviar_script_gcode(
            macro.gcode,
            nome=f"Macro '{macro.nome}'",
            callback_conclusao=_ao_concluir
        )

    def expandir_macros_em_gcode(self, conteudo: str) -> str:
        """
        Expande referências a macros dentro do conteúdo G-code (estilo Klipper).

        Percorre cada linha do G-code. Se a linha corresponder ao comando de disparo
        (comando_gcode) ou ao ID de uma macro registrada, substitui a linha pelo G-code
        completo da macro. Apenas 1 nível de expansão (sem recursão).

        Args:
            conteudo (str): Conteúdo G-code original com possíveis referências a macros.

        Returns:
            str: Conteúdo G-code com macros expandidas.
        """
        if not conteudo.strip():
            return conteudo

        # Monta lookup normalizado: mapeia comando_gcode e id para (nome_macro, gcode)
        lookup: Dict[str, tuple[str, str]] = {}
        for macro in self._macros.values():
            if macro.comando_gcode and macro.comando_gcode.strip():
                chave_cmd = macro.comando_gcode.strip().upper().replace(" ", "_")
                lookup[chave_cmd] = (macro.nome, macro.gcode)
            chave_id = macro.id.strip().upper().replace(" ", "_")
            lookup[chave_id] = (macro.nome, macro.gcode)

        linhas_resultado = []
        for linha in conteudo.splitlines():
            linha_limpa = linha.strip()

            # Ignorar linhas vazias e comentários puros
            if not linha_limpa or linha_limpa.startswith(";"):
                linhas_resultado.append(linha)
                continue

            # Extrair parte antes de comentário inline (ex: "HOME ; vai para origem")
            parte_comando = linha_limpa.split(";")[0].strip()
            chave_normalizada = parte_comando.upper().replace(" ", "_")

            if chave_normalizada in lookup:
                nome_macro, gcode_macro = lookup[chave_normalizada]
                linhas_resultado.append(f"; >>> MACRO: {parte_comando} ({nome_macro}) <<<")
                linhas_resultado.append(gcode_macro)
                linhas_resultado.append(f"; >>> FIM MACRO: {parte_comando} <<<")
            else:
                linhas_resultado.append(linha)

        return "\n".join(linhas_resultado)

    def obter_nomes_macros_disponiveis(self) -> List[str]:
        """
        Retorna a lista de comandos/IDs de macros disponíveis para uso no editor G-code.

        Returns:
            List[str]: Lista de identificadores das macros registradas.
        """
        comandos = []
        for macro in self._macros.values():
            if macro.comando_gcode:
                comandos.append(macro.comando_gcode)
            else:
                comandos.append(macro.id.upper())
        return comandos

    def _carregar_macros(self) -> None:
        """
        Carrega macros do JSON ou popula com os modelos padrão.
        """
        if os.path.exists(self._caminho_config):
            try:
                with open(self._caminho_config, "r", encoding="utf-8") as arquivo_config:
                    dados = json.load(arquivo_config)
                    for item in dados:
                        if not item.get("comando_gcode"):
                            item["comando_gcode"] = item.get("id", "").upper().replace("-", "_")
                        macro = MacroGcode(**item)
                        self._macros[macro.id] = macro
                # Mesclar novas macros padrão essenciais caso não existam no JSON do usuário
                precisa_salvar = False
                for item in MACROS_PADRAO:
                    if item["id"] not in self._macros:
                        macro = MacroGcode(**item)
                        self._macros[macro.id] = macro
                        precisa_salvar = True
                if precisa_salvar:
                    self._salvar_macros()
                return
            except Exception:
                pass

        for item in MACROS_PADRAO:
            macro = MacroGcode(**item)
            self._macros[macro.id] = macro
        self._salvar_macros()

    def _salvar_macros(self) -> None:
        """
        Persiste as macros no disco em formato JSON.
        """
        try:
            pasta = os.path.dirname(self._caminho_config)
            if pasta and not os.path.exists(pasta):
                os.makedirs(pasta, exist_ok=True)

            dados = [asdict(macro) for macro in self._macros.values()]
            with open(self._caminho_config, "w", encoding="utf-8") as arquivo_config:
                json.dump(dados, arquivo_config, indent=2, ensure_ascii=False)
        except OSError:
            pass

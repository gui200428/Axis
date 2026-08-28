"""
Módulo de gerenciamento de nivelamento por software (Mesh Bed Leveling)
e calibração de Z-offset para as 10 canetas da plotter AXIS.

Permite gerar uma malha de pontos configurável dentro da área de desenho,
calibrar o ponto de Z para cada caneta e aplicar compensação de altura
dinâmica via interpolação bilinear 2D no fluxo de comandos G-code.
"""

import json
import math
import os
import re
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Any
from PySide6.QtCore import QObject, Signal

from resources.controle_da_maquina.gerenciador_area_desenho import (
    GerenciadorAreaDesenho, ConfiguracaoAreaDesenho
)
from resources.controle_da_maquina.gerenciador_canetas import GerenciadorCanetas


@dataclass
class PontoMalha:
    """Representa um ponto individual na malha de calibração."""
    linha: int        # Índice da linha horizontal (0..num_linhas-1)
    coluna: int       # Índice do ponto na linha (0..num_pontos_por_linha-1)
    x: float          # Coordenada X em mm
    y: float          # Coordenada Y em mm
    z: float = 0.0    # Altura Z calibrada (ponto) em mm
    calibrado: bool = False


@dataclass
class MalhaCaneta:
    """Representa a configuração e grade de calibração de uma caneta específica."""
    id_caneta: int
    nome: str
    cor_hex: str
    num_linhas: int = 4
    num_pontos_por_linha: int = 4
    pontos: List[PontoMalha] = field(default_factory=list)
    calibrado: bool = False
    distancia_teste_traco: float = 10.0  # Comprimento do traço de teste X+ (mm)
    feed_teste_traco: int = 1000         # Velocidade do traço de teste (mm/min)
    z_up: float = -4.0                   # Altura Z Levantada (Trânsito Seguro no Ar) em mm
    z_down: float = 25.0                 # Altura Z Abaixada (Contato/Desenho Nominal) em mm
    z_seguro: float = -4.0               # Compatibilidade com z_up


@dataclass
class ConfiguracaoNivelamento:
    """Configuração global de nivelamento."""
    nivelamento_ativo: bool = True
    canetas: Dict[int, MalhaCaneta] = field(default_factory=dict)


# Distância padrão conservadora de elevação para o comando PEN_HOP (Z-Hop de escrita)
DISTANCIA_PEN_HOP_PADRAO: float = 2.0


class GerenciadorNivelamento(QObject):
    """
    Controlador centralizado do sistema de nivelamento e compensação de Z-offset.
    """

    sinal_nivelamento_atualizado = Signal()
    sinal_ponto_calibrado = Signal(int, int, int, float)  # (id_caneta, linha, coluna, z)
    sinal_status_compensacao_alterado = Signal(bool)

    def __init__(
        self,
        gerenciador_area: Optional[GerenciadorAreaDesenho] = None,
        gerenciador_canetas: Optional[GerenciadorCanetas] = None,
        caminho_arquivo_config: Optional[str] = None
    ) -> None:
        super().__init__()
        self._gerenciador_area = gerenciador_area
        self._gerenciador_canetas = gerenciador_canetas
        self._caminho_config = caminho_arquivo_config or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "nivelamento_canetas.json"
        )
        self._config = ConfiguracaoNivelamento()
        self._carregar_configuracao()

        # Conectar sinal da área de desenho para atualizar automaticamente as coordenadas XY
        if self._gerenciador_area is not None:
            self._gerenciador_area.sinal_area_alterada.connect(self._ao_alterar_area_desenho)

        # Conectar sinal de canetas para manter nomes e cores sincronizados
        if self._gerenciador_canetas is not None:
            self._gerenciador_canetas.sinal_slots_atualizados.connect(self._sincronizar_dados_canetas)

    # ------------------------------------------------------------------ #
    #                         ACESSO E CONSULTAS                         #
    # ------------------------------------------------------------------ #

    def esta_nivelamento_ativo(self) -> bool:
        """
        Retorna se o nivelamento por software está ativado.

        Returns:
            bool: True se ativo, False caso contrário.
        """
        return self._config.nivelamento_ativo

    def definir_nivelamento_ativo(self, ativo: bool) -> None:
        """
        Ativa ou desativa a compensação dinâmica de nivelamento.

        Args:
            ativo (bool): True para ativar compensação, False para desativar.
        """
        if self._config.nivelamento_ativo != ativo:
            self._config.nivelamento_ativo = ativo
            self._salvar_configuracao()
            self.sinal_status_compensacao_alterado.emit(ativo)
            self.sinal_nivelamento_atualizado.emit()

    def obter_malha_caneta(self, id_caneta: int) -> Optional[MalhaCaneta]:
        """
        Retorna a malha de calibração para a caneta solicitada (1..10).

        Args:
            id_caneta (int): Identificador da caneta (1 a 10).

        Returns:
            Optional[MalhaCaneta]: Objeto da malha de calibração ou None.
        """
        return self._config.canetas.get(id_caneta)

    def obter_todas_malhas(self) -> Dict[int, MalhaCaneta]:
        """
        Retorna o dicionário de todas as 10 malhas de caneta.

        Returns:
            Dict[int, MalhaCaneta]: Mapeamento de id_caneta para MalhaCaneta.
        """
        return self._config.canetas

    # ------------------------------------------------------------------ #
    #                     GERAÇÃO E AJUSTE DA MALHA                      #
    # ------------------------------------------------------------------ #

    def obter_limites_area(self) -> Tuple[float, float, float, float]:
        """
        Retorna as coordenadas delimitadoras da área de desenho.

        Returns:
            Tuple[float, float, float, float]: (x_inicio, y_inicio, x_fim, y_fim) em mm.
        """
        if self._gerenciador_area is not None:
            cfg = self._gerenciador_area.obter_configuracao()
            return cfg.x_inicio, cfg.y_inicio, cfg.x_fim, cfg.y_fim
        return 40.0, 40.0, 250.0, 250.0

    def redimensionar_malha_caneta(
        self,
        id_caneta: int,
        num_linhas: int,
        num_pontos_por_linha: int,
        manter_valores_z: bool = True
    ) -> None:
        """
        Gera uma nova grade com a quantidade de linhas e pontos especificada,
        distribuindo-os uniformemente na área de desenho.

        Args:
            id_caneta (int): Identificador da caneta (1 a 10).
            num_linhas (int): Quantidade de linhas na grade (Y).
            num_pontos_por_linha (int): Quantidade de pontos por linha (X).
            manter_valores_z (bool): Se True, interpola valores Z previamente calibrados.
        """
        num_linhas = max(2, min(30, int(num_linhas)))
        num_pontos_por_linha = max(2, min(30, int(num_pontos_por_linha)))

        malha_existente = self._config.canetas.get(id_caneta)
        nome = malha_existente.nome if malha_existente else f"Caneta {id_caneta}"
        cor = malha_existente.cor_hex if malha_existente else "#5b7fff"
        dist_traco = malha_existente.distancia_teste_traco if malha_existente else 10.0
        feed_traco = malha_existente.feed_teste_traco if malha_existente else 1000
        z_up = malha_existente.z_up if malha_existente else -4.0
        z_down = malha_existente.z_down if malha_existente else 25.0
        z_seguro = malha_existente.z_seguro if malha_existente else z_up

        x_ini, y_ini, x_fim, y_fim = self.obter_limites_area()

        novos_pontos: List[PontoMalha] = []
        for i in range(num_linhas):
            # Interpolação de Y para a linha i (de baixo para cima: y_ini -> y_fim)
            if num_linhas > 1:
                y_val = y_ini + (i / (num_linhas - 1)) * (y_fim - y_ini)
            else:
                y_val = (y_ini + y_fim) / 2.0

            for j in range(num_pontos_por_linha):
                # Interpolação de X para o ponto j da linha
                if num_pontos_por_linha > 1:
                    x_val = x_ini + (j / (num_pontos_por_linha - 1)) * (x_fim - x_ini)
                else:
                    x_val = (x_ini + x_fim) / 2.0

                z_val = z_down
                calibrado = False
                if manter_valores_z and malha_existente and malha_existente.pontos:
                    # Tenta interpolar ou manter valor existente
                    z_val = self._interpolar_ponto_existente(malha_existente, x_val, y_val)
                    calibrado = malha_existente.calibrado

                novos_pontos.append(PontoMalha(
                    linha=i,
                    coluna=j,
                    x=round(x_val, 3),
                    y=round(y_val, 3),
                    z=round(z_val, 3),
                    calibrado=calibrado
                ))

        todos_calibrados = all(p.calibrado for p in novos_pontos) if novos_pontos else False

        self._config.canetas[id_caneta] = MalhaCaneta(
            id_caneta=id_caneta,
            nome=nome,
            cor_hex=cor,
            num_linhas=num_linhas,
            num_pontos_por_linha=num_pontos_por_linha,
            pontos=novos_pontos,
            calibrado=todos_calibrados,
            distancia_teste_traco=dist_traco,
            feed_teste_traco=feed_traco,
            z_up=z_up,
            z_down=z_down,
            z_seguro=z_seguro
        )
        self._salvar_configuracao()
        self.sinal_nivelamento_atualizado.emit()

    def definir_ponto_z(
        self,
        id_caneta: int,
        linha: int,
        coluna: int,
        z_valor: float
    ) -> None:
        """
        Salva a calibração de Z (ponto) para um nó específico da malha.

        Args:
            id_caneta (int): Identificador da caneta (1 a 10).
            linha (int): Índice da linha horizontal.
            coluna (int): Índice da coluna do ponto.
            z_valor (float): Altura Z calibrada em mm.
        """
        malha = self._config.canetas.get(id_caneta)
        if not malha:
            return

        for p in malha.pontos:
            if p.linha == linha and p.coluna == coluna:
                p.z = round(float(z_valor), 3)
                p.calibrado = True
                break

        malha.calibrado = all(p.calibrado for p in malha.pontos)
        self._salvar_configuracao()
        self.sinal_ponto_calibrado.emit(id_caneta, linha, coluna, float(z_valor))
        self.sinal_nivelamento_atualizado.emit()

    def resetar_calibracao_caneta(self, id_caneta: int) -> None:
        """
        Reseta todos os pontos Z da caneta para o z_down base e desmarca calibrado.

        Args:
            id_caneta (int): Identificador da caneta (1 a 10).
        """
        malha = self._config.canetas.get(id_caneta)
        if malha:
            for p in malha.pontos:
                p.z = malha.z_down
                p.calibrado = False
            malha.calibrado = False
            self._salvar_configuracao()
            self.sinal_nivelamento_atualizado.emit()

    def definir_z_up_down(self, id_caneta: int, z_up: float, z_down: float) -> None:
        """
        Define os limites funcionais de Z-Up (seguro/ar) e Z-Down (contato base) para a caneta.

        Args:
            id_caneta (int): Identificador da caneta (1 a 10).
            z_up (float): Altura Z no ar (trânsito seguro) em mm.
            z_down (float): Altura Z de contato nominal em mm.
        """
        malha = self._config.canetas.get(id_caneta)
        if malha:
            malha.z_up = round(float(z_up), 3)
            malha.z_down = round(float(z_down), 3)
            malha.z_seguro = malha.z_up

            # Sincronizar com GerenciadorCanetas se disponível
            if self._gerenciador_canetas:
                slot = self._gerenciador_canetas.obter_slot(id_caneta)
                if slot:
                    slot.z_up = malha.z_up
                    slot.z_down = malha.z_down
                    slot.z_seguro = malha.z_up
                    self._gerenciador_canetas.atualizar_slot(slot)

            self._salvar_configuracao()
            self.sinal_nivelamento_atualizado.emit()

    def definir_parametros_traco(self, id_caneta: int, distancia: float, feed: int) -> None:
        """Define e salva o comprimento e velocidade (feed rate) do traço de teste para a caneta."""
        malha = self._config.canetas.get(id_caneta)
        if malha:
            malha.distancia_teste_traco = round(float(distancia), 2)
            malha.feed_teste_traco = int(feed)
            self._salvar_configuracao()

    def copiar_z_up_down_para_todas(self, id_caneta_origem: int) -> None:
        """Copia os limites de Z-Up e Z-Down da caneta de origem para todas as 10 canetas."""
        origem = self._config.canetas.get(id_caneta_origem)
        if not origem:
            return

        for id_dest, malha in self._config.canetas.items():
            malha.z_up = origem.z_up
            malha.z_down = origem.z_down
            malha.z_seguro = origem.z_up

            if self._gerenciador_canetas:
                slot = self._gerenciador_canetas.obter_slot(id_dest)
                if slot:
                    slot.z_up = origem.z_up
                    slot.z_down = origem.z_down
                    slot.z_seguro = origem.z_up
                    self._gerenciador_canetas.atualizar_slot(slot)

        self._salvar_configuracao()
        self.sinal_nivelamento_atualizado.emit()

    def copiar_malha_para_todas_canetas(self, id_caneta_origem: int) -> None:
        """Copia a malha e os valores calibrados da caneta de origem para todas as outras 9 canetas."""
        origem = self._config.canetas.get(id_caneta_origem)
        if not origem:
            return

        for id_destino, malha_dest in self._config.canetas.items():
            if id_destino == id_caneta_origem:
                continue

            novos_pontos = [
                PontoMalha(
                    linha=p.linha,
                    coluna=p.coluna,
                    x=p.x,
                    y=p.y,
                    z=p.z,
                    calibrado=p.calibrado
                )
                for p in origem.pontos
            ]

            malha_dest.num_linhas = origem.num_linhas
            malha_dest.num_pontos_por_linha = origem.num_pontos_por_linha
            malha_dest.distancia_teste_traco = origem.distancia_teste_traco
            malha_dest.feed_teste_traco = origem.feed_teste_traco
            malha_dest.z_up = origem.z_up
            malha_dest.z_down = origem.z_down
            malha_dest.z_seguro = origem.z_up

        self._salvar_configuracao()
        self.sinal_nivelamento_atualizado.emit()

    # ------------------------------------------------------------------ #
    #                   INTERPOLAÇÃO BILINEAR 2D DE Z                    #
    # ------------------------------------------------------------------ #

    def calcular_z_interpolado(self, id_caneta: int, x: float, y: float) -> float:
        """
        Calcula o Z-offset compensado para uma coordenada (x, y) arbitrária
        através de interpolação bilinear na malha calibrada da caneta.
        """
        malha = self._config.canetas.get(id_caneta)
        if not malha or not malha.pontos:
            return 0.0

        return self._interpolar_ponto_existente(malha, x, y)

    def _interpolar_ponto_existente(self, malha: MalhaCaneta, x: float, y: float) -> float:
        """Executa a interpolação bilinear robusta em uma malha retangular estruturada."""
        R = malha.num_linhas
        C = malha.num_pontos_por_linha
        if R < 1 or C < 1 or len(malha.pontos) != R * C:
            if malha.pontos:
                # Média simples caso formato inconsistente
                return sum(p.z for p in malha.pontos) / len(malha.pontos)
            return 0.0

        # Montar matriz de pontos [linha][coluna]
        matriz: List[List[PontoMalha]] = [[None for _ in range(C)] for _ in range(R)]
        for p in malha.pontos:
            if 0 <= p.linha < R and 0 <= p.coluna < C:
                matriz[p.linha][p.coluna] = p

        # Verificar integridade
        for r in range(R):
            for c in range(C):
                if matriz[r][c] is None:
                    return 0.0

        # Caso 1x1
        if R == 1 and C == 1:
            return matriz[0][0].z

        # Vetores de coordenadas das linhas (Y) e colunas (X)
        vet_y = [matriz[r][0].y for r in range(R)]
        vet_x = [matriz[0][c].x for c in range(C)]

        # Caso linha única (R == 1): interpolação linear em X
        if R == 1:
            return self._interpolar_linear_1d(vet_x, [matriz[0][c].z for c in range(C)], x)

        # Caso coluna única (C == 1): interpolação linear em Y
        if C == 1:
            return self._interpolar_linear_1d(vet_y, [matriz[r][0].z for r in range(R)], y)

        # Localizar célula (i, i+1) em Y
        i = 0
        while i < R - 2 and y > vet_y[i + 1]:
            i += 1

        # Localizar célula (j, j+1) em X
        j = 0
        while j < C - 2 and x > vet_x[j + 1]:
            j += 1

        x0, x1 = vet_x[j], vet_x[j + 1]
        y0, y1 = vet_y[i], vet_y[i + 1]

        # Fatores normalizados u e v com clamp para estabilidade nas bordas
        dx = x1 - x0
        dy = y1 - y0
        u = (x - x0) / dx if abs(dx) > 1e-6 else 0.0
        v = (y - y0) / dy if abs(dy) > 1e-6 else 0.0

        u = max(0.0, min(1.0, u))
        v = max(0.0, min(1.0, v))

        z00 = matriz[i][j].z
        z01 = matriz[i][j + 1].z
        z10 = matriz[i + 1][j].z
        z11 = matriz[i + 1][j + 1].z

        z_interp = (
            (1.0 - u) * (1.0 - v) * z00 +
            u * (1.0 - v) * z01 +
            (1.0 - u) * v * z10 +
            u * v * z11
        )
        return z_interp

    @staticmethod
    def _interpolar_linear_1d(vet_coords: List[float], vet_valores: List[float], val: float) -> float:
        """Interpolação linear unidimensional com clamping nas extremidades."""
        n = len(vet_coords)
        if n == 0:
            return 0.0
        if n == 1:
            return vet_valores[0]

        idx = 0
        while idx < n - 2 and val > vet_coords[idx + 1]:
            idx += 1

        c0, c1 = vet_coords[idx], vet_coords[idx + 1]
        v0, v1 = vet_valores[idx], vet_valores[idx + 1]

        dc = c1 - c0
        if abs(dc) < 1e-6:
            return v0

        t = max(0.0, min(1.0, (val - c0) / dc))
        return (1.0 - t) * v0 + t * v1

    def esta_dentro_area(self, x: float, y: float, margem: float = 0.05) -> bool:
        """Verifica se a coordenada (x, y) está dentro dos limites da área de desenho."""
        x_ini, y_ini, x_fim, y_fim = self.obter_limites_area()
        x_min, x_max = min(x_ini, x_fim), max(x_ini, x_fim)
        y_min, y_max = min(y_ini, y_fim), max(y_ini, y_fim)
        return (x_min - margem) <= x <= (x_max + margem) and (y_min - margem) <= y <= (y_max + margem)

    def obter_z_up_down(self, id_caneta: Optional[int] = None) -> Tuple[float, float]:
        """Retorna (z_up, z_down) para a caneta solicitada (ou caneta 1 por padrão)."""
        cid = id_caneta if (id_caneta is not None and id_caneta > 0) else 1
        malha = self._config.canetas.get(cid)
        if malha:
            return malha.z_up, malha.z_down
        # Fallback para caneta 1 se existir
        m1 = self._config.canetas.get(1)
        if m1:
            return m1.z_up, m1.z_down
        return -4.0, 25.0

    def calcular_z_compensado_ponto(self, id_caneta: Optional[int], x: float, y: float) -> float:
        """Calcula a altura Z compensada para a caneta informada na posição (x, y)."""
        cid = id_caneta if (id_caneta is not None and id_caneta > 0) else 1
        if self.esta_nivelamento_ativo() and self.esta_dentro_area(x, y):
            return self.calcular_z_interpolado(cid, x, y)
        z_up, z_down = self.obter_z_up_down(cid)
        return z_down

    def calcular_z_hop_ponto(
        self,
        id_caneta: Optional[int],
        x: float,
        y: float,
        dist_hop: float = DISTANCIA_PEN_HOP_PADRAO
    ) -> float:
        """
        Calcula a altura de salto intermediário Z (PEN_HOP) para a posição (x, y) informada,
        elevando a caneta uma distância reduzida (padrão 2.0mm) em relação à superfície de contato.
        """
        cid = id_caneta if (id_caneta is not None and id_caneta > 0) else 1
        z_up, z_down = self.obter_z_up_down(cid)
        if self.esta_nivelamento_ativo() and self.esta_dentro_area(x, y):
            z_comp = self.calcular_z_interpolado(cid, x, y)
        else:
            z_comp = z_down

        if z_down >= z_up:
            return max(z_up, z_comp - dist_hop)
        else:
            return min(z_up, z_comp + dist_hop)

    # ------------------------------------------------------------------ #
    #              TRANSFORMAÇÃO INTELIGENTE DE G-CODE                   #
    # ------------------------------------------------------------------ #

    def aplicar_nivelamento_gcode(
        self,
        conteudo_gcode: str,
        id_caneta_padrao: int = 1,
        max_comprimento_segmento: float = 5.0
    ) -> str:
        """
        Processa o script G-code e aplica a compensação de nivelamento Z
        baseada na malha da caneta ativa. Subdivide traços longos em pequenos
        segmentos para garantir que a caneta siga o contorno da mesa fielmente.

        Também expande dinamicamente os comandos universais PEN_DOWN e PEN_UP
        e aplica proteção de limites de área de desenho (Auto-Lift Z).
        """
        linhas = conteudo_gcode.splitlines()
        linhas_resultado = []
        nivelamento_habilitado = self.esta_nivelamento_ativo()

        # Estado da máquina durante o parsing
        pos_x = 0.0
        pos_y = 0.0
        pos_z = 0.0
        caneta_ativa = id_caneta_padrao if id_caneta_padrao and id_caneta_padrao > 0 else 1
        absoluto = True  # G90
        em_bloco_protegido = False

        padrao_troca = re.compile(r"(?:TROCAR_CANETA_|PEGAR_CANETA_|TROCA_CANETA_|PEGA_CANETA_|T)(\d+)", re.IGNORECASE)

        modo_g_atual = None

        for linha in linhas:
            linha_limpa = linha.strip()
            if not linha_limpa:
                linhas_resultado.append(linha)
                continue

            # Preservar comentários inteiros e gerenciar blocos protegidos (troca de caneta/estojo)
            if linha_limpa.startswith(";") or linha_limpa.startswith("("):
                linha_upper = linha_limpa.upper()
                if any(k in linha_upper for k in (
                    "PEGAR CANETA", "GUARDAR CANETA", "SOLTAR CANETA", "TROCAR CANETA", "TROCA CANETA",
                    "SLOT", "TOOL CHANGE"
                )):
                    if "FIM" not in linha_upper:
                        em_bloco_protegido = True
                if any(k in linha_upper for k in (
                    "FIM DO ENGATE", "FIM DO DESENGATE", "FIM TROCA", "FIM PEGAR", "FIM SOLTAR", ">>> FIM"
                )):
                    em_bloco_protegido = False

                linhas_resultado.append(linha)
                continue

            # Se estamos em bloco de troca de ferramentas / hardware, não modificar comandos:
            if em_bloco_protegido:
                linhas_resultado.append(linha)
                parte_codigo = linha_limpa.split(";")[0].split("(")[0].strip()
                tokens = parte_codigo.upper().split()
                for tok in tokens:
                    if tok.startswith("X") and len(tok) > 1:
                        try:
                            pos_x = float(tok[1:])
                        except ValueError:
                            pass
                    elif tok.startswith("Y") and len(tok) > 1:
                        try:
                            pos_y = float(tok[1:])
                        except ValueError:
                            pass
                    elif tok.startswith("Z") and len(tok) > 1:
                        try:
                            pos_z = float(tok[1:])
                        except ValueError:
                            pass
                continue

            parte_codigo = linha_limpa.split(";")[0].split("(")[0].strip()
            tokens = parte_codigo.upper().split()

            # Ignorar comandos invasivos de impressora 3D ou homing no início/meio do desenho
            if any(t in tokens for t in ("G28", "M107", "M106")):
                linhas_resultado.append(f"; [IGNORADO AUTOMATICAMENTE] {linha}")
                continue

            # Detectar mudança de caneta
            match_troca = padrao_troca.search(parte_codigo)
            if match_troca:
                try:
                    caneta_ativa = int(match_troca.group(1))
                except ValueError:
                    pass

            # Detectar modo absoluto/relativo
            if "G90" in tokens:
                absoluto = True
            elif "G91" in tokens:
                absoluto = False

            # Obter z_up e z_down configurados para a caneta ativa
            z_up_atual, z_down_atual = self.obter_z_up_down(caneta_ativa)
            limiar_desenho = (z_up_atual + z_down_atual) / 2.0

            # --- Tratamento de PEN_DOWN ---
            if "PEN_DOWN" in tokens:
                if nivelamento_habilitado and self.esta_dentro_area(pos_x, pos_y):
                    z_comp = self.calcular_z_interpolado(caneta_ativa, pos_x, pos_y)
                    linhas_resultado.append(f"; >>> PEN_DOWN [Caneta {caneta_ativa}] <<<")
                    linhas_resultado.append(f"G1 Z{z_comp:.3f} F600")
                    pos_z = z_comp
                elif nivelamento_habilitado:
                    linhas_resultado.append(
                        f"; [SEGURANÇA] PEN_DOWN bloqueado fora da área de desenho ({pos_x:.1f}, {pos_y:.1f}). Z mantido em {z_up_atual:.2f}mm."
                    )
                    linhas_resultado.append(f"G0 Z{z_up_atual:.3f} F3000")
                    pos_z = z_up_atual
                else:
                    linhas_resultado.append(f"; >>> PEN_DOWN [Caneta {caneta_ativa}] <<<")
                    linhas_resultado.append(f"G1 Z{z_down_atual:.3f} F600")
                    pos_z = z_down_atual
                continue

            # --- Tratamento de PEN_HOP (Salto Intermediário / Escrita Rápida) ---
            if "PEN_HOP" in tokens:
                z_hop_pos = self.calcular_z_hop_ponto(caneta_ativa, pos_x, pos_y)
                linhas_resultado.append(f"; >>> PEN_HOP [Caneta {caneta_ativa}] <<<")
                linhas_resultado.append(f"G0 Z{z_hop_pos:.3f} F3000")
                pos_z = z_hop_pos
                continue

            # --- Tratamento de PEN_UP ---
            if "PEN_UP" in tokens:
                linhas_resultado.append(f"; >>> PEN_UP [Caneta {caneta_ativa}] <<<")
                linhas_resultado.append(f"G0 Z{z_up_atual:.3f} F3000")
                pos_z = z_up_atual
                continue

            # Se não estiver em coordenadas absolutas ou se nivelamento estiver desligado, mantemos comandos normais
            if not absoluto or not nivelamento_habilitado:
                linhas_resultado.append(linha)
                continue

            # Extrair coordenadas e parâmetros X, Y, Z, I, J, R, F
            alvo_x = pos_x
            alvo_y = pos_y
            alvo_z = pos_z
            i_val = None
            j_val = None
            r_val = None
            tem_x = False
            tem_y = False
            tem_z = False
            tem_i = False
            tem_j = False
            tem_r = False
            feed_rate_str = ""

            for tok in tokens:
                if tok.startswith("X") and len(tok) > 1:
                    try:
                        alvo_x = float(tok[1:])
                        tem_x = True
                    except ValueError:
                        pass
                elif tok.startswith("Y") and len(tok) > 1:
                    try:
                        alvo_y = float(tok[1:])
                        tem_y = True
                    except ValueError:
                        pass
                elif tok.startswith("Z") and len(tok) > 1:
                    try:
                        alvo_z = float(tok[1:])
                        tem_z = True
                    except ValueError:
                        pass
                elif tok.startswith("I") and len(tok) > 1:
                    try:
                        i_val = float(tok[1:])
                        tem_i = True
                    except ValueError:
                        pass
                elif tok.startswith("J") and len(tok) > 1:
                    try:
                        j_val = float(tok[1:])
                        tem_j = True
                    except ValueError:
                        pass
                elif tok.startswith("R") and len(tok) > 1:
                    try:
                        r_val = float(tok[1:])
                        tem_r = True
                    except ValueError:
                        pass
                elif tok.startswith("F") and len(tok) > 1:
                    feed_rate_str = f" {tok}"

            # Detectar comandos de movimento lineares e circulares
            g_cmd = None
            if "G0" in tokens or "G00" in tokens:
                g_cmd = "G0"
                modo_g_atual = "G0"
            elif "G1" in tokens or "G01" in tokens:
                g_cmd = "G1"
                modo_g_atual = "G1"
            elif "G2" in tokens or "G02" in tokens:
                g_cmd = "G2"
                modo_g_atual = "G2"
            elif "G3" in tokens or "G03" in tokens:
                g_cmd = "G3"
                modo_g_atual = "G3"
            elif (tem_x or tem_y or tem_z or tem_i or tem_j or tem_r) and modo_g_atual:
                g_cmd = modo_g_atual

            if g_cmd is None:
                linhas_resultado.append(linha)
                continue

            # --- Tratamento de Arcos Circulares (G2 / G3) ---
            if g_cmd in ("G2", "G3"):
                x0, y0 = pos_x, pos_y
                x1 = alvo_x
                y1 = alvo_y
                z0 = pos_z
                z1 = alvo_z

                # Calcular centro (cx, cy) e raio r do arco
                if tem_i or tem_j:
                    cx = x0 + (i_val if i_val is not None else 0.0)
                    cy = y0 + (j_val if j_val is not None else 0.0)
                    r = math.hypot(x0 - cx, y0 - cy)
                elif tem_r and abs(r_val) > 1e-4:
                    r = abs(r_val)
                    dx = x1 - x0
                    dy = y1 - y0
                    dist = math.hypot(dx, dy)
                    if dist < 1e-6 or dist > 2.0 * r:
                        cx, cy = x0, y0
                    else:
                        h = math.sqrt(max(0.0, r * r - (dist / 2.0) ** 2))
                        mx = (x0 + x1) / 2.0
                        my = (y0 + y1) / 2.0
                        nx = -dy / dist
                        ny = dx / dist
                        if g_cmd == "G2":
                            if r_val > 0:
                                cx = mx + nx * h
                                cy = my + ny * h
                            else:
                                cx = mx - nx * h
                                cy = my - ny * h
                        else:
                            if r_val > 0:
                                cx = mx - nx * h
                                cy = my - ny * h
                            else:
                                cx = mx + nx * h
                                cy = my + ny * h
                else:
                    cx, cy = x0, y0
                    r = 0.0

                # Regra de detecção de desenho para o arco
                if z_down_atual >= z_up_atual:
                    eh_desenho_arco = (z1 >= limiar_desenho or z0 >= limiar_desenho)
                else:
                    eh_desenho_arco = (z1 <= limiar_desenho or z0 <= limiar_desenho)

                if r < 1e-4:
                    # Fallback linear seguro
                    if eh_desenho_arco:
                        z_comp = self.calcular_z_interpolado(caneta_ativa, x1, y1)
                        linhas_resultado.append(f"G1 X{x1:.3f} Y{y1:.3f} Z{z_comp:.3f}{feed_rate_str}")
                        pos_z = z_comp
                    else:
                        linhas_resultado.append(f"G1 X{x1:.3f} Y{y1:.3f} Z{z1:.3f}{feed_rate_str}")
                        pos_z = z1
                    pos_x = x1
                    pos_y = y1
                    continue

                ang_ini = math.atan2(y0 - cy, x0 - cx)
                ang_fim = math.atan2(y1 - cy, x1 - cx)
                is_circulo_fechado = (math.hypot(x1 - x0, y1 - y0) < 1e-4)

                if g_cmd == "G2":
                    if is_circulo_fechado:
                        sweep = -2.0 * math.pi
                    else:
                        if ang_fim >= ang_ini:
                            ang_fim -= 2.0 * math.pi
                        sweep = ang_fim - ang_ini
                else:  # G3
                    if is_circulo_fechado:
                        sweep = 2.0 * math.pi
                    else:
                        if ang_fim <= ang_ini:
                            ang_fim += 2.0 * math.pi
                        sweep = ang_fim - ang_ini

                comprimento_arco = abs(sweep) * r
                max_seg = min(max_comprimento_segmento, 2.0)
                num_subdivisoes = max(8, int(math.ceil(comprimento_arco / max_seg)))
                if is_circulo_fechado:
                    num_subdivisoes = max(num_subdivisoes, 24)

                for k in range(1, num_subdivisoes + 1):
                    frac = k / num_subdivisoes
                    ang = ang_ini + frac * sweep
                    sub_x = cx + r * math.cos(ang)
                    sub_y = cy + r * math.sin(ang)

                    if eh_desenho_arco:
                        if self.esta_dentro_area(sub_x, sub_y):
                            z_comp = self.calcular_z_interpolado(caneta_ativa, sub_x, sub_y)
                            linhas_resultado.append(
                                f"G1 X{sub_x:.3f} Y{sub_y:.3f} Z{z_comp:.3f}{feed_rate_str}"
                            )
                            pos_z = z_comp
                        else:
                            linhas_resultado.append(
                                f"; [SEGURANÇA] Ponto do arco fora da área de desenho ({sub_x:.1f}, {sub_y:.1f}). Elevando caneta (Auto-Lift Z)."
                            )
                            linhas_resultado.append(f"G0 Z{z_up_atual:.3f} F3000")
                            linhas_resultado.append(f"G0 X{sub_x:.3f} Y{sub_y:.3f}{feed_rate_str}")
                            pos_z = z_up_atual
                    else:
                        sub_z_nom = z0 + frac * (z1 - z0)
                        linhas_resultado.append(
                            f"G1 X{sub_x:.3f} Y{sub_y:.3f} Z{sub_z_nom:.3f}{feed_rate_str}"
                        )
                        pos_z = sub_z_nom

                pos_x = x1
                pos_y = y1
                continue

            # --- Tratamento de Movimentos Lineares (G0 / G1) ---
            # Regra de detecção de desenho:
            if z_down_atual >= z_up_atual:
                # Convenção padrão da plotter AXIS: Z maior = contato com a mesa/papel
                eh_desenho = (g_cmd == "G1") and (alvo_z >= limiar_desenho or pos_z >= limiar_desenho)
                eh_contato_vertical = tem_z and (alvo_z >= limiar_desenho)
            else:
                # Convenção invertida: Z menor = contato com a mesa
                eh_desenho = (g_cmd == "G1") and (alvo_z <= limiar_desenho or pos_z <= limiar_desenho)
                eh_contato_vertical = tem_z and (alvo_z <= limiar_desenho)

            # Proteção de Limites de Área de Desenho (Auto-Lift Z):
            if eh_desenho and (tem_x or tem_y):
                alvo_dentro = self.esta_dentro_area(alvo_x, alvo_y)
                if not alvo_dentro:
                    # O traço tentaria sair da área de desenho com a caneta abaixada:
                    # Eleva a caneta para Z seguro antes do deslocamento
                    linhas_resultado.append(
                        f"; [SEGURANÇA] Destino fora da área de desenho ({alvo_x:.1f}, {alvo_y:.1f}). Elevando caneta (Auto-Lift Z)."
                    )
                    linhas_resultado.append(f"G0 Z{z_up_atual:.3f} F3000")
                    linhas_resultado.append(f"G0 X{alvo_x:.3f} Y{alvo_y:.3f}{feed_rate_str}")
                    pos_x = alvo_x
                    pos_y = alvo_y
                    pos_z = z_up_atual
                    continue

                # Destino dentro da área: interpolação e fatiamento dinâmico
                dist_xy = math.hypot(alvo_x - pos_x, alvo_y - pos_y)
                num_subdivisoes = max(1, int(math.ceil(dist_xy / max_comprimento_segmento)))

                if num_subdivisoes > 1 and dist_xy > max_comprimento_segmento:
                    for k in range(1, num_subdivisoes + 1):
                        frac = k / num_subdivisoes
                        sub_x = pos_x + frac * (alvo_x - pos_x)
                        sub_y = pos_y + frac * (alvo_y - pos_y)
                        z_comp = self.calcular_z_interpolado(caneta_ativa, sub_x, sub_y)
                        linhas_resultado.append(
                            f"G1 X{sub_x:.3f} Y{sub_y:.3f} Z{z_comp:.3f}{feed_rate_str}"
                        )
                        pos_z = z_comp
                else:
                    z_comp = self.calcular_z_interpolado(caneta_ativa, alvo_x, alvo_y)
                    linhas_resultado.append(
                        f"G1 X{alvo_x:.3f} Y{alvo_y:.3f} Z{z_comp:.3f}{feed_rate_str}"
                    )
                    pos_z = z_comp

                pos_x = alvo_x
                pos_y = alvo_y
                continue
            elif eh_contato_vertical:
                # Movimento vertical para contato com o papel
                if self.esta_dentro_area(alvo_x, alvo_y):
                    z_comp = self.calcular_z_interpolado(caneta_ativa, alvo_x, alvo_y)
                    nova_linha = f"{g_cmd}"
                    if tem_x:
                        nova_linha += f" X{alvo_x:.3f}"
                    if tem_y:
                        nova_linha += f" Y{alvo_y:.3f}"
                    nova_linha += f" Z{z_comp:.3f}{feed_rate_str}"
                    linhas_resultado.append(nova_linha)
                    pos_z = z_comp
                else:
                    linhas_resultado.append(
                        f"; [SEGURANÇA] Contato vertical fora da área de desenho ({alvo_x:.1f}, {alvo_y:.1f}). Z mantido em {z_up_atual:.2f}mm."
                    )
                    linhas_resultado.append(f"G0 Z{z_up_atual:.3f} F3000")
                    pos_z = z_up_atual
                pos_x = alvo_x
                pos_y = alvo_y
                continue
            else:
                # Movimento rápido ou Z elevado (safe travel)
                linhas_resultado.append(linha)
                pos_x = alvo_x
                pos_y = alvo_y
                pos_z = alvo_z

        return "\n".join(linhas_resultado)

    # ------------------------------------------------------------------ #
    #                       SINCRONIZAÇÃO E EVENTOS                      #
    # ------------------------------------------------------------------ #

    def _ao_alterar_area_desenho(self, x_ini: float, y_ini: float, x_fim: float, y_fim: float) -> None:
        """Recalcula a distribuição de coordenadas de todas as malhas quando a área de desenho muda."""
        for id_caneta, malha in self._config.canetas.items():
            num_linhas = malha.num_linhas
            num_cols = malha.num_pontos_por_linha
            for p in malha.pontos:
                if num_linhas > 1:
                    p.y = round(y_ini + (p.linha / (num_linhas - 1)) * (y_fim - y_ini), 3)
                else:
                    p.y = round((y_ini + y_fim) / 2.0, 3)

                if num_cols > 1:
                    p.x = round(x_ini + (p.coluna / (num_cols - 1)) * (x_fim - x_ini), 3)
                else:
                    p.x = round((x_ini + x_fim) / 2.0, 3)

        self._salvar_configuracao()
        self.sinal_nivelamento_atualizado.emit()

    def _sincronizar_dados_canetas(self) -> None:
        """Sincroniza os nomes e cores das canetas a partir do GerenciadorCanetas."""
        if not self._gerenciador_canetas:
            return

        slots = self._gerenciador_canetas.obter_todos_slots()
        alterado = False
        for slot in slots:
            if slot.id in self._config.canetas:
                malha = self._config.canetas[slot.id]
                if malha.nome != slot.nome or malha.cor_hex != slot.cor_hex:
                    malha.nome = slot.nome
                    malha.cor_hex = slot.cor_hex
                    alterado = True

        if alterado:
            self._salvar_configuracao()
            self.sinal_nivelamento_atualizado.emit()

    # ------------------------------------------------------------------ #
    #                       PERSISTÊNCIA JSON                            #
    # ------------------------------------------------------------------ #

    def _carregar_configuracao(self) -> None:
        """
        Carrega a configuração de nivelamento do disco ou inicializa padrão de 10 canetas.
        """
        if os.path.exists(self._caminho_config):
            try:
                with open(self._caminho_config, "r", encoding="utf-8") as arquivo_config:
                    dados = json.load(arquivo_config)
                    self._config.nivelamento_ativo = dados.get("nivelamento_ativo", True)
                    self._config.canetas = {}
                    for item in dados.get("canetas", []):
                        pontos = [PontoMalha(**p) for p in item.get("pontos", [])]
                        z_up_val = float(item.get("z_up", item.get("z_seguro", 15.0)))
                        z_down_val = float(item.get("z_down", 0.0))
                        malha = MalhaCaneta(
                            id_caneta=item["id_caneta"],
                            nome=item.get("nome", f"Caneta {item['id_caneta']}"),
                            cor_hex=item.get("cor_hex", "#5b7fff"),
                            num_linhas=item.get("num_linhas", 4),
                            num_pontos_por_linha=item.get("num_pontos_por_linha", 4),
                            pontos=pontos,
                            calibrado=item.get("calibrado", False),
                            distancia_teste_traco=item.get("distancia_teste_traco", 10.0),
                            feed_teste_traco=item.get("feed_teste_traco", 1000),
                            z_up=z_up_val,
                            z_down=z_down_val,
                            z_seguro=z_up_val
                        )
                        self._config.canetas[malha.id_caneta] = malha

                    if len(self._config.canetas) == 10:
                        return
            except Exception:
                pass

        # Inicializar 10 canetas padrão
        x_ini, y_ini, x_fim, y_fim = self.obter_limites_area()
        cores_padrao = [
            "#0f172a", "#2563eb", "#ef4444", "#10b981", "#eab308",
            "#f97316", "#a855f7", "#ec4899", "#854d0e", "#06b6d4"
        ]
        nomes_padrao = [
            "Preto", "Azul", "Vermelho", "Verde", "Amarelo",
            "Laranja", "Roxo", "Rosa", "Marrom", "Ciano"
        ]

        self._config.nivelamento_ativo = True
        self._config.canetas = {}

        for i in range(1, 11):
            cor = cores_padrao[i - 1]
            nome = nomes_padrao[i - 1]
            z_up_padrao = 15.0
            z_down_padrao = 0.0
            if self._gerenciador_canetas:
                slot = self._gerenciador_canetas.obter_slot(i)
                if slot:
                    cor = slot.cor_hex
                    nome = slot.nome
                    z_up_padrao = getattr(slot, "z_up", slot.z_seguro)
                    z_down_padrao = getattr(slot, "z_down", 0.0)

            num_linhas = 4
            num_pontos_por_linha = 4
            pontos = []
            for lin in range(num_linhas):
                y_val = y_ini + (lin / (num_linhas - 1)) * (y_fim - y_ini)
                for col in range(num_pontos_por_linha):
                    x_val = x_ini + (col / (num_pontos_por_linha - 1)) * (x_fim - x_ini)
                    pontos.append(PontoMalha(
                        linha=lin,
                        coluna=col,
                        x=round(x_val, 3),
                        y=round(y_val, 3),
                        z=z_down_padrao,
                        calibrado=False
                    ))

            self._config.canetas[i] = MalhaCaneta(
                id_caneta=i,
                nome=nome,
                cor_hex=cor,
                num_linhas=num_linhas,
                num_pontos_por_linha=num_pontos_por_linha,
                pontos=pontos,
                calibrado=False,
                distancia_teste_traco=10.0,
                feed_teste_traco=1000,
                z_up=z_up_padrao,
                z_down=z_down_padrao,
                z_seguro=z_up_padrao
            )

        self._salvar_configuracao()

    def _salvar_configuracao(self) -> None:
        """
        Salva as configurações de nivelamento em arquivo JSON.
        """
        try:
            pasta = os.path.dirname(self._caminho_config)
            if pasta and not os.path.exists(pasta):
                os.makedirs(pasta, exist_ok=True)

            dados = {
                "nivelamento_ativo": self._config.nivelamento_ativo,
                "canetas": [
                    {
                        "id_caneta": m.id_caneta,
                        "nome": m.nome,
                        "cor_hex": m.cor_hex,
                        "num_linhas": m.num_linhas,
                        "num_pontos_por_linha": m.num_pontos_por_linha,
                        "calibrado": m.calibrado,
                        "distancia_teste_traco": m.distancia_teste_traco,
                        "feed_teste_traco": m.feed_teste_traco,
                        "z_up": m.z_up,
                        "z_down": m.z_down,
                        "z_seguro": m.z_up,
                        "pontos": [asdict(p) for p in m.pontos]
                    }
                    for m in sorted(self._config.canetas.values(), key=lambda x: x.id_caneta)
                ]
            }

            with open(self._caminho_config, "w", encoding="utf-8") as arquivo_config:
                json.dump(dados, arquivo_config, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def importar_calibracao_de_arquivo(self, caminho_arquivo: str) -> Tuple[bool, str, int]:
        """
        Importa offsets e malhas calibradas de um arquivo JSON previamente salvo.
        Atualiza as configurações de todas as canetas contidas no arquivo,
        preservando com exatidão os pontos calibrados (X, Y, Z, calibrado) e limites Z-Up/Z-Down.

        Args:
            caminho_arquivo (str): Caminho completo para o arquivo JSON de calibração.

        Returns:
            Tuple[bool, str, int]: (sucesso, mensagem descritiva, quantidade de canetas importadas).
        """
        if not os.path.exists(caminho_arquivo):
            return False, f"Arquivo não encontrado: {caminho_arquivo}", 0

        try:
            with open(caminho_arquivo, "r", encoding="utf-8") as arquivo_importacao:
                dados = json.load(arquivo_importacao)
        except Exception as erro:
            return False, f"Erro ao ler arquivo JSON: {str(erro)}", 0

        if not isinstance(dados, (dict, list)):
            return False, "Estrutura do arquivo inválida (esperava objeto ou lista JSON).", 0

        lista_canetas_dados = []
        if isinstance(dados, dict):
            if "canetas" in dados and isinstance(dados["canetas"], list):
                lista_canetas_dados = dados["canetas"]
                if "nivelamento_ativo" in dados:
                    self._config.nivelamento_ativo = bool(dados["nivelamento_ativo"])
            elif "id_caneta" in dados:
                lista_canetas_dados = [dados]
        elif isinstance(dados, list):
            lista_canetas_dados = dados

        if not lista_canetas_dados:
            return False, "Nenhuma configuração de caneta encontrada no arquivo.", 0

        total_importadas = 0
        total_pontos_calibrados = 0

        for item in lista_canetas_dados:
            if not isinstance(item, dict):
                continue

            id_caneta_item = item.get("id_caneta", item.get("id"))
            if id_caneta_item is None:
                continue

            try:
                id_caneta_item = int(id_caneta_item)
            except ValueError:
                continue

            if id_caneta_item not in self._config.canetas:
                nome_caneta_item = item.get("nome", f"Caneta {id_caneta_item}")
                cor_caneta_item = item.get("cor_hex", "#5b7fff")
                self._config.canetas[id_caneta_item] = MalhaCaneta(
                    id_caneta=id_caneta_item,
                    nome=nome_caneta_item,
                    cor_hex=cor_caneta_item
                )

            malha = self._config.canetas[id_caneta_item]

            if "nome" in item:
                malha.nome = str(item["nome"])
            if "cor_hex" in item:
                malha.cor_hex = str(item["cor_hex"])
            if "num_linhas" in item:
                malha.num_linhas = int(item["num_linhas"])
            if "num_pontos_por_linha" in item:
                malha.num_pontos_por_linha = int(item["num_pontos_por_linha"])
            if "distancia_teste_traco" in item:
                malha.distancia_teste_traco = float(item["distancia_teste_traco"])
            if "feed_teste_traco" in item:
                malha.feed_teste_traco = int(item["feed_teste_traco"])
            if "z_up" in item:
                malha.z_up = float(item["z_up"])
            elif "z_seguro" in item:
                malha.z_up = float(item["z_seguro"])
            if "z_down" in item:
                malha.z_down = float(item["z_down"])
            malha.z_seguro = malha.z_up

            # Atualizar pontos da malha
            if "pontos" in item and isinstance(item["pontos"], list):
                novos_pontos = []
                for p_dict in item["pontos"]:
                    if not isinstance(p_dict, dict):
                        continue
                    ponto = PontoMalha(
                        linha=int(p_dict.get("linha", 0)),
                        coluna=int(p_dict.get("coluna", 0)),
                        x=float(p_dict.get("x", 0.0)),
                        y=float(p_dict.get("y", 0.0)),
                        z=float(p_dict.get("z", malha.z_down)),
                        calibrado=bool(p_dict.get("calibrado", False))
                    )
                    if ponto.calibrado:
                        total_pontos_calibrados += 1
                    novos_pontos.append(ponto)

                if novos_pontos:
                    malha.pontos = novos_pontos

            if "calibrado" in item:
                malha.calibrado = bool(item["calibrado"])
            elif malha.pontos:
                malha.calibrado = all(p.calibrado for p in malha.pontos)

            # Sincronizar com GerenciadorCanetas se disponível
            if self._gerenciador_canetas:
                slot = self._gerenciador_canetas.obter_slot(id_caneta_item)
                if slot:
                    slot.z_up = malha.z_up
                    slot.z_down = malha.z_down
                    slot.z_seguro = malha.z_up
                    self._gerenciador_canetas.atualizar_slot(slot)

            total_importadas += 1

        if total_importadas == 0:
            return False, "Nenhuma caneta válida pôde ser importada do arquivo.", 0

        self._salvar_configuracao()
        self.sinal_nivelamento_atualizado.emit()
        return True, f"Importação concluída com sucesso: {total_importadas} caneta(s) e {total_pontos_calibrados} ponto(s) calibrado(s).", total_importadas

    def exportar_calibracao_para_arquivo(self, caminho_arquivo: str) -> Tuple[bool, str]:
        """
        Exporta a malha de pontos e offsets de todas as canetas para arquivo JSON.

        Args:
            caminho_arquivo (str): Caminho onde o arquivo JSON será salvo.

        Returns:
            Tuple[bool, str]: (sucesso, mensagem descritiva).
        """
        try:
            pasta = os.path.dirname(caminho_arquivo)
            if pasta and not os.path.exists(pasta):
                os.makedirs(pasta, exist_ok=True)

            dados = {
                "nivelamento_ativo": self._config.nivelamento_ativo,
                "canetas": [
                    {
                        "id_caneta": m.id_caneta,
                        "nome": m.nome,
                        "cor_hex": m.cor_hex,
                        "num_linhas": m.num_linhas,
                        "num_pontos_por_linha": m.num_pontos_por_linha,
                        "calibrado": m.calibrado,
                        "distancia_teste_traco": m.distancia_teste_traco,
                        "feed_teste_traco": m.feed_teste_traco,
                        "z_up": m.z_up,
                        "z_down": m.z_down,
                        "z_seguro": m.z_up,
                        "pontos": [asdict(p) for p in m.pontos]
                    }
                    for m in sorted(self._config.canetas.values(), key=lambda x: x.id_caneta)
                ]
            }

            with open(caminho_arquivo, "w", encoding="utf-8") as arquivo_exportacao:
                json.dump(dados, arquivo_exportacao, indent=2, ensure_ascii=False)
            return True, f"Calibração de {len(dados['canetas'])} canetas exportada com sucesso para {os.path.basename(caminho_arquivo)}!"
        except Exception as erro:
            return False, f"Erro ao exportar calibração: {str(erro)}"


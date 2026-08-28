"""
Módulo de gerenciamento da área de desenho da caneta da plotter AXIS.

Gerencia as coordenadas de início e fim (X, Y) da área de desenho,
com persistência em JSON e emissão de sinais para o mapa 2D.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Optional
from PySide6.QtCore import QObject, Signal


@dataclass
class ConfiguracaoAreaDesenho:
    """Representa as coordenadas delimitadoras da área de desenho da plotter."""
    x_inicio: float = 60.0
    y_inicio: float = 10.0
    x_fim: float = 270.0
    y_fim: float = 307.0


class GerenciadorAreaDesenho(QObject):
    """
    Controlador responsável por carregar, persistir e emitir notificações
    sobre a área de desenho da máquina.
    """

    sinal_area_alterada = Signal(float, float, float, float)  # (x_inicio, y_inicio, x_fim, y_fim)

    def __init__(self, caminho_arquivo_config: Optional[str] = None) -> None:
        """
        Inicializa o gerenciador da área de desenho.

        Args:
            caminho_arquivo_config (str, optional): Caminho customizado para o arquivo de configuração JSON.
        """
        super().__init__()
        self._caminho_config = caminho_arquivo_config or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "area_desenho.json"
        )
        self._config = ConfiguracaoAreaDesenho()
        self._carregar_configuracao()

    def obter_configuracao(self) -> ConfiguracaoAreaDesenho:
        """
        Retorna a configuração atual da área de desenho.

        Returns:
            ConfiguracaoAreaDesenho: Objeto contendo x_inicio, y_inicio, x_fim e y_fim.
        """
        return self._config

    def atualizar_area(self, x_inicio: float, y_inicio: float, x_fim: float, y_fim: float) -> None:
        """
        Atualiza as coordenadas da área de desenho, salva no arquivo JSON
        e emite o sinal para sincronização com o mapa 2D.

        Args:
            x_inicio (float): Posição X inicial da área de desenho em milímetros.
            y_inicio (float): Posição Y inicial da área de desenho em milímetros.
            x_fim (float): Posição X final da área de desenho em milímetros.
            y_fim (float): Posição Y final da área de desenho em milímetros.
        """
        self._config.x_inicio = float(x_inicio)
        self._config.y_inicio = float(y_inicio)
        self._config.x_fim = float(x_fim)
        self._config.y_fim = float(y_fim)

        self._salvar_configuracao()
        self.sinal_area_alterada.emit(
            self._config.x_inicio,
            self._config.y_inicio,
            self._config.x_fim,
            self._config.y_fim
        )

    def _carregar_configuracao(self) -> None:
        """
        Carrega as configurações salvas do disco ou cria padrão.
        """
        if os.path.exists(self._caminho_config):
            try:
                with open(self._caminho_config, "r", encoding="utf-8") as arquivo_config:
                    dados = json.load(arquivo_config)
                    self._config = ConfiguracaoAreaDesenho(
                        x_inicio=float(dados.get("x_inicio", 60.0)),
                        y_inicio=float(dados.get("y_inicio", 10.0)),
                        x_fim=float(dados.get("x_fim", 270.0)),
                        y_fim=float(dados.get("y_fim", 307.0))
                    )
                return
            except Exception:
                pass

        self._config = ConfiguracaoAreaDesenho()
        self._salvar_configuracao()

    def _salvar_configuracao(self) -> None:
        """
        Salva a configuração atual no arquivo JSON.
        """
        try:
            pasta = os.path.dirname(self._caminho_config)
            if pasta and not os.path.exists(pasta):
                os.makedirs(pasta, exist_ok=True)

            with open(self._caminho_config, "w", encoding="utf-8") as arquivo_config:
                json.dump(asdict(self._config), arquivo_config, indent=2, ensure_ascii=False)
        except OSError:
            pass

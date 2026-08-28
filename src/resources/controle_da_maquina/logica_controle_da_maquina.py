"""
Módulo de lógica de negócio para o controle da máquina.

Contém as funções e classes responsáveis pela comunicação
e controle dos motores e atuadores da máquina AXIS via protocolo GRBL.
"""

import sys
import re
from typing import Optional
import serial
import serial.tools.list_ports
from collections import deque
from PySide6.QtCore import QObject, Signal, QThread, QTimer, QMutex, QMutexLocker


def limpar_linha_gcode(linha: str) -> str:
    """
    Remove comentários (; e (...)) e espaços redundantes de uma linha G-code.
    Retorna string vazia se a linha for puramente comentário ou vazia.

    Args:
        linha (str): Linha de código G-code bruta.

    Returns:
        str: Linha limpa para envio ao GRBL, ou '' se descartável.
    """
    if not linha:
        return ""

    # Remover comentário de ponto-e-vírgula até o fim da linha
    if ";" in linha:
        linha = linha.split(";", 1)[0]

    # Remover comentários entre parênteses: (comentário)
    if "(" in linha and ")" in linha:
        linha = re.sub(r"\(.*?\)", "", linha)

    return linha.strip()


class LeitorSerial(QThread):
    """
    Thread dedicada à leitura contínua da porta serial.

    Roda em loop lendo linhas do GRBL e emitindo sinais
    para a thread principal processar as respostas.
    """

    sinal_linha_recebida = Signal(str)

    def __init__(self, porta_serial: serial.Serial) -> None:
        """
        Inicializa o leitor serial com a referência da porta.

        Args:
            porta_serial (serial.Serial): Instância da porta serial aberta.
        """
        super().__init__()
        self._porta_serial = porta_serial
        self._rodando = False

    def run(self) -> None:
        """
        Loop principal de leitura. Lê linhas da porta serial
        e emite o sinal para cada linha recebida.
        """
        self._rodando = True
        while self._rodando:
            try:
                if (self._porta_serial is not None
                        and self._porta_serial.is_open
                        and self._porta_serial.in_waiting > 0):
                    linha = self._porta_serial.readline().decode(
                        "utf-8", errors="replace"
                    ).strip()
                    if linha:
                        self.sinal_linha_recebida.emit(linha)
                else:
                    self.msleep(5)
            except (serial.SerialException, OSError):
                self._rodando = False
                break

    def parar(self) -> None:
        """
        Sinaliza para o loop de leitura parar e aguarda
        o encerramento da thread.
        """
        self._rodando = False
        self.wait(2000)


class ControladorGrbl(QObject):
    """
    Controlador de comunicação com firmware GRBL via porta serial.

    Gerencia conexão, envio de comandos, polling de status,
    movimentação jog, homing e leitura de configurações.
    """

    sinal_posicao_atualizada = Signal(float, float, float)
    sinal_status_atualizado = Signal(str)
    sinal_conexao_alterada = Signal(bool)
    sinal_resposta_recebida = Signal(str)
    sinal_erro = Signal(str)
    sinal_configuracao_recebida = Signal(float, float, float)
    sinal_parametros_grbl_recebidos = Signal(dict)
    sinal_envio_arquivo_concluido = Signal()
    sinal_progresso_envio = Signal(int, int)
    sinal_linha_enviada = Signal(int)
    sinal_pausa_alterada = Signal(bool)

    def __init__(self) -> None:
        """
        Inicializa o controlador GRBL sem conexão ativa.
        """
        super().__init__()
        # Janela de bytes em voo (GRBL usa buffer RX de 128 bytes; margem de segurança)
        self.JANELA_ENVIO_BYTES = 100

        self._porta_serial = None
        self._leitor_serial = None
        self._timer_status = QTimer(self)
        self._timer_status.timeout.connect(self._solicitar_status)
        self._mutex_envio = QMutex()
        self._conectado = False
        self._enviando_arquivo = False
        self._executando_script = False
        self._em_pausa = False
        self._linhas_pendentes = []
        self._mapa_indices_originais = []
        self._indice_linha_atual = 0
        self._total_linhas_arquivo = 0
        # Fila de linhas em voo aguardando 'ok': tuplas (indice_original, custo_bytes)
        self._fila_em_voo = deque()
        self._bytes_em_voo = 0
        self._linhas_confirmadas = 0
        self._aguardando_ocioso = False
        self._callback_conclusao_script = None
        self._nome_script_atual = ""
        self._status_atual = "IDLE"
        self._coletando_configuracoes = False
        self._configuracoes_coletadas = {}
        self._parametros_grbl = {}
        # Offset do sistema de coordenadas de trabalho (WCO) reportado pelo GRBL
        self._wco_x = 0.0
        self._wco_y = 0.0
        self._wco_z = 0.0
        # Posição de trabalho atual (WPos: X, Y, Z) em milímetros
        self._posicao_trabalho = (0.0, 0.0, 0.0)
        # Estado anterior da máquina para detectar fim do ciclo de homing
        self._estado_anterior = ""
        # Gerenciador de macros para expansão de macros no G-code (injetado externamente)
        self._gerenciador_macros = None
        # Gerenciador de canetas para expansão de comandos de troca no G-code
        self._gerenciador_canetas = None
        # Gerenciador de nivelamento por software (Mesh Bed Leveling)
        self._gerenciador_nivelamento = None
        # Caneta final após envio de arquivo (para atualizar estado após execução)
        self._caneta_final_apos_envio = None
        self._tem_caneta_final_apos_envio = False

    def definir_gerenciador_macros(self, gerenciador) -> None:
        """
        Define o gerenciador de macros para expansão automática de
        referências a macros em arquivos G-code (estilo Klipper).

        Args:
            gerenciador: Instância de GerenciadorMacros.
        """
        self._gerenciador_macros = gerenciador

    def definir_gerenciador_canetas(self, gerenciador) -> None:
        """
        Define o gerenciador de canetas para expansão automática de
        comandos de troca de caneta no G-code.

        Comandos reconhecidos no G-code:
            - TROCAR_CANETA_X  — Troca completa (devolve a atual + pega a nova)
            - PEGAR_CANETA_X   — Pega caneta X (sem devolver a atual)
            - SOLTAR_CANETA_X  — Devolve caneta X na baia
            - SOLTAR_CANETA    — Devolve a caneta atualmente ativa

        Args:
            gerenciador: Instância de GerenciadorCanetas.
        """
        self._gerenciador_canetas = gerenciador

    def definir_gerenciador_nivelamento(self, gerenciador) -> None:
        """
        Define o gerenciador de nivelamento por software para compensação
        dinâmica de Z-offset baseada na malha de calibração das canetas.

        Args:
            gerenciador: Instância de GerenciadorNivelamento.
        """
        self._gerenciador_nivelamento = gerenciador

    def listar_portas_disponiveis(self) -> list:
        """
        Lista todas as portas seriais válidas e conectadas no sistema.
        Filtra portas seriais virtuais/fantasmas do Linux (ex: ttyS0-ttyS31) que não possuem hardware conectado.

        Returns:
            list: Lista de strings com as portas disponíveis (ex: ['/dev/ttyUSB0', '/dev/ttyACM0', 'COM3']).
        """
        portas = serial.tools.list_ports.comports()
        lista_portas = []
        for porta in portas:
            # No Linux, filtrar portas /dev/ttyS* genéricas do kernel que não possuem hardware real conectado
            if sys.platform.startswith("linux"):
                if porta.device.startswith("/dev/ttyS") and (porta.hwid == "n/a" or porta.vid is None):
                    continue
            lista_portas.append(porta.device)
        return sorted(lista_portas)

    def conectar(self, porta: str, baud_rate: int = 115200) -> bool:
        """
        Abre a conexão serial com o GRBL na porta especificada.

        Args:
            porta (str): Nome da porta serial (ex: '/dev/ttyUSB0').
            baud_rate (int): Taxa de comunicação em baud. Padrão GRBL: 115200.

        Returns:
            bool: True se a conexão foi estabelecida com sucesso.
        """
        try:
            self._porta_serial = serial.Serial(
                port=porta,
                baudrate=baud_rate,
                timeout=0.1,
                write_timeout=2
            )

            self._porta_serial.reset_input_buffer()
            self._porta_serial.reset_output_buffer()

            self._leitor_serial = LeitorSerial(self._porta_serial)
            self._leitor_serial.sinal_linha_recebida.connect(
                self._processar_resposta
            )
            self._leitor_serial.start()

            self._conectado = True
            self.sinal_conexao_alterada.emit(True)
            self.sinal_resposta_recebida.emit(
                "[SISTEMA] Conectado em " + porta
            )

            self._timer_status.start(250)

            QTimer.singleShot(1500, self.obter_configuracao_area_trabalho)

            return True

        except serial.SerialException as erro:
            self.sinal_erro.emit(
                f"Erro ao conectar na porta {porta}: {str(erro)}"
            )
            self._conectado = False
            return False

    def desconectar(self) -> None:
        """
        Fecha a conexão serial e para o polling de status.
        """
        self._timer_status.stop()
        self._enviando_arquivo = False
        self._executando_script = False
        self._aguardando_ocioso = False
        self._em_pausa = False
        self._linhas_pendentes = []
        self._fila_em_voo.clear()
        self._bytes_em_voo = 0
        self._linhas_confirmadas = 0
        self._callback_conclusao_script = None
        self._nome_script_atual = ""
        self._wco_x = 0.0
        self._wco_y = 0.0
        self._wco_z = 0.0
        self._posicao_trabalho = (0.0, 0.0, 0.0)
        self._estado_anterior = ""
        self._status_atual = "IDLE"
        self.sinal_pausa_alterada.emit(False)

        if self._leitor_serial is not None:
            self._leitor_serial.parar()
            self._leitor_serial = None

        if self._porta_serial is not None and self._porta_serial.is_open:
            try:
                self._porta_serial.close()
            except serial.SerialException:
                pass

        self._porta_serial = None
        self._conectado = False
        self.sinal_conexao_alterada.emit(False)
        self.sinal_resposta_recebida.emit("[SISTEMA] Desconectado")

    def esta_conectado(self) -> bool:
        """
        Verifica se há uma conexão serial ativa.

        Returns:
            bool: True se conectado.
        """
        return self._conectado and self._porta_serial is not None

    def obter_posicao_atual(self) -> tuple:
        """
        Retorna a última posição de trabalho (X, Y, Z) conhecida da máquina.

        Returns:
            tuple[float, float, float]: Coordenadas (X, Y, Z) de trabalho em milímetros.
        """
        return self._posicao_trabalho

    def obter_posicao_x(self) -> float:
        """
        Retorna a coordenada de trabalho atual do eixo X em mm.

        Returns:
            float: Posição X de trabalho.
        """
        return self._posicao_trabalho[0]

    def obter_posicao_y(self) -> float:
        """
        Retorna a coordenada de trabalho atual do eixo Y em mm.

        Returns:
            float: Posição Y de trabalho.
        """
        return self._posicao_trabalho[1]

    def obter_posicao_z(self) -> float:
        """
        Retorna a coordenada de trabalho atual do eixo Z em mm.

        Returns:
            float: Posição Z de trabalho.
        """
        return self._posicao_trabalho[2]

    def obter_caneta_ativa_id(self) -> int:
        """Retorna o ID da caneta ativa no cabeçote ou 1 por padrão."""
        if self._gerenciador_canetas is not None:
            cid = self._gerenciador_canetas.obter_caneta_ativa_id()
            if cid is not None and cid > 0:
                return cid
        return 1

    def caneta_esta_abaixada(self, z_valor: Optional[float] = None) -> bool:
        """
        Verifica se a caneta está na altura de escrita/contato com o papel.
        """
        z_atual = z_valor if z_valor is not None else self.obter_posicao_z()
        cid = self.obter_caneta_ativa_id()
        if self._gerenciador_nivelamento is not None:
            z_up, z_down = self._gerenciador_nivelamento.obter_z_up_down(cid)
        elif self._gerenciador_canetas is not None:
            slot = self._gerenciador_canetas.obter_slot(cid)
            z_up = slot.z_up if slot else -4.0
            z_down = slot.z_down if slot else 25.0
        else:
            z_up, z_down = -4.0, 25.0

        limiar = (z_up + z_down) / 2.0
        if z_down >= z_up:
            return z_atual >= limiar
        else:
            return z_atual <= limiar

    def caneta_esta_alta(self, z_seguro: Optional[float] = None, margem: float = 0.5) -> bool:
        """
        Verifica se a caneta está na altura segura de trabalho (Z no ar).
        """
        return not self.caneta_esta_abaixada()

    def abaixar_caneta(self, id_caneta: Optional[int] = None) -> bool:
        """
        Abaixa a caneta suavemente até a altura de contato com a mesa/papel.
        Se estiver dentro da área de desenho, calcula dinamicamente o Z compensado pela malha.
        Se estiver fora da área, utiliza o Z-Down nominal configurado para a ferramenta.
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return False

        if self.esta_enviando():
            self.sinal_erro.emit("Máquina ocupada executando comando.")
            return False

        cid = id_caneta if (id_caneta is not None and id_caneta > 0) else self.obter_caneta_ativa_id()
        x_atual, y_atual, _ = self.obter_posicao_atual()

        if self._gerenciador_nivelamento is not None:
            z_up, z_down = self._gerenciador_nivelamento.obter_z_up_down(cid)
            if self._gerenciador_nivelamento.esta_dentro_area(x_atual, y_atual):
                z_alvo = self._gerenciador_nivelamento.calcular_z_compensado_ponto(cid, x_atual, y_atual)
            else:
                z_alvo = z_down
        elif self._gerenciador_canetas is not None:
            slot = self._gerenciador_canetas.obter_slot(cid)
            z_alvo = slot.z_down if slot else 25.0
        else:
            z_alvo = 25.0

        nome_caneta = f"Caneta {cid}"
        if self._gerenciador_canetas:
            slot = self._gerenciador_canetas.obter_slot(cid)
            if slot:
                nome_caneta = f"Caneta {cid} ({slot.nome})"

        self.sinal_resposta_recebida.emit(
            f"[CANETA] Abaixando {nome_caneta} para Z={z_alvo:.3f}mm na posição (X={x_atual:.1f}, Y={y_atual:.1f})..."
        )
        script = f"G90\nG1 Z{z_alvo:.3f} F600\n"
        return self.enviar_script_gcode(script, nome=f"Abaixar Caneta {cid}")

    def levantar_caneta(self, id_caneta: Optional[int] = None) -> bool:
        """
        Eleva a caneta imediatamente para a altura segura de trânsito aéreo (Z-Up).
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return False

        if self.esta_enviando():
            self.sinal_erro.emit("Máquina ocupada executando comando.")
            return False

        cid = id_caneta if (id_caneta is not None and id_caneta > 0) else self.obter_caneta_ativa_id()

        if self._gerenciador_nivelamento is not None:
            z_up, _ = self._gerenciador_nivelamento.obter_z_up_down(cid)
        elif self._gerenciador_canetas is not None:
            slot = self._gerenciador_canetas.obter_slot(cid)
            z_up = slot.z_up if slot else -4.0
        else:
            z_up = -4.0

        self.sinal_resposta_recebida.emit(
            f"[CANETA] Levantando caneta {cid} para Z-Up seguro ({z_up:.2f}mm)..."
        )
        script = f"G90\nG0 Z{z_up:.3f} F3000\n"
        return self.enviar_script_gcode(script, nome=f"Levantar Caneta {cid}")

    def hop_caneta(self, id_caneta: Optional[int] = None) -> bool:
        """
        Eleva a caneta apenas uma pequena distância intermediária (2.0mm) acima do papel
        para troca rápida de traço/linha na escrita (PEN_HOP).
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return False

        if self.esta_enviando():
            self.sinal_erro.emit("Máquina ocupada executando comando.")
            return False

        cid = id_caneta if (id_caneta is not None and id_caneta > 0) else self.obter_caneta_ativa_id()
        x_atual, y_atual, _ = self.obter_posicao_atual()

        if self._gerenciador_nivelamento is not None:
            z_hop_alvo = self._gerenciador_nivelamento.calcular_z_hop_ponto(cid, x_atual, y_atual)
        elif self._gerenciador_canetas is not None:
            slot = self._gerenciador_canetas.obter_slot(cid)
            z_up = slot.z_up if slot else -4.0
            z_down = slot.z_down if slot else 25.0
            if z_down >= z_up:
                z_hop_alvo = max(z_up, z_down - 2.0)
            else:
                z_hop_alvo = min(z_up, z_down + 2.0)
        else:
            z_hop_alvo = 23.0

        nome_caneta = f"Caneta {cid}"
        if self._gerenciador_canetas:
            slot = self._gerenciador_canetas.obter_slot(cid)
            if slot:
                nome_caneta = f"Caneta {cid} ({slot.nome})"

        self.sinal_resposta_recebida.emit(
            f"[CANETA] Salto intermediário (PEN_HOP) de {nome_caneta} para Z={z_hop_alvo:.3f}mm..."
        )
        script = f"G90\nG0 Z{z_hop_alvo:.3f} F3000\n"
        return self.enviar_script_gcode(script, nome=f"Hop Caneta {cid}")

    def enviar_comando(self, comando: str) -> None:
        """
        Envia um comando de texto avulso para o GRBL via serial.

        Comandos manuais são bloqueados durante o envio de arquivo/script para
        não desincronizar a contagem de 'ok' da transmissão.

        Args:
            comando (str): Comando G-code ou GRBL a ser enviado.
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return

        if self.esta_enviando():
            self.sinal_erro.emit(
                "Execução em andamento — comando manual bloqueado."
            )
            return

        # Se contiver múltiplas linhas, despacha via enviar_script_gcode
        if "\n" in comando.strip():
            self.enviar_script_gcode(comando, nome="Comando Múltiplo")
            return

        comando_limpo = limpar_linha_gcode(comando)
        # Se for comando de sistema ($X, $H, $$, etc.), manter
        if not comando_limpo and comando.strip().startswith("$"):
            comando_limpo = comando.strip().split(";")[0].strip()

        if not comando_limpo:
            return

        # Expandir macros customizadas
        if self._gerenciador_macros is not None:
            expansao_macro = self._gerenciador_macros.expandir_macros_em_gcode(comando_limpo)
            if expansao_macro.strip() != comando_limpo:
                self.enviar_script_gcode(expansao_macro, nome=f"Macro: {comando_limpo}")
                return

        # Expandir comandos de caneta (TROCAR_CANETA_X, PEGAR_CANETA_X, SOLTAR_CANETA, etc.)
        if self._gerenciador_canetas is not None:
            expansao_caneta = self._expandir_comandos_canetas(comando_limpo)
            if expansao_caneta.strip() != comando_limpo:
                caneta_alvo = self._caneta_final_apos_envio
                self._tem_caneta_final_apos_envio = False
                self._caneta_final_apos_envio = None
                self.enviar_script_gcode(
                    expansao_caneta,
                    nome=f"Caneta: {comando_limpo}",
                    callback_conclusao=lambda: self._gerenciador_canetas.definir_caneta_ativa(caneta_alvo)
                )
                return

        # Expandir comandos PEN_DOWN, PEN_UP e PEN_HOP avulsos
        cmd_upper = comando_limpo.upper()
        if cmd_upper == "PEN_DOWN":
            self.abaixar_caneta()
            return
        elif cmd_upper == "PEN_HOP":
            self.hop_caneta()
            return
        elif cmd_upper == "PEN_UP":
            self.levantar_caneta()
            return

        # Se for comando $$ de leitura de parâmetros, ativa coleta
        if comando_limpo == "$$":
            self._coletando_configuracoes = True
            self._configuracoes_coletadas = {}
            self._parametros_grbl = {}

        self._escrever_serial(comando_limpo)

    def _escrever_serial(self, comando: str) -> None:
        """
        Escreve uma linha na porta serial e registra no console.

        Método interno usado tanto por comandos manuais quanto pelo
        transmissor de arquivo/script (que não pode ser bloqueado).

        Args:
            comando (str): Linha já limpa a ser enviada.
        """
        try:
            with QMutexLocker(self._mutex_envio):
                self._porta_serial.write((comando + "\n").encode("utf-8"))
            self.sinal_resposta_recebida.emit(f"> {comando}")
        except serial.SerialException as erro:
            self.sinal_erro.emit(f"Erro ao enviar comando: {str(erro)}")
            self.desconectar()

    def esta_enviando(self) -> bool:
        """
        Verifica se há um envio de arquivo G-code ou script em andamento.

        Returns:
            bool: True se estiver transmitindo arquivo ou script ou aguardando conclusão física.
        """
        return self._enviando_arquivo or self._executando_script or self._aguardando_ocioso

    def esta_em_pausa(self) -> bool:
        """
        Verifica se o envio de arquivo G-code está pausado.

        Returns:
            bool: True se estiver em pausa.
        """
        return self._em_pausa

    def desbloquear_maquina(self) -> None:
        """
        Envia o comando de desbloqueio ($X) ao GRBL para desativar o estado de alarme.
        """
        self.enviar_comando("$X")

    def reiniciar_grbl(self) -> None:
        """
        Envia um soft-reset (Ctrl+X / \\x18) ao GRBL para reiniciar o controlador.
        Cancela qualquer transmissão de arquivo ou script em andamento.
        """
        self._enviando_arquivo = False
        self._executando_script = False
        self._aguardando_ocioso = False
        self._em_pausa = False
        self._linhas_pendentes = []
        self._fila_em_voo.clear()
        self._bytes_em_voo = 0
        self._linhas_confirmadas = 0
        self._callback_conclusao_script = None
        self._nome_script_atual = ""
        self.sinal_pausa_alterada.emit(False)
        self.sinal_linha_enviada.emit(-1)

        if self.esta_conectado():
            try:
                with QMutexLocker(self._mutex_envio):
                    self._porta_serial.write(b"\x18")
                self.sinal_resposta_recebida.emit("[SISTEMA] Soft Reset enviado ao GRBL (Ctrl+X).")
            except serial.SerialException as erro:
                self.sinal_erro.emit(f"Erro ao reiniciar GRBL: {str(erro)}")

        if self.esta_conectado():
            try:
                with QMutexLocker(self._mutex_envio):
                    self._porta_serial.write(b"\x18")
                self.sinal_resposta_recebida.emit("[SISTEMA] Soft Reset enviado ao GRBL (Ctrl+X).")
            except serial.SerialException as erro:
                self.sinal_erro.emit(f"Erro ao reiniciar GRBL: {str(erro)}")

    def pausar_envio_arquivo(self) -> None:
        """
        Pausa o envio de arquivo G-code em andamento e envia o caractere
        de Feed Hold ('!') ao GRBL em tempo real.
        """
        if not self._enviando_arquivo or self._em_pausa:
            return

        self._em_pausa = True
        if self.esta_conectado():
            try:
                with QMutexLocker(self._mutex_envio):
                    self._porta_serial.write(b"!")
                self.sinal_resposta_recebida.emit("[SISTEMA] Execução pausada (Feed Hold).")
            except serial.SerialException as erro:
                self.sinal_erro.emit(f"Erro ao pausar execução: {str(erro)}")

        self.sinal_pausa_alterada.emit(True)

    def retomar_envio_arquivo(self) -> None:
        """
        Retoma o envio de arquivo G-code pausado e envia o caractere
        de Cycle Start ('~') ao GRBL em tempo real.
        """
        if not self._enviando_arquivo or not self._em_pausa:
            return

        self._em_pausa = False
        if self.esta_conectado():
            try:
                with QMutexLocker(self._mutex_envio):
                    self._porta_serial.write(b"~")
                self.sinal_resposta_recebida.emit("[SISTEMA] Execução retomada (Cycle Start).")
            except serial.SerialException as erro:
                self.sinal_erro.emit(f"Erro ao retomar execução: {str(erro)}")

        self.sinal_pausa_alterada.emit(False)
        self._despachar_linhas()

    def alternar_pausa(self) -> None:
        """
        Alterna entre pausar e retomar a execução do arquivo G-code.
        """
        if self._em_pausa:
            self.retomar_envio_arquivo()
        else:
            self.pausar_envio_arquivo()

    def executar_auto_home(self) -> None:
        """
        Executa o ciclo de homing ($H) da máquina.

        Move todos os eixos até os fins de curso para
        definir a posição zero da máquina.
        """
        self.enviar_comando("$H")

    def mover_eixo(
        self,
        eixo: str,
        direcao: int,
        passo: float,
        feed_rate: int
    ) -> None:
        """
        Envia um comando de movimentação jog para um eixo específico.

        Args:
            eixo (str): Eixo a ser movido ('X', 'Y' ou 'Z').
            direcao (int): Direção do movimento (1 para positivo, -1 para negativo).
            passo (float): Distância do movimento em milímetros.
            feed_rate (int): Velocidade do movimento em mm/min.
        """
        distancia = passo * direcao
        comando = f"$J=G91 {eixo.upper()}{distancia:.3f} F{feed_rate}"
        self.enviar_comando(comando)

    def mover_eixos_diagonais(
        self,
        direcao_x: int,
        direcao_y: int,
        passo: float,
        feed_rate: int
    ) -> None:
        """
        Envia um comando de movimentação jog diagonal simultâneo nos eixos X e Y.

        Args:
            direcao_x (int): Direção no eixo X (1 ou -1).
            direcao_y (int): Direção no eixo Y (1 ou -1).
            passo (float): Distância do movimento em milímetros para cada eixo.
            feed_rate (int): Velocidade do movimento em mm/min.
        """
        distancia_x = passo * direcao_x
        distancia_y = passo * direcao_y
        comando = f"$J=G91 X{distancia_x:.3f} Y{distancia_y:.3f} F{feed_rate}"
        self.enviar_comando(comando)

    def zerar_coordenadas(self) -> None:
        """
        Zera as coordenadas de trabalho (Work Position) de todos os eixos.

        Envia o comando G10 L20 P1 X0 Y0 Z0 para definir a posição
        atual como a nova origem do sistema de coordenadas de trabalho.
        """
        self._posicao_trabalho = (0.0, 0.0, 0.0)
        self.enviar_comando("G10 L20 P1 X0 Y0 Z0")

    def zerar_eixo(self, eixo: str) -> None:
        """
        Zera a coordenada de trabalho de um eixo específico.

        Args:
            eixo (str): Eixo a zerar ('X', 'Y' ou 'Z').
        """
        eixo_formatado = eixo.strip().upper()
        x_atual, y_atual, z_atual = self._posicao_trabalho
        if eixo_formatado == "X":
            self._posicao_trabalho = (0.0, y_atual, z_atual)
        elif eixo_formatado == "Y":
            self._posicao_trabalho = (x_atual, 0.0, z_atual)
        elif eixo_formatado == "Z":
            self._posicao_trabalho = (x_atual, y_atual, 0.0)
        self.enviar_comando(f"G10 L20 P1 {eixo_formatado}0")

    def obter_configuracao_area_trabalho(self) -> None:
        """
        Solicita as configurações do GRBL para obter os limites
        da área de trabalho ($130, $131, $132) e todos os parâmetros $$.

        As configurações serão recebidas assincronamente e
        processadas por _processar_resposta.
        """
        if self._enviando_arquivo or self._executando_script:
            return

        self._coletando_configuracoes = True
        self._configuracoes_coletadas = {}
        self._parametros_grbl = {}
        self.enviar_comando("$$")

    def obter_parametros_grbl(self) -> dict:
        """
        Retorna uma cópia do dicionário com os últimos parâmetros lidos do GRBL ($N=V).
        """
        return dict(self._parametros_grbl)

    def gravar_parametro_grbl(self, chave: str, valor: str) -> bool:
        """
        Grava um parâmetro específico no firmware GRBL (ex: '$130=350.000').

        Args:
            chave (str): Código do parâmetro (ex: '$130' ou '130').
            valor (str): Novo valor a gravar.

        Returns:
            bool: True se o comando foi despachado para a porta serial.
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return False

        chave_formatada = chave.strip()
        if not chave_formatada.startswith("$"):
            chave_formatada = f"${chave_formatada}"

        valor_formatado = valor.strip()
        cmd = f"{chave_formatada}={valor_formatado}"
        self.enviar_comando(cmd)
        self._parametros_grbl[chave_formatada] = valor_formatado
        return True

    def enviar_script_gcode(
        self,
        conteudo: str,
        nome: str = "Script",
        callback_conclusao: Optional[callable] = None
    ) -> bool:
        """
        Envia uma sequência de comandos G-code (macro, troca de caneta, etc.)
        com controle de fluxo por janela de bytes e sincronização com o GRBL.

        Remove comentários inline para não sobrecarregar o buffer serial RX (128 bytes)
        e garante que todos os comandos sejam enviados de forma síncrona/gerenciada.

        Args:
            conteudo (str): Conteúdo G-code (múltiplas linhas).
            nome (str): Nome descritivo da rotina/macro para logs.
            callback_conclusao (callable, optional): Função a ser executada quando
                o GRBL concluir fisicamente todos os movimentos (estado IDLE).

        Returns:
            bool: True se o envio foi iniciado com sucesso.
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return False

        if self.esta_enviando():
            self.sinal_erro.emit(
                f"Máquina ocupada — não é possível executar '{nome}' agora."
            )
            return False

        # Expandir macros customizadas referenciadas no script se houver
        if self._gerenciador_macros is not None:
            conteudo = self._gerenciador_macros.expandir_macros_em_gcode(conteudo)

        # Se houver comandos PEN_DOWN, PEN_UP ou PEN_HOP no script, expandir para a posição atual
        if "PEN_DOWN" in conteudo.upper() or "PEN_UP" in conteudo.upper() or "PEN_HOP" in conteudo.upper():
            cid = self.obter_caneta_ativa_id()
            x_atual, y_atual, _ = self.obter_posicao_atual()
            if self._gerenciador_nivelamento is not None:
                z_up, z_down = self._gerenciador_nivelamento.obter_z_up_down(cid)
                if self._gerenciador_nivelamento.esta_dentro_area(x_atual, y_atual):
                    z_down_comp = self._gerenciador_nivelamento.calcular_z_compensado_ponto(cid, x_atual, y_atual)
                else:
                    z_down_comp = z_down
                z_hop_comp = self._gerenciador_nivelamento.calcular_z_hop_ponto(cid, x_atual, y_atual)
            else:
                z_up, z_down = -4.0, 25.0
                z_down_comp = 25.0
                z_hop_comp = 23.0

            linhas_exp = []
            for lin in conteudo.splitlines():
                lin_upper = lin.strip().upper()
                if lin_upper == "PEN_DOWN":
                    linhas_exp.append(f"G1 Z{z_down_comp:.3f} F600")
                elif lin_upper == "PEN_HOP":
                    linhas_exp.append(f"G0 Z{z_hop_comp:.3f} F3000")
                elif lin_upper == "PEN_UP":
                    linhas_exp.append(f"G0 Z{z_up:.3f} F3000")
                else:
                    linhas_exp.append(lin)
            conteudo = "\n".join(linhas_exp)

        # Extrair e limpar linhas G-code
        linhas = []
        for linha in conteudo.splitlines():
            linha_limpa = limpar_linha_gcode(linha)
            if linha_limpa:
                linhas.append(linha_limpa)

        if not linhas:
            if callback_conclusao:
                try:
                    callback_conclusao()
                except Exception as erro:
                    self.sinal_erro.emit(f"Erro no callback: {str(erro)}")
            return True

        self._linhas_pendentes = linhas
        self._mapa_indices_originais = list(range(len(linhas)))
        self._indice_linha_atual = 0
        self._total_linhas_arquivo = len(linhas)
        self._fila_em_voo.clear()
        self._bytes_em_voo = 0
        self._linhas_confirmadas = 0
        self._executando_script = True
        self._enviando_arquivo = False
        self._em_pausa = False
        self._aguardando_ocioso = False
        self._nome_script_atual = nome
        self._callback_conclusao_script = callback_conclusao

        self.sinal_resposta_recebida.emit(
            f"[SISTEMA] Iniciando execução de '{nome}' ({self._total_linhas_arquivo} comandos)..."
        )
        self._despachar_linhas()
        return True

    def enviar_gcode_arquivo(self, conteudo: str) -> None:
        """
        Envia o conteúdo de um arquivo G-code para o GRBL com controle
        de fluxo por janela de bytes.

        Mantém uma fila de linhas em voo (enviadas e ainda não confirmadas
        com 'ok'), respeitando o buffer de recepção do GRBL. O destaque no
        editor segue sempre a linha mais antiga ainda não confirmada — ou
        seja, a linha que a máquina está efetivamente executando.

        Args:
            conteudo (str): Conteúdo completo do arquivo G-code.
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return

        if self.esta_enviando():
            self.sinal_erro.emit("Já existe um envio em andamento.")
            return

        # Expandir macros customizadas referenciadas no G-code (estilo Klipper)
        if self._gerenciador_macros is not None:
            conteudo = self._gerenciador_macros.expandir_macros_em_gcode(conteudo)

        # Expandir comandos de troca de caneta (TROCAR_CANETA_X, PEGAR_CANETA_X, etc.)
        if self._gerenciador_canetas is not None:
            conteudo = self._expandir_comandos_canetas(conteudo)

        # Aplicar compensação inteligente de nivelamento da malha Z e expansão de comandos PEN
        if self._gerenciador_nivelamento is not None:
            caneta_inicial = 1
            if self._gerenciador_canetas and self._gerenciador_canetas.obter_caneta_ativa_id():
                caneta_inicial = self._gerenciador_canetas.obter_caneta_ativa_id()
            conteudo = self._gerenciador_nivelamento.aplicar_nivelamento_gcode(
                conteudo_gcode=conteudo,
                id_caneta_padrao=caneta_inicial
            )

        linhas = []
        mapa_indices = []
        for indice_original, linha in enumerate(conteudo.splitlines()):
            linha_limpa = limpar_linha_gcode(linha)
            if linha_limpa:
                linhas.append(linha_limpa)
                mapa_indices.append(indice_original)

        if not linhas:
            self.sinal_erro.emit("Nenhuma linha G-code válida encontrada.")
            return

        self._linhas_pendentes = linhas
        self._mapa_indices_originais = mapa_indices
        self._indice_linha_atual = 0
        self._total_linhas_arquivo = len(linhas)
        self._fila_em_voo.clear()
        self._bytes_em_voo = 0
        self._linhas_confirmadas = 0
        self._enviando_arquivo = True
        self._executando_script = False
        self._em_pausa = False
        self._aguardando_ocioso = False
        self._callback_conclusao_script = None
        self._nome_script_atual = "Arquivo G-code"
        self.sinal_pausa_alterada.emit(False)

        self.sinal_resposta_recebida.emit(
            f"[SISTEMA] Iniciando envio de {self._total_linhas_arquivo} linhas..."
        )
        self._despachar_linhas()

    def cancelar_envio_arquivo(self) -> None:
        """
        Cancela o envio de arquivo ou script em andamento e envia
        um soft-reset (Ctrl+X) ao GRBL para parar a máquina.
        """
        self._enviando_arquivo = False
        self._executando_script = False
        self._aguardando_ocioso = False
        self._em_pausa = False
        self._linhas_pendentes = []
        self._fila_em_voo.clear()
        self._bytes_em_voo = 0
        self._linhas_confirmadas = 0
        self._callback_conclusao_script = None
        self._nome_script_atual = ""
        self.sinal_pausa_alterada.emit(False)
        self.sinal_linha_enviada.emit(-1)

        if self.esta_conectado():
            try:
                with QMutexLocker(self._mutex_envio):
                    self._porta_serial.write(b"\x18")
            except serial.SerialException:
                pass

        self.sinal_resposta_recebida.emit(
            "[SISTEMA] Execução cancelada."
        )

    def _despachar_linhas(self) -> None:
        """
        Despacha linhas pendentes do arquivo/script enquanto houver espaço na
        janela de envio (buffer RX do GRBL).

        Cada linha enviada entra na fila de linhas em voo; o sinal de
        linha enviada reflete sempre a linha mais antiga aguardando 'ok'.
        """
        while ((self._enviando_arquivo or self._executando_script)
               and not self._em_pausa
               and self._indice_linha_atual < self._total_linhas_arquivo):
            linha = self._linhas_pendentes[self._indice_linha_atual]
            indice_original = self._mapa_indices_originais[self._indice_linha_atual]
            custo_bytes = len(linha.encode("utf-8")) + 1

            if (self._fila_em_voo
                    and self._bytes_em_voo + custo_bytes > self.JANELA_ENVIO_BYTES):
                break

            self._indice_linha_atual += 1
            self._bytes_em_voo += custo_bytes
            self._fila_em_voo.append((indice_original, custo_bytes))
            self._escrever_serial(linha)

        if self._enviando_arquivo and self._fila_em_voo:
            self.sinal_linha_enviada.emit(self._fila_em_voo[0][0])
        elif ((self._enviando_arquivo or self._executando_script)
                and self._linhas_confirmadas >= self._total_linhas_arquivo):
            self._verificar_conclusao_ou_aguardar_idle()

    def _verificar_conclusao_ou_aguardar_idle(self) -> None:
        """
        Verifica se a máquina já concluiu fisicamente todos os movimentos
        (estado IDLE) ou se deve aguardar a conclusão antes de finalizar o envio.
        """
        if self._status_atual == "IDLE":
            self._finalizar_envio()
        else:
            self._aguardando_ocioso = True
            # Força consulta imediata de status
            self._solicitar_status()

    def _finalizar_envio(self) -> None:
        """
        Encerra oficialmente a transmissão do arquivo ou script, restaurando os
        estados internos, disparando callbacks e notificando a interface.
        """
        era_arquivo = self._enviando_arquivo
        era_script = self._executando_script
        nome_script = self._nome_script_atual
        callback = self._callback_conclusao_script

        self._enviando_arquivo = False
        self._executando_script = False
        self._aguardando_ocioso = False
        self._em_pausa = False
        self._fila_em_voo.clear()
        self._bytes_em_voo = 0
        self._callback_conclusao_script = None
        self._nome_script_atual = ""
        self.sinal_pausa_alterada.emit(False)
        self.sinal_linha_enviada.emit(-1)

        # Atualizar caneta ativa no gerenciador após execução do arquivo
        if (self._gerenciador_canetas is not None
                and self._tem_caneta_final_apos_envio):
            self._gerenciador_canetas.definir_caneta_ativa(
                self._caneta_final_apos_envio
            )
            self._tem_caneta_final_apos_envio = False
            self._caneta_final_apos_envio = None

        if callback is not None:
            try:
                callback()
            except Exception as erro:
                self.sinal_erro.emit(f"Erro no callback pós-execução: {str(erro)}")

        if era_arquivo:
            self.sinal_envio_arquivo_concluido.emit()
            self.sinal_resposta_recebida.emit(
                "[SISTEMA] Envio de arquivo concluído!"
            )
        elif era_script:
            self.sinal_resposta_recebida.emit(
                f"[SISTEMA] '{nome_script}' concluído com sucesso!"
            )

    def _interromper_envio_por_erro(self) -> None:
        """
        Aborta a transmissão do arquivo ou script devido a um 'error' do GRBL,
        restaurando os estados internos e a interface.
        """
        era_arquivo = self._enviando_arquivo
        self._enviando_arquivo = False
        self._executando_script = False
        self._aguardando_ocioso = False
        self._em_pausa = False
        self._fila_em_voo.clear()
        self._bytes_em_voo = 0
        self._callback_conclusao_script = None
        self._nome_script_atual = ""
        self.sinal_pausa_alterada.emit(False)
        self.sinal_linha_enviada.emit(-1)

        if era_arquivo:
            self.sinal_envio_arquivo_concluido.emit()
        self.sinal_resposta_recebida.emit(
            "[SISTEMA] Execução interrompida por erro."
        )

    def _expandir_comandos_canetas(self, conteudo: str) -> str:
        """
        Expande comandos de troca de caneta dentro do G-code.

        Rastreia qual caneta está ativa ao longo do arquivo para gerar
        corretamente as sequências de soltar a atual + pegar a nova.

        Comandos reconhecidos (case-insensitive):
            - TROCAR_CANETA_X  — Troca completa (devolve a atual + pega a nova)
            - PEGAR_CANETA_X   — Pega caneta X diretamente
            - SOLTAR_CANETA_X  — Devolve caneta X na baia
            - SOLTAR_CANETA    — Devolve a caneta atualmente ativa

        Args:
            conteudo (str): Conteúdo G-code com possíveis comandos de caneta.

        Returns:
            str: Conteúdo G-code com comandos de caneta expandidos.
        """
        if not conteudo.strip():
            return conteudo

        gc = self._gerenciador_canetas
        # Estado simulado: começa com a caneta real atualmente ativa
        caneta_ativa_simulada = gc.obter_caneta_ativa_id()

        # Patterns para comandos de caneta/estojo (aceita TROCA/TROCAR, PEGA/PEGAR, SOLTA/SOLTAR/GUARDA/GUARDAR/DEVOLVER com CANETA/ESTOJO/SLOT)
        padrao_trocar = re.compile(r'^TROCA[R]?[_\s]?(?:CANETA|ESTOJO|SLOT)[_\s]?(\d{1,2})$', re.IGNORECASE)
        padrao_pegar = re.compile(r'^PEGA[R]?[_\s]?(?:CANETA|ESTOJO|SLOT)[_\s]?(\d{1,2})$', re.IGNORECASE)
        padrao_soltar_id = re.compile(r'^(?:SOLTA[R]?|GUARDA[R]?|DEVOLVER?)[_\s]?(?:CANETA|ESTOJO|SLOT)[_\s]?(\d{1,2})$', re.IGNORECASE)
        padrao_soltar = re.compile(r'^(?:SOLTA[R]?|GUARDA[R]?|DEVOLVER?)[_\s]?(?:CANETA|ESTOJO)?$', re.IGNORECASE)

        linhas_resultado = []
        for linha in conteudo.splitlines():
            linha_limpa = linha.strip()

            # Ignorar linhas vazias e comentários
            if not linha_limpa or linha_limpa.startswith(";"):
                linhas_resultado.append(linha)
                continue

            # Extrair parte antes de comentário inline
            parte_comando = linha_limpa.split(";")[0].strip()

            # --- TROCAR_CANETA_X ---
            match_trocar = padrao_trocar.match(parte_comando)
            if match_trocar:
                novo_id = int(match_trocar.group(1))
                slot_novo = gc.obter_slot(novo_id)
                if not slot_novo:
                    linhas_resultado.append(f"; [ERRO] Slot de caneta {novo_id} não encontrado!")
                    continue

                linhas_resultado.append(f"; >>> TROCAR CANETA → Slot {novo_id} ({slot_novo.nome}) <<<")

                # Se a mesma caneta já está ativa, pular
                if caneta_ativa_simulada == novo_id:
                    linhas_resultado.append(f"; Caneta {novo_id} já está ativa — nenhuma troca necessária")
                else:
                    # Soltar caneta atual se houver
                    if caneta_ativa_simulada is not None and caneta_ativa_simulada > 0:
                        gcode_soltar = gc.gerar_gcode_soltar_caneta(caneta_ativa_simulada)
                        linhas_resultado.append(gcode_soltar)
                        linhas_resultado.append("G4 P0.2")

                    # Pegar nova caneta
                    gcode_pegar = gc.gerar_gcode_pegar_caneta(novo_id)
                    linhas_resultado.append(gcode_pegar)

                    caneta_ativa_simulada = novo_id

                linhas_resultado.append(f"; >>> FIM TROCA CANETA {novo_id} <<<")
                continue

            # --- PEGAR_CANETA_X ---
            match_pegar = padrao_pegar.match(parte_comando)
            if match_pegar:
                id_caneta = int(match_pegar.group(1))
                slot = gc.obter_slot(id_caneta)
                if not slot:
                    linhas_resultado.append(f"; [ERRO] Slot de caneta {id_caneta} não encontrado!")
                    continue

                linhas_resultado.append(f"; >>> PEGAR CANETA {id_caneta} ({slot.nome}) <<<")
                gcode_pegar = gc.gerar_gcode_pegar_caneta(id_caneta)
                linhas_resultado.append(gcode_pegar)
                caneta_ativa_simulada = id_caneta
                linhas_resultado.append(f"; >>> FIM PEGAR CANETA {id_caneta} <<<")
                continue

            # --- SOLTAR_CANETA_X ---
            match_soltar_id = padrao_soltar_id.match(parte_comando)
            if match_soltar_id:
                id_caneta = int(match_soltar_id.group(1))
                slot = gc.obter_slot(id_caneta)
                if not slot:
                    linhas_resultado.append(f"; [ERRO] Slot de caneta {id_caneta} não encontrado!")
                    continue

                linhas_resultado.append(f"; >>> SOLTAR CANETA {id_caneta} ({slot.nome}) <<<")
                gcode_soltar = gc.gerar_gcode_soltar_caneta(id_caneta)
                linhas_resultado.append(gcode_soltar)
                if caneta_ativa_simulada == id_caneta:
                    caneta_ativa_simulada = None
                linhas_resultado.append(f"; >>> FIM SOLTAR CANETA {id_caneta} <<<")
                continue

            # --- SOLTAR_CANETA (sem ID — devolve a ativa) ---
            match_soltar = padrao_soltar.match(parte_comando)
            if match_soltar:
                if caneta_ativa_simulada is not None and caneta_ativa_simulada > 0:
                    slot = gc.obter_slot(caneta_ativa_simulada)
                    nome = slot.nome if slot else "?"
                    linhas_resultado.append(f"; >>> SOLTAR CANETA ATIVA {caneta_ativa_simulada} ({nome}) <<<")
                    gcode_soltar = gc.gerar_gcode_soltar_caneta(caneta_ativa_simulada)
                    linhas_resultado.append(gcode_soltar)
                    caneta_ativa_simulada = None
                    linhas_resultado.append(f"; >>> FIM SOLTAR CANETA <<<")
                else:
                    linhas_resultado.append("; [AVISO] Nenhuma caneta ativa para soltar")
                continue

            # Linha G-code normal — manter inalterada
            linhas_resultado.append(linha)

        # Registrar qual caneta estará ativa após execução completa
        self._caneta_final_apos_envio = caneta_ativa_simulada
        self._tem_caneta_final_apos_envio = True

        return "\n".join(linhas_resultado)

    def _solicitar_status(self) -> None:
        """
        Envia o comando de consulta de status '?' ao GRBL.

        Chamada periodicamente pelo QTimer. O '?' não requer
        newline e não gera 'ok' como resposta.
        """
        if not self.esta_conectado():
            return

        try:
            with QMutexLocker(self._mutex_envio):
                self._porta_serial.write(b"?")
        except serial.SerialException:
            self.desconectar()

    def _processar_resposta(self, linha: str) -> None:
        """
        Processa cada linha recebida do GRBL.

        Identifica o tipo de resposta (status, ok, erro, configuração)
        e emite os sinais correspondentes.

        Args:
            linha (str): Linha de texto recebida da porta serial.
        """
        if linha.startswith("<") and linha.endswith(">"):
            self._parsear_status(linha)
            return

        if self._coletando_configuracoes:
            if linha.startswith("$") and "=" in linha:
                self._parsear_configuracao(linha)
                self.sinal_resposta_recebida.emit(linha)
                return
            elif linha == "ok":
                self._coletando_configuracoes = False
                self._emitir_configuracoes()
                self.sinal_resposta_recebida.emit(linha)
                return
        elif linha.startswith("$") and "=" in linha:
            self._parsear_configuracao(linha)

        self.sinal_resposta_recebida.emit(linha)

        if linha == "ok":
            if (self._enviando_arquivo or self._executando_script) and self._fila_em_voo:
                _indice, custo_bytes = self._fila_em_voo.popleft()
                self._bytes_em_voo = max(0, self._bytes_em_voo - custo_bytes)
                self._linhas_confirmadas += 1
                if self._enviando_arquivo:
                    self.sinal_progresso_envio.emit(
                        self._linhas_confirmadas,
                        self._total_linhas_arquivo
                    )
                if self._linhas_confirmadas >= self._total_linhas_arquivo:
                    self._verificar_conclusao_ou_aguardar_idle()
                else:
                    self._despachar_linhas()

        elif linha.startswith("error:"):
            self.sinal_erro.emit(f"GRBL: {linha}")
            if self._enviando_arquivo or self._executando_script:
                self._interromper_envio_por_erro()

        elif linha.startswith("ALARM:"):
            self.sinal_erro.emit(f"GRBL: {linha}")
            self.sinal_status_atualizado.emit("Alarm")

    def _parsear_status(self, resposta_status: str) -> None:
        """
        Parseia a resposta de status do GRBL no formato
        <Status|MPos:X,Y,Z|...> ou <Status|WPos:X,Y,Z|WCO:...>.

        O DRO exibe sempre a POSIÇÃO DE TRABALHO (WPos). Quando o
        relatório traz apenas MPos, ela é convertida subtraindo o
        último WCO (offset de trabalho) conhecido. Assim, o zeramento
        por eixo (G10 L20) reflete imediatamente no visor.

        Args:
            resposta_status (str): String de status crua do GRBL.
        """
        try:
            conteudo = resposta_status.strip("<>")
            partes = conteudo.split("|")

            status = partes[0] if partes else "Desconhecido"
            self._status_atual = status.strip().upper()

            pos_mpos = None
            pos_wpos = None

            for parte in partes[1:]:
                if parte.startswith("MPos:"):
                    valores = parte.split(":")[1].split(",")
                    if len(valores) >= 3:
                        pos_mpos = (
                            float(valores[0]),
                            float(valores[1]),
                            float(valores[2])
                        )
                elif parte.startswith("WPos:"):
                    valores = parte.split(":")[1].split(",")
                    if len(valores) >= 3:
                        pos_wpos = (
                            float(valores[0]),
                            float(valores[1]),
                            float(valores[2])
                        )
                elif parte.startswith("WCO:"):
                    valores = parte.split(":")[1].split(",")
                    if len(valores) >= 3:
                        self._wco_x = float(valores[0])
                        self._wco_y = float(valores[1])
                        self._wco_z = float(valores[2])

            if pos_wpos is None and pos_mpos is not None:
                pos_wpos = (
                    round(pos_mpos[0] - self._wco_x, 3),
                    round(pos_mpos[1] - self._wco_y, 3),
                    round(pos_mpos[2] - self._wco_z, 3)
                )

            if pos_wpos is not None:
                self._posicao_trabalho = (pos_wpos[0], pos_wpos[1], pos_wpos[2])
                self.sinal_posicao_atualizada.emit(*pos_wpos)

            self.sinal_status_atualizado.emit(status)

            # Se estava aguardando conclusão física e GRBL retornou para IDLE
            if self._aguardando_ocioso and self._status_atual == "IDLE":
                self._aguardando_ocioso = False
                self._finalizar_envio()
            elif self._aguardando_ocioso and self._status_atual == "ALARM":
                self._aguardando_ocioso = False
                self._interromper_envio_por_erro()

            # Fim do ciclo de homing: zera as coordenadas de trabalho para
            # que a posição de home seja 0,0,0 e a máquina siga para +.
            if (self._estado_anterior == "Home"
                    and status not in ("Home", "Alarm")):
                self.zerar_coordenadas()

            self._estado_anterior = status

        except (ValueError, IndexError):
            pass

    def _parsear_configuracao(self, linha_configuracao: str) -> None:
        """
        Parseia uma linha de configuração do GRBL no formato $N=V.

        Armazena todos os parâmetros recebidos em _parametros_grbl
        e os limites de área em _configuracoes_coletadas.

        Args:
            linha_configuracao (str): Linha de configuração (ex: '$130=300.000').
        """
        try:
            if "=" in linha_configuracao:
                partes = linha_configuracao.split("=", 1)
                if len(partes) == 2:
                    chave = partes[0].strip()
                    valor_bruto = partes[1].strip()
                    # Extrai valor limpo sem comentários inline como "(x max travel)"
                    valor_limpo = valor_bruto.split(" ")[0].split("(")[0].strip()

                    self._parametros_grbl[chave] = valor_limpo

                    if chave in ("$130", "$131", "$132"):
                        try:
                            self._configuracoes_coletadas[chave] = float(valor_limpo)
                        except ValueError:
                            pass
        except Exception:
            pass

    def _emitir_configuracoes(self) -> None:
        """
        Emite os sinais com os limites da área de trabalho e
        o mapa completo de parâmetros do firmware GRBL.
        """
        try:
            limite_x = float(self._configuracoes_coletadas.get("$130", 330.0))
        except (ValueError, TypeError):
            limite_x = 330.0

        try:
            limite_y = float(self._configuracoes_coletadas.get("$131", 327.7))
        except (ValueError, TypeError):
            limite_y = 327.7

        try:
            limite_z = float(self._configuracoes_coletadas.get("$132", 50.0))
        except (ValueError, TypeError):
            limite_z = 50.0

        self.sinal_configuracao_recebida.emit(limite_x, limite_y, limite_z)
        self.sinal_parametros_grbl_recebidos.emit(dict(self._parametros_grbl))
        self.sinal_resposta_recebida.emit(
            f"[SISTEMA] Configurações GRBL ($$) recebidas ({len(self._parametros_grbl)} parâmetros). "
            f"Área útil: X={limite_x}mm, Y={limite_y}mm, Z={limite_z}mm"
        )

"""
Módulo de lógica de negócio para o controle da máquina.

Contém as funções e classes responsáveis pela comunicação
e controle dos motores e atuadores da máquina AXIS via protocolo GRBL.
"""

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, Signal, QThread, QTimer, QMutex, QMutexLocker


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
                    self.msleep(10)
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
    sinal_envio_arquivo_concluido = Signal()
    sinal_progresso_envio = Signal(int, int)
    sinal_linha_enviada = Signal(int)
    sinal_pausa_alterada = Signal(bool)

    def __init__(self) -> None:
        """
        Inicializa o controlador GRBL sem conexão ativa.
        """
        super().__init__()
        self._porta_serial = None
        self._leitor_serial = None
        self._timer_status = QTimer(self)
        self._timer_status.timeout.connect(self._solicitar_status)
        self._mutex_envio = QMutex()
        self._conectado = False
        self._enviando_arquivo = False
        self._em_pausa = False
        self._linhas_pendentes = []
        self._mapa_indices_originais = []
        self._indice_linha_atual = 0
        self._total_linhas_arquivo = 0
        self._aguardando_ok = False
        self._coletando_configuracoes = False
        self._configuracoes_coletadas = {}

    def listar_portas_disponiveis(self) -> list:
        """
        Lista todas as portas seriais disponíveis no sistema.

        Returns:
            list: Lista de strings com as portas disponíveis (ex: ['/dev/ttyUSB0', 'COM3']).
        """
        portas = serial.tools.list_ports.comports()
        lista_portas = [porta.device for porta in portas]
        return lista_portas

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
        self._em_pausa = False
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

    def enviar_comando(self, comando: str) -> None:
        """
        Envia um comando de texto para o GRBL via serial.

        O comando é codificado em UTF-8 e terminado com newline.
        A resposta será recebida assincronamente pelo LeitorSerial.

        Args:
            comando (str): Comando G-code ou GRBL a ser enviado.
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return

        try:
            with QMutexLocker(self._mutex_envio):
                comando_limpo = comando.strip()
                self._porta_serial.write(
                    (comando_limpo + "\n").encode("utf-8")
                )
                self.sinal_resposta_recebida.emit(f"> {comando_limpo}")
        except serial.SerialException as erro:
            self.sinal_erro.emit(f"Erro ao enviar comando: {str(erro)}")
            self.desconectar()

    def esta_enviando(self) -> bool:
        """
        Verifica se há um envio de arquivo G-code em andamento.

        Returns:
            bool: True se estiver transmitindo arquivo.
        """
        return self._enviando_arquivo

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
        Cancela qualquer transmissão de arquivo em andamento.
        """
        self._enviando_arquivo = False
        self._em_pausa = False
        self._linhas_pendentes = []
        self._aguardando_ok = False
        self.sinal_pausa_alterada.emit(False)
        self.sinal_linha_enviada.emit(-1)

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

        if not self._aguardando_ok:
            self._enviar_proxima_linha()

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
        comando = f"$J=G91 {eixo}{distancia:.3f} F{feed_rate}"
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
        self.enviar_comando("G10 L20 P1 X0 Y0 Z0")

    def zerar_eixo(self, eixo: str) -> None:
        """
        Zera a coordenada de trabalho de um eixo específico.

        Args:
            eixo (str): Eixo a zerar ('X', 'Y' ou 'Z').
        """
        eixo_formatado = eixo.strip().upper()
        self.enviar_comando(f"G10 L20 P1 {eixo_formatado}0")

    def obter_configuracao_area_trabalho(self) -> None:
        """
        Solicita as configurações do GRBL para obter os limites
        da área de trabalho ($130, $131, $132).

        As configurações serão recebidas assincronamente e
        processadas por _processar_resposta.
        """
        self._coletando_configuracoes = True
        self._configuracoes_coletadas = {}
        self.enviar_comando("$$")

    def enviar_gcode_arquivo(self, conteudo: str) -> None:
        """
        Envia o conteúdo de um arquivo G-code linha a linha para o GRBL.

        Cada linha é enviada após receber 'ok' da linha anterior,
        evitando overflow no buffer do GRBL.

        Args:
            conteudo (str): Conteúdo completo do arquivo G-code.
        """
        if not self.esta_conectado():
            self.sinal_erro.emit("Não conectado à máquina.")
            return

        if self._enviando_arquivo:
            self.sinal_erro.emit("Já existe um envio em andamento.")
            return

        linhas = []
        mapa_indices = []
        for indice_original, linha in enumerate(conteudo.strip().split("\n")):
            linha_limpa = linha.strip()
            if linha_limpa and not linha_limpa.startswith(";"):
                linhas.append(linha_limpa)
                mapa_indices.append(indice_original)

        if not linhas:
            self.sinal_erro.emit("Nenhuma linha G-code válida encontrada.")
            return

        self._linhas_pendentes = linhas
        self._mapa_indices_originais = mapa_indices
        self._indice_linha_atual = 0
        self._total_linhas_arquivo = len(linhas)
        self._enviando_arquivo = True
        self._em_pausa = False
        self._aguardando_ok = False
        self.sinal_pausa_alterada.emit(False)

        self.sinal_resposta_recebida.emit(
            f"[SISTEMA] Iniciando envio de {self._total_linhas_arquivo} linhas..."
        )
        self._enviar_proxima_linha()

    def cancelar_envio_arquivo(self) -> None:
        """
        Cancela o envio de arquivo em andamento e envia
        um soft-reset (Ctrl+X) ao GRBL para parar a máquina.
        """
        self._enviando_arquivo = False
        self._em_pausa = False
        self._linhas_pendentes = []
        self._aguardando_ok = False
        self.sinal_pausa_alterada.emit(False)
        self.sinal_linha_enviada.emit(-1)

        if self.esta_conectado():
            try:
                with QMutexLocker(self._mutex_envio):
                    self._porta_serial.write(b"\x18")
            except serial.SerialException:
                pass

        self.sinal_resposta_recebida.emit(
            "[SISTEMA] Envio de arquivo cancelado."
        )

    def _enviar_proxima_linha(self) -> None:
        """
        Envia a próxima linha pendente do arquivo G-code.

        Chamada internamente após cada 'ok' recebido do GRBL.
        Não envia se estiver em estado de pausa.
        """
        if not self._enviando_arquivo or self._em_pausa:
            return

        if self._indice_linha_atual >= self._total_linhas_arquivo:
            self._enviando_arquivo = False
            self._em_pausa = False
            self.sinal_pausa_alterada.emit(False)
            self.sinal_linha_enviada.emit(-1)
            self.sinal_envio_arquivo_concluido.emit()
            self.sinal_resposta_recebida.emit(
                "[SISTEMA] Envio de arquivo concluído!"
            )
            return

        linha = self._linhas_pendentes[self._indice_linha_atual]
        indice_original = self._mapa_indices_originais[self._indice_linha_atual]
        self._aguardando_ok = True
        self.sinal_linha_enviada.emit(indice_original)
        self.enviar_comando(linha)
        self.sinal_progresso_envio.emit(
            self._indice_linha_atual + 1,
            self._total_linhas_arquivo
        )

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
            if linha.startswith("$"):
                self._parsear_configuracao(linha)
                return
            elif linha == "ok":
                self._coletando_configuracoes = False
                self._emitir_configuracoes()

        self.sinal_resposta_recebida.emit(linha)

        if linha == "ok":
            if self._enviando_arquivo and self._aguardando_ok:
                self._aguardando_ok = False
                self._indice_linha_atual += 1
                self._enviar_proxima_linha()

        elif linha.startswith("error:"):
            self.sinal_erro.emit(f"GRBL: {linha}")
            if self._enviando_arquivo:
                self._enviando_arquivo = False
                self.sinal_resposta_recebida.emit(
                    "[SISTEMA] Envio interrompido por erro."
                )

        elif linha.startswith("ALARM:"):
            self.sinal_erro.emit(f"GRBL: {linha}")
            self.sinal_status_atualizado.emit("Alarm")

    def _parsear_status(self, resposta_status: str) -> None:
        """
        Parseia a resposta de status do GRBL no formato
        <Status|MPos:X,Y,Z|...> ou <Status|WPos:X,Y,Z|...>.

        Args:
            resposta_status (str): String de status crua do GRBL.
        """
        try:
            conteudo = resposta_status.strip("<>")
            partes = conteudo.split("|")

            status = partes[0] if partes else "Desconhecido"
            self.sinal_status_atualizado.emit(status)

            for parte in partes[1:]:
                if parte.startswith("MPos:") or parte.startswith("WPos:"):
                    coordenadas_texto = parte.split(":")[1]
                    valores = coordenadas_texto.split(",")
                    if len(valores) >= 3:
                        posicao_x = float(valores[0])
                        posicao_y = float(valores[1])
                        posicao_z = float(valores[2])
                        self.sinal_posicao_atualizada.emit(
                            posicao_x, posicao_y, posicao_z
                        )
        except (ValueError, IndexError):
            pass

    def _parsear_configuracao(self, linha_configuracao: str) -> None:
        """
        Parseia uma linha de configuração do GRBL no formato $N=V.

        Armazena os valores relevantes ($130, $131, $132) para
        emissão posterior.

        Args:
            linha_configuracao (str): Linha de configuração (ex: '$130=300.000').
        """
        try:
            partes = linha_configuracao.split("=")
            if len(partes) == 2:
                chave = partes[0].strip()
                valor = partes[1].strip()
                if chave in ("$130", "$131", "$132"):
                    self._configuracoes_coletadas[chave] = float(valor)
        except ValueError:
            pass

    def _emitir_configuracoes(self) -> None:
        """
        Emite o sinal com os limites da área de trabalho
        após coletar as configurações $130, $131, $132.
        """
        limite_x = self._configuracoes_coletadas.get("$130", 0.0)
        limite_y = self._configuracoes_coletadas.get("$131", 0.0)
        limite_z = self._configuracoes_coletadas.get("$132", 0.0)

        self.sinal_configuracao_recebida.emit(limite_x, limite_y, limite_z)
        self.sinal_resposta_recebida.emit(
            f"[SISTEMA] Área de trabalho: "
            f"X={limite_x}mm, Y={limite_y}mm, Z={limite_z}mm"
        )

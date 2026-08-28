# Documentação de Manutenção: logica_controle_da_maquina.py

* **Objetivo do Script:** 
O arquivo `logica_controle_da_maquina.py` implementa a camada de comunicação e controle com o hardware CNC/Plotter rodando firmware GRBL (v0.9, v1.1 e GrblHAL). Ele gerencia a conexão serial assíncrona, streaming de arquivos e rotinas G-code linha a linha (com controle de buffer de caracteres do GRBL), leitura do relatório de status em tempo real (`?`), gerenciamento de alarmes/erros, cálculo de progresso e expansão automática de macros, trocas de canetas e interpolação Z de nivelamento.

* **Dependências:** 
  * `serial` (`pyserial` - comunicação serial RS232/USB)
  * `serial.tools.list_ports` (descoberta automática de portas COM/tty)
  * `PySide6.QtCore` (`QObject`, `Signal`, `QTimer`, `QThread`)
  * `typing` (`Optional`, `Tuple`, `List`, `Dict`, `Callable`)
  * `re`, `time`, `os` (nativos do Python)

* **Guia de Alteração:** 
  * **Ajuste de taxa de polling de status:** O temporizador de consulta periódica (`?`) é configurado em `_iniciar_polling_status()`. Por padrão opera em 100-200ms.
  * **Tamanho do buffer de caracteres:** O GRBL padrão possui buffer serial RX de 128 bytes. O envio contínuo em `_gerenciar_buffer_envio()` respeita esse limite para evitar overflow.
  * **Tratamento de respostas e alarmes:** Para adicionar tratamento a novas mensagens de erro ou códigos de alarme do firmware, altere `_processar_resposta()`.
  * **Integração de filtros de G-code:** A injeção de compensação de nivelamento e expansão de macros ocorre antes da fila de envio em `enviar_script_gcode()`.

* **Possíveis Falhas:** 
  * **SerialException (Porta Ocupada ou Negada):** Ocorre se outro software (ex: Universal Gcode Sender, Cura, terminal serial) estiver utilizando a porta. O método `conectar()` trata a exceção e emite sinal de falha.
  * **Buffer Overflow / Perda de Caracteres:** Caso comandos longos sejam enviados sem aguardar `ok`, o GRBL responderá com erro. O algoritmo de contagem de bytes em trânsito previne essa situação.
  * **Desconexão física durante gravação:** Caso o cabo seja desconectado durante um trabalho, a thread de monitoramento detecta a perda e emite sinal de desconexão com interrupção segura do fluxo.

# Documentação de Manutenção: aba_controle_da_maquina.py

* **Objetivo do Script:** 
O arquivo `aba_controle_da_maquina.py` implementa a interface gráfica principal para o controle da máquina CNC/Laser via GRBL. Seu layout é estruturado e inspirado no *Universal Gcode Sender (UGS)*, contendo:
  1. **Barra Superior:** Conexão serial com detecção de portas, indicador LED e barra unificada de execução de trabalho (Play ▶, Pause ⏸, Stop ⏹, Home 🏠, Desbloquear 🔓, Reset 🔄) com barra de progresso.
  2. **Painel Esquerdo:** Visor Digital de Leitura de Coordenadas (**DRO - Digital Read Out**) com badge de estado dinâmico (IDLE, RUN, HOLD, ALARM), botões de zeramento individual ($X_0, Y_0, Z_0$) e visor LCD ciano de alto contraste; e **Jog Controller** com matriz 4x3 perfeitamente alinhada (movimentos ortogonais, diagonais $\nwarrow, \nearrow, \swarrow, \searrow$, e eixo Z), seletores e inputs independentes para passos $XY$ e $Z$ com classe `SpinBoxPassoAdaptativo` (que decrementa/incrementa em $0.1$ abaixo de $1.0$ e $1.0$ acima de $1.0$) e controle de velocidade (*feed rate*).
  3. **Painel Central:** Editor de G-code com numeração de linhas, realce da linha em execução em tempo real, detecção de modificações pendentes com bloqueio de envio sem salvar, botão dedicado **💾 Salvar**, e Console Serial com comandos manuais.
  4. **Painel Direito:** Gerenciador de Arquivos G-code para seleção de diretórios e carregamento direto no editor via duplo clique no item da lista.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets` - classes `QWidget`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`, `QLabel`, `QPushButton`, `QComboBox`, `QLineEdit`, `QTextEdit`, `QListWidget`, `QFrame`, `QGroupBox`, `QDoubleSpinBox`, `QSpinBox`, `QFileDialog`, `QSplitter`, `QSizePolicy`, `QProgressBar`, `QButtonGroup`, `QMessageBox`)
  * `PySide6` (módulos `PySide6.QtCore` - classes `Qt`, `Slot`, `QSize`)
  * `PySide6` (módulos `PySide6.QtGui` - classes `QFont`, `QColor`)
  * `os`, `typing` (nativos do Python)
  * `resources.controle_da_maquina.logica_controle_da_maquina` (módulo interno - classe `ControladorGrbl`)
  * `resources.controle_da_maquina.editor_gcode` (módulo interno - classe `EditorGcode`)

* **Guia de Alteração:** 
  * **Ajuste da dinâmica do SpinBox adaptativo:** Edite a classe `SpinBoxPassoAdaptativo` e seu método `stepBy()`.
  * **Passos independentes XY e Z:** O input de XY é `self.input_passo_xy` e o de Z é `self.input_passo_z`. O método `_mover_eixo()` chaveia entre eles conforme o eixo.
  * **Validação de salvamento antes do envio:** A lógica está centralizada em `_ao_alterar_texto_editor()`, `_salvar_gcode_editor()` e a checagem em `_iniciar_execucao_trabalho()`.
  * **Carregamento por duplo clique:** Configurado pelo sinal `self.lista_arquivos.itemDoubleClicked.connect(self._carregar_arquivo_selecionado_no_editor)`.

* **Possíveis Falhas:** 
  * **Envio bloqueado por arquivo modificado:** Se o botão Iniciar não disparar o envio, verifique se há alterações não salvas no editor (indicativo em amarelo). O usuário deve salvar clicando em `💾 Salvar`.
  * **Erro de permissão ao salvar:** Se o arquivo estiver protegido contra escrita no sistema de arquivos, uma mensagem de erro será registrada no console serial via tratamento `try/except OSError`.
  * **Layout desalinhado:** Os painéis utilizam `QSplitter(Qt.Orientation.Horizontal)`. Certifique-se de que os tamanhos mínimos (`setMinimumWidth`) e fatores de estiramento (`setStretchFactor`) sejam preservados.

---

# Documentação de Manutenção: logica_controle_da_maquina.py

* **Objetivo do Script:** 
O arquivo `logica_controle_da_maquina.py` contém a classe `ControladorGrbl` e a classe `LeitorSerial`, responsáveis pela comunicação assíncrona bidirecional via protocolo GRBL pela porta serial. Gerencia:
  * Conexão e desconexão segura.
  * Leitura e envio de comandos em tempo real e de configuração.
  * Controle de fluxo linha a linha para envio de programas G-code com suporte a Pausa (*Feed Hold* `!`), Retomada (*Cycle Start* `~`) e Cancelamento/Soft-Reset (`\x18`).
  * Movimentação manual (Jog) ortogonal e composta/diagonal (`$J=G91 X... Y... F...`).
  * Zeramento de coordenadas global e por eixo individual (`G10 L20 P1`).
  * Ciclos de Homing (`$H`) e desbloqueio de alarme (`$X`).

* **Dependências:** 
  * `serial` (`pyserial` - comunicação serial)
  * `serial.tools.list_ports` (`pyserial` - listagem de portas)
  * `PySide6` (módulo `PySide6.QtCore` - classes `QObject`, `Signal`, `QThread`, `QTimer`, `QMutex`, `QMutexLocker`)

* **Guia de Alteração:** 
  * **Adicionar novos comandos de controle de fluxo:** Utilize os métodos `pausar_envio_arquivo()`, `retomar_envio_arquivo()`, `alternar_pausa()` e `cancelar_envio_arquivo()`.
  * **Modificar polling de status em tempo real:** Altere o intervalo do timer `self._timer_status.start(250)` no método `conectar()`.
  * **Adicionar comandos GRBL específicos:** Crie métodos públicos dedicados que chamem `enviar_comando()`.
  * **Adicionar novos sinais para a interface:** Declare instâncias de `Signal(...)` na definição da classe `ControladorGrbl` e emita com `.emit(...)`.

* **Possíveis Falhas:** 
  * **Máquina travada em ALARM:** O GRBL entra em estado de alarme após homing ou acionamento de limites. Utilize o método `desbloquear_maquina()` (comando `$X`) ou o botão correspondente na interface.
  * **Timeout ou travamento de envio:** Se o firmware parar de responder com `ok`, o envio pode pausar. O método `reiniciar_grbl()` envia soft-reset (`\x18`) e restabelece a fila de transmissão.
  * **Buffer Overflow:** O controle de envio aguarda confirmação `ok` antes de despachar a próxima linha pendente em `_enviar_proxima_linha()`, prevenindo overflow no buffer do microcontrolador.

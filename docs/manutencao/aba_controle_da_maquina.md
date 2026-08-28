# Documentação de Manutenção: aba_controle_da_maquina.py

* **Objetivo do Script:** 
O arquivo `aba_controle_da_maquina.py` implementa a interface gráfica principal para o controle da plotter AXIS via GRBL com visual moderno e profissional (Dark Slate Theme). Seu layout é composto por:
  1. **Barra Superior:** Conexão serial com detecção de portas, indicador LED, barra unificada de execução de trabalho (Play ▶, Pause ⏸, Stop ⏹, Home 🏠, Desbloquear 🔓, Reset 🔄) e barra de progresso.
  2. **Painel Esquerdo:**
     - **Visor Digital de Coordenadas (DRO):** Leitura cristalina dos eixos $X, Y, Z$, badge de estado dinâmico (IDLE, RUN, HOLD, ALARM), botões de zeramento individual ($X_0, Y_0, Z_0$) e botão *Zerar XYZ*.
     - **Indicador de Caneta Ativa & Troca Rápida:** Exibe a cor e número da caneta engatada no cabeçote com seletor rápido para troca entre as 10 cores, botão *Devolver*, e ações rápidas de caneta: *Abaixar Caneta (PEN_DOWN)*, *Salto / Hop (PEN_HOP)* e *Levantar Caneta (PEN_UP)*.
     - **Jog Controller:** Matriz 4x3 (movimentos ortogonais, diagonais $\nwarrow, \nearrow, \swarrow, \searrow$, e eixo Z), seletores de passos independentes adaptativos e controle de velocidade (*feed rate*).
  3. **Painel Central:**
     - **Visualizador 2D da Máquina em Tempo Real (`Visualizador2DMaquina`):** Canvas interativo com mesa milimétrica, réguas, posições dos 10 slots de caneta, marcador do cabeçote em movimento ao vivo, pré-visualização de G-code e controles de zoom e centralização.
     - **Abas Inferiores:** Editor de G-code com numeração de linhas e destaque da linha em envio; e Console Serial bidirecional com comandos manuais.
  4. **Painel Direito:** Gerenciador de Arquivos G-code com seleção de pastas e carregamento por duplo clique no item da lista.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`)
  * `os`, `typing`
  * `resources.controle_da_maquina.logica_controle_da_maquina` (`ControladorGrbl`)
  * `resources.controle_da_maquina.gerenciador_area_desenho` (`GerenciadorAreaDesenho`)
  * `resources.controle_da_maquina.gerenciador_nivelamento` (`GerenciadorNivelamento`)
  * `resources.macros.logica_macros` (`GerenciadorMacros`)
  * `resources.controle_da_maquina.visualizador_2d` (`Visualizador2DMaquina`)
  * `resources.controle_da_maquina.editor_gcode` (`EditorGcode`)
  * `resources.estilo.tema_escuro` (`ESTILO_CARD_PADRAO`)

* **Guia de Alteração:** 
  * **Ajuste de sensibilidade do passo:** Edite `SpinBoxPassoAdaptativo`.
  * **Preview 2D de G-code:** Ao alterar ou carregar código no editor, `self.visualizador_2d.canvas.carregar_gcode_preview()` é chamado automaticamente.
  * **Atualização de posição no canvas:** Os sinais `sinal_posicao_atualizada` do controlador GRBL atualizam simultaneamente o DRO e o cabeçote no visualizador 2D.
  * **Botões de Macros Rápidas:** Novos botões de macro podem ser adicionados em `_criar_painel_macros_rapidas()` ou via gerenciador de macros.

* **Possíveis Falhas:** 
  * **Porta serial ocupada ou inacessível:** Se outra aplicação estiver com a porta serial aberta (ou se faltar permissão no Linux tipo grupo `dialout`), a conexão falhará. O sistema exibirá o indicador LED em vermelho com status desconectado.
  * **Comando enviado em estado de Alarme ($X):** Caso a máquina atinja um fim de curso físico ou seja ligada sem homing, o GRBL entrará em estado `ALARM`. O usuário deve clicar em `🔓 Desbloquear` ou `🏠 Home` para liberar o buffer de comandos.
  * **Travamento por desconexão física do cabo USB durante streaming:** O controlador detecta perda de sinal da porta e interrompe o envio com timeout sem travar a interface gráfica.

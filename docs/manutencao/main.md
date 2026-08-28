# Documentação de Manutenção: main.py

* **Objetivo do Script:** 
O arquivo `main.py` serve como o orquestrador do programa. Ele inicializa a aplicação PySide6, aplica o tema escuro profissional (`ESTILO_GLOBAL`), instancia os controladores compartilhados de hardware e ferramentas (`ControladorGrbl`, `GerenciadorCanetas`, `GerenciadorMacros`), define a janela principal com navegação por abas (`QTabWidget`), registra os módulos de cada aba e inicia o laço de eventos da interface gráfica.

* **Estrutura de Abas:** 
  1. `🎛️ Controle da Máquina` (`AbaControleDaMaquina`) - Painel operacional, DRO, Jog, visualizador 2D, indicador de caneta e botões de macros rápidas.
  2. `🖼️ Processamento de Imagem` (`AbaProcessamentoDeImagem`)
  3. `📐 Conversão de SVG` (`AbaConversaoDeSvg`)
  4. `⚙️ Conversão de Gcode` (`AbaConversaoDeGcode`)
  5. `⚙️ Configurações` (`AbaConfiguracoes`) - Gerenciamento e calibração das 10 canetas com editor de G-code livre, biblioteca de macros e parâmetros do firmware GRBL.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets` - classes `QApplication`, `QMainWindow`, `QTabWidget`)
  * `sys` (nativo do Python)
  * `resources` (exporta: `AbaControleDaMaquina`, `AbaConfiguracoes`, `AbaProcessamentoDeImagem`, `AbaConversaoDeSvg`, `AbaConversaoDeGcode`)
  * `resources.controle_da_maquina.logica_controle_da_maquina` (`ControladorGrbl`)
  * `resources.controle_da_maquina.gerenciador_canetas` (`GerenciadorCanetas`)
  * `resources.controle_da_maquina.gerenciador_area_desenho` (`GerenciadorAreaDesenho`)
  * `resources.controle_da_maquina.gerenciador_nivelamento` (`GerenciadorNivelamento`)
  * `resources.macros.logica_macros` (`GerenciadorMacros`)
  * `resources.estilo` (`ESTILO_GLOBAL`)

* **Guia de Alteração:** 
  * **Adicionar novas abas:** Instancie o widget da nova aba e adicione-o na lista `lista_de_abas` dentro da função `iniciar_interface_grafica()`.
  * **Controladores compartilhados:** Caso uma nova aba necessite de acesso ao controlador serial GRBL, gerenciador de canetas ou macros, passe a instância correspondente (`controlador_grbl`, `gerenciador_canetas`, `gerenciador_nivelamento`, etc.) no construtor da aba.
  * **Dimensões e tema da janela:** As dimensões iniciais e limites mínimos de resolução são definidos em `iniciar_interface_grafica()`. O estilo visual global é aplicado via `aplicativo.setStyleSheet(ESTILO_GLOBAL)`.

* **Possíveis Falhas:** 
  * **Falha de inicialização gráfica:** Se o Qt não inicializar, verifique se as dependências do `PySide6` estão instaladas no ambiente virtual (`pip install -r requirements.txt`).
  * **Erro ao instanciar controladores:** Falha de leitura de arquivos JSON em `src/config/` pode ocorrer se permissões de disco estiverem bloqueadas. Os gerenciadores possuem fallbacks com configurações padrão.
  * **Incompatibilidade de dependências circulares:** Garanta que novos módulos importem classes diretamente de seus pacotes específicos ou através do `src/resources/__init__.py`.

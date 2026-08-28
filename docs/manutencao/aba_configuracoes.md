# Documentação de Manutenção: aba_configuracoes.py

* **Objetivo do Script:** 
O arquivo `aba_configuracoes.py` centraliza todas as configurações da máquina, do sistema de troca de ferramentas (10 canetas) e da biblioteca de macros personalizadas.

* **Sub-Abas de Configuração:** 
  1. **Troca de Canetas (10 Cores) & Editor G-code:**
     - Calibração física de posições de baia ($X, Y, Z, Z_{seguro}$).
     - Seletor de cores em tempo real (`QColorDialog`).
     - **Editor completo de G-code livre** para o script de pegar (`macro_pegar`) e soltar (`macro_soltar`) de cada uma das 10 canetas.
     - Botões para restaurar templates padrões e testar rotinas na máquina.
  2. **Área de Desenho:**
     - Configuração direta das coordenadas delimitadoras da área útil ($X_{inicio}, Y_{inicio}, X_{fim}, Y_{fim}$).
     - Sincronização em tempo real com o mapa 2D e a malha de calibração.
  3. **Calibrar Z-Offset das Canetas (Nivelamento de Mesa por Software):**
     - Geração dinâmica de malha com linhas horizontais e pontos equidistantes configuráveis ($2 \dots 20$).
     - Calibração de ponto individual para as 10 canetas.
     - **Importação & Exportação de Offsets Calibrados:** Botões dedicados para importar backups/arquivos JSON de calibração prévia de todas as canetas sem perda de dados e exportar backups das malhas.
     - Visualizador 2D interativo com linhas delimitadoras, nós com valores de $Z$ e posição do cabeçote.
     - Botão de **Teste de Ponto** com traço $X+/X-$ e avanço passo a passo.
     - **Controle Manual (Joystick / Jog)** integrado para movimentação livre da máquina ($X, Y$, diagonais, $Z$), seletores rápidos de passos e velocidade ($Feed$), facilitando o teste contínuo do traçado.
     - Aplicação de **Interpolação Bilinear 2D** no envio de G-code para compensação dinâmica contínua de $Z$.
  4. **Biblioteca de Macros G-code:**
     - Criação, edição, exclusão e teste de macros personalizadas.
     - Persistência em `config/macros_usuario.json`.
  5. **Parâmetros do Firmware GRBL:**
     - Leitura e exibição dos limites reais de curso ($130, $131, $132) e envio de `$$.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`)
  * `resources.controle_da_maquina.logica_controle_da_maquina` (`ControladorGrbl`)
  * `resources.controle_da_maquina.gerenciador_canetas` (`GerenciadorCanetas`, `SlotCaneta`)
  * `resources.controle_da_maquina.gerenciador_area_desenho` (`GerenciadorAreaDesenho`, `ConfiguracaoAreaDesenho`)
  * `resources.controle_da_maquina.gerenciador_nivelamento` (`GerenciadorNivelamento`, `MalhaCaneta`, `PontoMalha`)
  * `resources.configuracoes.painel_calibracao_zoffset` (`PainelCalibracaoZOffset`, `VisualizadorMalhaNivelamento`)
  * `resources.macros.logica_macros` (`GerenciadorMacros`, `MacroGcode`)
  * `resources.configuracoes.dicionario_grbl` (`DICIONARIO_PARAMETROS_GRBL`, `obter_info_parametro`)
  * `resources.estilo.tema_escuro` (`ESTILO_CARD_PADRAO`)

* **Guia de Alteração:** 
  * **Adicionar novas sub-abas:** Crie um novo widget de painel e adicione-o ao `QTabWidget` em `AbaConfiguracoes._configurar_ui()`.
  * **Ajustar parâmetros de baia e macros de caneta:** Para modificar a forma como o G-code de pegar/soltar é gerado automaticamente a partir das coordenadas físicas da baia, edite `PainelConfiguracaoCanetas._ao_alterar_parametros_baia()` e as funções geradoras em `gerenciador_canetas.py`.
  * **Configurações do GRBL:** A tabela e os cartões de status do firmware em `PainelParametrosGrbl` consomem metadados de `dicionario_grbl.py`. Para adicionar novos parâmetros suportados pelo firmware, atualize `dicionario_grbl.py`.

* **Possíveis Falhas:** 
  * **Máquina desconectada ao testar comandos:** Ao clicar em testar pegar/soltar ou enviar parâmetros sem porta serial aberta, o sistema exibirá mensagem de aviso impedindo o envio.
  * **Inconsistência nos limites da área de desenho:** Se `X_fim <= X_inicio` ou `Y_fim <= Y_inicio`, a área de desenho resultante terá dimensões nulas. O sistema possui validações de segurança nos spinboxes para evitar valores negativos de curso útil.
  * **Conflito de escrita nos arquivos JSON:** Caso múltiplos processos acessem `src/config/*.json` simultaneamente, pode ocorrer `OSError` ou `JSONDecodeError`. As operações em disco contam com blocos `try/except` protegidos.

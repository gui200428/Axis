# Documentação de Manutenção: painel_calibracao_zoffset.py

* **Objetivo do Script:** 
O arquivo `painel_calibracao_zoffset.py` implementa a interface gráfica interativa do assistente de calibração de altura $Z$ e nivelamento da mesa. Ele fornece um canvas 2D onde cada nó da malha pode ser selecionado com clique do mouse, exibe leituras digitais de posição (DRO), integra controles de movimentação manual (Jog com seletores de passo e diagonais), acionamento de traços de teste no papel e importação/exportação de backups de calibração.

* **Dependências:** 
  * `math`, `typing`
  * `PySide6.QtWidgets` (`QWidget`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`, `QLabel`, `QPushButton`, `QDoubleSpinBox`, `QSpinBox`, `QGroupBox`, `QFileDialog`, `QMessageBox`, etc.)
  * `PySide6.QtCore` (`Qt`, `QPointF`, `QRectF`, `Slot`, `Signal`)
  * `PySide6.QtGui` (`QPainter`, `QColor`, `QPen`, `QFont`, `QMouseEvent`)
  * `resources.controle_da_maquina.logica_controle_da_maquina` (`ControladorGrbl`)
  * `resources.controle_da_maquina.gerenciador_canetas` (`GerenciadorCanetas`)
  * `resources.controle_da_maquina.gerenciador_area_desenho` (`GerenciadorAreaDesenho`)
  * `resources.controle_da_maquina.gerenciador_nivelamento` (`GerenciadorNivelamento`, `MalhaCaneta`, `PontoMalha`)
  * `resources.estilo.tema_escuro` (`ESTILO_CARD_PADRAO`, `PALETA_CORES`)

* **Guia de Alteração:** 
  * **Canvas 2D da Malha (`VisualizadorMalhaNivelamento`):** Para modificar a renderização dos nós da grade, valores numéricos de $Z$ e indicador de posição da máquina, edite os métodos `paintEvent()` e `_desenhar_malha()`.
  * **Assistente de Passo a Passo:** As ações de avançar ponto, retroceder ponto, testar traço ($X+/X-$) e salvar $Z$ atual da máquina são manipuladas em `PainelCalibracaoZOffset`.
  * **Importação/Exportação de Malhas:** Os botões de exportar e importar arquivo JSON de calibração disparam `_ao_clicar_exportar_calibracao()` e `_ao_clicar_importar_calibracao()`.

* **Possíveis Falhas:** 
  * **Calibração sem conexão serial:** O painel desabilita o envio de comandos físicos de movimento quando não há porta conectada, exibindo avisos ao usuário.
  * **Importação de arquivo incompatível:** Se o usuário selecionar um JSON sem a estrutura esperada de canetas/pontos, o parser captura o erro e exibe diálogo explicativo sem afetar a calibração atual.
  * **Seleção de ponto fora do índice:** A seleção direta por clique converte a coordenada de pixels da tela para a matriz $[linha, coluna]$ com tolerância de raio em pixels.

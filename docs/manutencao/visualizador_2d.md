# Documentação de Manutenção: visualizador_2d.py

* **Objetivo do Script:** 
O arquivo `visualizador_2d.py` implementa a visualização bidimensional interativa da mesa de trabalho da plotter em tempo real. Ele renderiza a mesa milimétrica com réguas graduadas, a posição física de HOME no canto inferior direito, as 10 estações/slots de caneta com suas respectivas cores, a área delimitada de desenho, o cabeçote móvel com retículo e estado da caneta (PEN UP / PEN DOWN), além de pré-visualização completa das trajetórias do G-code (G0 rápidos e G1/G2/G3 de desenho) com suporte a zoom e pan via mouse.

* **Dependências:** 
  * `math`, `re`, `typing`
  * `PySide6.QtWidgets` (`QWidget`, `QVBoxLayout`, `QHBoxLayout`, `QPushButton`, `QLabel`, `QFrame`)
  * `PySide6.QtCore` (`Qt`, `QPointF`, `QRectF`, `Slot`)
  * `PySide6.QtGui` (`QPainter`, `QColor`, `QPen`, `QFont`, `QWheelEvent`, `QMouseEvent`)
  * `resources.controle_da_maquina.gerenciador_canetas` (`GerenciadorCanetas`)

* **Guia de Alteração:** 
  * **Interpretação e Preview de G-code:** A função `carregar_gcode_preview()` extrai coordenadas modais e arcos para preencher `linhas_preview_g0` e `linhas_preview_g1`.
  * **Mapeamento de Coordenadas Máquina para Tela:** O método `mm_para_tela(x_mm, y_mm)` converte milímetros no sistema da máquina para pixels da tela, considerando a orientação física da mesa ($X$ vertical, $Y$ horizontal, origem $0,0$ no canto inferior direito).
  * **Interpolação de Arcos G2/G3:** A função `interpolar_arco_gcode()` decompõe arcos circulares em pequenos segmentos lineares para renderização no `QPainter`.

* **Possíveis Falhas:** 
  * **Linhas de comprimento zero / G-code com ruído:** O parser descarta movimentos com deslocamento menor que $1 \times 10^{-4}$ mm para evitar sobrecarga no pipeline de pintura.
  * **Coordenadas fora dos limites:** O visualizador desenha toda a área visível baseada nas dimensões reportadas pelo firmware via `$130` e `$131`, adaptando o fator de escala dinamicamente.

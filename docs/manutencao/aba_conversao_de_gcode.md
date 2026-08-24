# Documentação de Manutenção: aba_conversao_de_gcode.py

* **Objetivo do Script:** 
O arquivo `aba_conversao_de_gcode.py` define o widget da aba de Conversão de Gcode. Ele é responsável exclusivamente pela interface visual (layout, labels, botões) da aba, delegando toda a lógica de negócio ao arquivo `logica_conversao_de_gcode.py` do mesmo módulo.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets` - classes `QWidget`, `QVBoxLayout`, `QLabel`)
  * `PySide6` (módulo `PySide6.QtCore` - classe `Qt`)

* **Guia de Alteração:** 
  * Para adicionar novos componentes visuais na aba (botões, visualizadores de Gcode, etc.), edite o método `_configurar_layout()` da classe `AbaConversaoDeGcode`.
  * Para integrar lógica de negócio, importe funções ou classes de `logica_conversao_de_gcode.py` e conecte-as aos eventos dos widgets (ex: `botao.clicked.connect(funcao_da_logica)`).
  * A classe deve permanecer focada apenas na interface visual. Geração de Gcode, parsing e cálculos devem ficar em `logica_conversao_de_gcode.py`.

* **Possiveis Falhas:** 
  * **Erro de Importação:** Se o módulo não for encontrado, verifique se o `__init__.py` do pacote `conversao_de_gcode` e do pacote `resources` estão exportando a classe corretamente.
  * **Layout não aparece:** Se os widgets adicionados não aparecerem, verifique se foram inseridos no `layout_principal` via `addWidget()`.

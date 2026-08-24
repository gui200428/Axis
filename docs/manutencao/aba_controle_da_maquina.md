# Documentação de Manutenção: aba_controle_da_maquina.py

* **Objetivo do Script:** 
O arquivo `aba_controle_da_maquina.py` define o widget da aba de Controle da Máquina. Ele é responsável exclusivamente pela interface visual (layout, labels, botões) da aba, delegando toda a lógica de negócio ao arquivo `logica_controle_da_maquina.py` do mesmo módulo.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets` - classes `QWidget`, `QVBoxLayout`, `QLabel`)
  * `PySide6` (módulo `PySide6.QtCore` - classe `Qt`)

* **Guia de Alteração:** 
  * Para adicionar novos componentes visuais na aba (botões, inputs, etc.), edite o método `_configurar_layout()` da classe `AbaControleDaMaquina`.
  * Para integrar lógica de negócio, importe funções ou classes de `logica_controle_da_maquina.py` e conecte-as aos eventos dos widgets (ex: `botao.clicked.connect(funcao_da_logica)`).
  * A classe deve permanecer focada apenas na interface visual. Cálculos, comunicação com hardware e processamento devem ficar em `logica_controle_da_maquina.py`.

* **Possiveis Falhas:** 
  * **Erro de Importação:** Se o módulo não for encontrado, verifique se o `__init__.py` do pacote `controle_da_maquina` e do pacote `resources` estão exportando a classe corretamente.
  * **Layout não aparece:** Se os widgets adicionados não aparecerem, verifique se foram inseridos no `layout_principal` via `addWidget()`.

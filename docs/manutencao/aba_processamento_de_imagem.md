# Documentação de Manutenção: aba_processamento_de_imagem.py

* **Objetivo do Script:** 
O arquivo `aba_processamento_de_imagem.py` define o widget da aba de Processamento de Imagem. Ele é responsável exclusivamente pela interface visual (layout, labels, botões) da aba, delegando toda a lógica de negócio ao arquivo `logica_processamento_de_imagem.py` do mesmo módulo.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets` - classes `QWidget`, `QVBoxLayout`, `QLabel`)
  * `PySide6` (módulo `PySide6.QtCore` - classe `Qt`)

* **Guia de Alteração:** 
  * Para adicionar novos componentes visuais na aba (botões, visualizadores de imagem, etc.), edite o método `_configurar_layout()` da classe `AbaProcessamentoDeImagem`.
  * Para integrar lógica de negócio, importe funções ou classes de `logica_processamento_de_imagem.py` e conecte-as aos eventos dos widgets (ex: `botao.clicked.connect(funcao_da_logica)`).
  * A classe deve permanecer focada apenas na interface visual. Processamento de imagem, filtros e manipulações devem ficar em `logica_processamento_de_imagem.py`.

* **Possiveis Falhas:** 
  * **Erro de Importação:** Se o módulo não for encontrado, verifique se o `__init__.py` do pacote `processamento_de_imagem` e do pacote `resources` estão exportando a classe corretamente.
  * **Layout não aparece:** Se os widgets adicionados não aparecerem, verifique se foram inseridos no `layout_principal` via `addWidget()`.

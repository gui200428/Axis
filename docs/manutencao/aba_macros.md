# Documentação de Manutenção: aba_macros.py

* **Objetivo do Script:** 
O arquivo `aba_macros.py` fornece uma interface gráfica dedicada para calibração rápida e visual dos 10 slots de canetas (`CardSlotCaneta`), visualização de status de acoplamento no cabeçote e gerenciamento da biblioteca de macros personalizadas com editor integrado de G-code.

* **Dependências:** 
  * `PySide6.QtWidgets` (`QWidget`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`, `QLabel`, `QPushButton`, `QLineEdit`, `QTextEdit`, `QGroupBox`, `QDoubleSpinBox`, `QScrollArea`, `QSplitter`, `QFrame`, `QMessageBox`, `QListWidget`)
  * `PySide6.QtCore` (`Qt`, `Slot`)
  * `PySide6.QtGui` (`QColor`, `QFont`)
  * `resources.controle_da_maquina.logica_controle_da_maquina` (`ControladorGrbl`)
  * `resources.controle_da_maquina.gerenciador_canetas` (`GerenciadorCanetas`, `SlotCaneta`)
  * `resources.macros.logica_macros` (`GerenciadorMacros`, `MacroGcode`)
  * `resources.estilo.tema_escuro` (`ESTILO_CARD_PADRAO`)

* **Guia de Alteração:** 
  * **Layout do Rack de Canetas:** O container de cards com grade $5 \times 2$ é construído em `_criar_secao_rack_canetas()`.
  * **Editor e Criação de Macros:** O formulário de edição com campos de nome, comando G-code, categoria e código é manipulado em `_criar_secao_macros()`.
  * **Cards Individuais de Caneta (`CardSlotCaneta`):** Cada card possui botões táteis para trocar, pegar, soltar e editar as coordenadas $X, Y, Z, Z_{seguro}$ do slot.

* **Possíveis Falhas:** 
  * **Tentativa de troca com máquina desconectada:** Avisos em `QMessageBox` bloqueiam tentativas de disparo de ferramentas sem link serial ativo.
  * **Conflito de estado do cabeçote:** Caso uma caneta seja removida manualmente pelo operador sem passar pela rotina de desengate, o botão *Declarar Cabeçote Livre* sincroniza o estado lógico com a realidade física.

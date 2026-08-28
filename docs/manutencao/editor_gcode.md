# Documentação de Manutenção: editor_gcode.py

* **Objetivo do Script:** 
O arquivo `editor_gcode.py` implementa um editor de texto customizado (`EditorGcode` herdado de `QPlainTextEdit`) especializado para arquivos G-code. Ele fornece uma régua lateral com numeração automática de linhas (`AreaNumerosLinha`), realce da linha em foco sob o cursor e destaque dinâmico da linha que está sendo enviada e executada pela máquina em tempo real.

* **Dependências:** 
  * `PySide6.QtWidgets` (`QPlainTextEdit`, `QWidget`, `QTextEdit`)
  * `PySide6.QtCore` (`Qt`, `QRect`, `QSize`, `Slot`)
  * `PySide6.QtGui` (`QColor`, `QPainter`, `QTextFormat`, `QTextCursor`)

* **Guia de Alteração:** 
  * **Cores e Destaques Visuais:** As constantes `COR_FUNDO_NUMERO`, `COR_TEXTO_NUMERO`, `COR_LINHA_CURSOR`, `COR_LINHA_ENVIANDO` e `COR_NUMERO_ENVIANDO` definem a identidade visual do componente.
  * **Largura da Área Lateral:** Calculada automaticamente em `calcular_largura_area_numeros()` baseada no total de dígitos do documento com margem de segurança.
  * **Sincronização de Linha Ativa:** O método slot `definir_linha_enviando(indice_linha)` aplica o realce da linha e rola o documento suavemente via `centerCursor()`.

* **Possíveis Falhas:** 
  * **Índice de linha inválido ou negativo:** Passar `-1` para `definir_linha_enviando()` limpa o destaque de envio de forma segura sem lançar exceções.
  * **Redimensionamento da janela:** O método `resizeEvent()` recalcula a geometria da régua lateral para acompanhar o redimensionamento do widget pai.

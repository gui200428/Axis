# Documentação de Manutenção: tema_escuro.py

* **Objetivo do Script:** 
O arquivo `tema_escuro.py` define o design system e a folha de estilos QSS (*Qt Style Sheets*) global da aplicação AXIS Plotter. Ele implementa uma paleta de cores escura profissional (Dark Slate Theme), tipografia hierárquica e estilos unificados para botões, abas, inputs, barras de rolagem, caixas de diálogo, groupboxes e widgets de texto.

* **Dependências:** 
  * Nenhuma dependência externa (definição de constantes de cores e strings QSS em Python puro).

* **Guia de Alteração:** 
  * **Paleta de Cores:** Altere as variáveis no dicionário `PALETA_CORES` (`fundo_app`, `fundo_elevado`, `azul_primario`, `verde_sucesso`, etc.).
  * **Estilo Global (`ESTILO_GLOBAL`):** Contém todas as regras QSS aplicadas na raiz do `QApplication`.
  * **Estilo de Cards (`ESTILO_CARD_PADRAO`):** String utilitária para formatação rápida de `QGroupBox` com visual de cartão elevado e borda suave.

* **Possíveis Falhas:** 
  * **Incompatibilidade de sintaxe QSS:** Propriedades CSS não suportadas pelo renderizador do Qt (ex: algumas propriedades CSS3 modernas) podem ser ignoradas silenciosamente pelo motor do PySide. Utilize seletores e propriedades compatíveis com a especificação QSS.

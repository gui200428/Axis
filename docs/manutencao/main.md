# Documentação de Manutenção: main.py

* **Objetivo do Script:** 
O arquivo `main.py` serve como o orquestrador do programa. Ele inicializa a aplicação PySide6, definindo a janela principal (em branco no projeto base) e iniciando o laço de eventos da interface gráfica.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets` - classes `QApplication`, `QMainWindow`)
  * `sys` (nativo do Python)

* **Guia de Alteração:** 
  * Para modificar o tamanho padrão da janela inicial, altere os parâmetros `width` e `height` na chamada da função `iniciar_interface_grafica()`.
  * Para modificar o título, altere o parâmetro `title` na mesma chamada da função.
  * A estrutura principal de adição de novos widgets e interfaces deve ser incorporada dentro da função `iniciar_interface_grafica()` ou preferencialmente, através da instanciação de classes especializadas para manter a organização.

* **Possiveis Falhas:** 
  * **Erro de Importação (PySide6 não encontrado):** O código irá falhar caso a biblioteca `PySide6` não esteja instalada no ambiente virtual. Conserte rodando `pip install PySide6`.
  * **Erro na execução da aplicação:** Se ocorrer algum erro antes da inicialização do loop `aplicativo.exec()`, a interface poderá fechar instantaneamente. Acompanhe os logs no terminal para identificar as falhas.

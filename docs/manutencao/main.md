# Documentação de Manutenção: main.py

* **Objetivo do Script:** 
O arquivo `main.py` serve como o orquestrador do programa. Ele inicializa a aplicação PySide6, define a janela principal com um sistema de navegação por abas (`QTabWidget`), registra os módulos de cada aba e inicia o laço de eventos da interface gráfica.

* **Dependências:** 
  * `PySide6` (módulos `PySide6.QtWidgets` - classes `QApplication`, `QMainWindow`, `QTabWidget`)
  * `sys` (nativo do Python)
  * `resources` (pacote interno que exporta os widgets das abas: `AbaControleDaMaquina`, `AbaProcessamentoDeImagem`, `AbaConversaoDeSvg`, `AbaConversaoDeGcode`)

* **Guia de Alteração:** 
  * Para modificar o tamanho padrão da janela inicial, altere os parâmetros `width` e `height` na chamada da função `iniciar_interface_grafica()`.
  * Para modificar o título, altere o parâmetro `title` na mesma chamada da função.
  * Para **adicionar uma nova aba**, crie o módulo em `src/resources/nome_do_modulo/`, exporte o widget no `__init__.py` do pacote `resources`, e adicione uma nova tupla `("Nome da Aba", InstanciaDaAba())` na `lista_de_abas` dentro de `iniciar_interface_grafica()`.
  * Para **remover uma aba**, remova a tupla correspondente da `lista_de_abas` e o import associado.
  * A função `registrar_abas()` é responsável por iterar sobre a lista e registrar cada aba no `QTabWidget`. Não é necessário alterá-la ao adicionar ou remover abas.

* **Possiveis Falhas:** 
  * **Erro de Importação (PySide6 não encontrado):** O código irá falhar caso a biblioteca `PySide6` não esteja instalada no ambiente virtual. Conserte rodando `pip install PySide6`.
  * **Erro de Importação (módulo da aba não encontrado):** Se o import de um widget de aba falhar, verifique se o módulo existe em `src/resources/`, se o `__init__.py` está correto e se o nome da classe está exportado.
  * **Erro na execução da aplicação:** Se ocorrer algum erro antes da inicialização do loop `aplicativo.exec()`, a interface poderá fechar instantaneamente. Acompanhe os logs no terminal para identificar as falhas.

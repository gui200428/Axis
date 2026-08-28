# Documentação de Manutenção: logica_macros.py

* **Objetivo do Script:** 
O arquivo `logica_macros.py` implementa o modelo de dados (`MacroGcode`) e o controlador (`GerenciadorMacros`) para a biblioteca de rotinas e macros G-code personalizadas da plotter AXIS. Ele permite cadastrar, persistir em `src/config/macros_usuario.json`, excluir, executar rotinas via porta serial e realizar a expansão inteligente de macros estilo Klipper no fluxo de G-code antes do envio ao firmware.

* **Dependências:** 
  * `json`, `os` (nativos do Python)
  * `dataclasses` (`dataclass`, `asdict`)
  * `typing` (`List`, `Dict`, `Optional`)
  * `PySide6.QtCore` (`QObject`, `Signal`)
  * `resources.controle_da_maquina.logica_controle_da_maquina` (`ControladorGrbl`)

* **Guia de Alteração:** 
  * **Macros Padrão de Fábrica:** A lista `MACROS_PADRAO` contém rotinas essenciais como *Homing Seguro*, *Estacionar Plotter*, *Ponto de Troca*, *Limpeza / Rabisco*, *Abaixar Caneta*, *Levantar Caneta*, etc.
  * **Expansão de Comandos no G-code:** O método `expandir_macros_em_gcode(conteudo)` varre o código linha a linha e substitui chamadas nominais (ex: `HOME`, `PEN_DOWN`, `PARK`) pelo script completo correspondente.
  * **Execução Assíncrona:** O método `executar_macro()` envia o G-code através de `ControladorGrbl.enviar_script_gcode()`.

* **Possíveis Falhas:** 
  * **Comandos recursivos em macros:** A expansão é realizada em 1 nível para evitar laços infinitos caso uma macro faça referência a ela mesma.
  * **Execução com máquina desconectada:** `executar_macro()` valida previamente o estado da conexão serial e retorna `False` caso a porta esteja fechada.

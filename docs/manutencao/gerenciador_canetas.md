# Documentação de Manutenção: gerenciador_canetas.py

* **Objetivo do Script:** 
O arquivo `gerenciador_canetas.py` implementa o modelo de dados e o controlador central do sistema de troca de ferramentas (Tool Changer) para as 10 canetas da plotter AXIS. Ele gerencia posições físicas de baia ($X, Y, Z, Z_{seguro}$), nomes, cores em hexadecimal, templates personalizáveis de scripts G-code de engate (`macro_pegar`) e descarte (`macro_soltar`), além de persistir tudo em `src/config/canetas_plotter.json`.

* **Dependências:** 
  * `json`, `os` (nativos do Python)
  * `dataclasses` (`dataclass`, `asdict`)
  * `typing` (`Dict`, `List`, `Optional`)
  * `PySide6.QtCore` (`QObject`, `Signal`)

* **Guia de Alteração:** 
  * **Templates Padrão de Movimento G-code:** As rotinas padrão de engate e descarte de canetas mecânicas são geradas pelas funções `gerar_template_pegar_padrao()` e `gerar_template_soltar_padrao()`.
  * **Adicionar parâmetros aos slots:** Modifique a classe `SlotCaneta` e a lista `CANETAS_PADRAO`.
  * **Sequência de Troca Completa:** O método `gerar_gcode_troca_completa(novo_id)` gera a sequência encadeada de devolver a caneta anterior (se houver) e pegar a nova selecionada.

* **Possíveis Falhas:** 
  * **Arquivo `canetas_plotter.json` ausente ou inválido:** O método `_carregar_configuracao()` restaura automaticamente os dados padrão predefinidos na constante `CANETAS_PADRAO`.
  * **Troca de caneta redundante:** Se o usuário solicitar a troca para a caneta que já está acoplada no cabeçote, `gerar_gcode_troca_completa()` retorna apenas um comentário de G-code sem movimentar motores desnecessariamente.

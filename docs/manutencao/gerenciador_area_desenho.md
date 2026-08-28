# Documentação de Manutenção: gerenciador_area_desenho.py

* **Objetivo do Script:** 
O arquivo `gerenciador_area_desenho.py` gerencia as coordenadas delimitadoras ($X_{inicio}, Y_{inicio}, X_{fim}, Y_{fim}$) da área útil onde a plotter realiza seus desenhos e traçados. Ele persiste esses valores em `src/config/area_desenho.json` e emite sinais Qt para sincronização dinâmica com o visualizador 2D e com a malha de nivelamento.

* **Dependências:** 
  * `json`, `os` (nativos do Python)
  * `dataclasses` (`dataclass`, `asdict`)
  * `typing` (`Optional`)
  * `PySide6.QtCore` (`QObject`, `Signal`)

* **Guia de Alteração:** 
  * **Valores Padrão de Fábrica:** Os valores nominais da mesa estão definidos na classe `ConfiguracaoAreaDesenho` ($X_{inicio}=60$, $Y_{inicio}=10$, $X_{fim}=270$, $Y_{fim}=307$).
  * **Emissão de Sinais:** A atualização das coordenadas via `atualizar_area()` emite `sinal_area_alterada(x_inicio, y_inicio, x_fim, y_fim)`, sincronizando todos os componentes visuais conectados.

* **Possíveis Falhas:** 
  * **Arquivo JSON corrompido:** Em caso de leitura inválida, `_carregar_configuracao()` restaura a configuração padrão e recria o arquivo em disco com tratamento seguro de exceções.
  * **Criação de diretório inexistente:** A gravação em `_salvar_configuracao()` cria a pasta `src/config/` automaticamente caso ainda não exista no sistema de arquivos.

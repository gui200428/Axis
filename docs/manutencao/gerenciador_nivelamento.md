# Documentação de Manutenção: gerenciador_nivelamento.py

* **Objetivo do Script:** 
O arquivo `gerenciador_nivelamento.py` é responsável pela lógica de nivelamento de mesa por software (*Mesh Bed Leveling*) e compensação de Z-offset para as 10 canetas da plotter. Ele permite criar malhas retangulares configuráveis (de $2 \times 2$ até $20 \times 20$ nós), armazenar as alturas de contato $Z$ para cada caneta, aplicar interpolação bilinear contínua 2D subdividindo traços longos de G-code e exportar/importar calibrações completas em formato JSON.

* **Dependências:** 
  * `json`, `math`, `os`, `re` (nativos do Python)
  * `dataclasses` (`dataclass`, `asdict`, `field`)
  * `typing` (`Dict`, `List`, `Optional`, `Tuple`, `Any`)
  * `PySide6.QtCore` (`QObject`, `Signal`)
  * `resources.controle_da_maquina.gerenciador_area_desenho` (`GerenciadorAreaDesenho`)
  * `resources.controle_da_maquina.gerenciador_canetas` (`GerenciadorCanetas`)

* **Guia de Alteração:** 
  * **Interpolação Bilinear 2D:** A função matemática de interpolação está em `_interpolar_ponto_existente()` e `_interpolar_linear_1d()`.
  * **Subdivisão e fatiamento de traços G-code:** O processamento e substituição de comandos `G1`, `G2`, `G3`, `PEN_DOWN`, `PEN_HOP` e `PEN_UP` ocorre em `aplicar_nivelamento_gcode()`.
  * **Proteção de limites da área útil:** O recurso de elevação preventiva (Auto-Lift Z) ao detectar traços saindo da área delimitada é validado via `esta_dentro_area()`.
  * **Importação/Exportação JSON:** As rotinas de backup e restauração estruturada estão em `importar_calibracao_de_arquivo()` e `exportar_calibracao_para_arquivo()`.

* **Possíveis Falhas:** 
  * **Arquivo JSON corrompido ou ausente:** Caso `nivelamento_canetas.json` esteja corrompido, o método `_carregar_configuracao()` cria automaticamente uma malha padrão uniforme de $4 \times 4$ para as 10 canetas.
  * **Divisão por zero em interpolação de pontos coincidentes:** Tratada através de tolerância `abs(dx) > 1e-6` com clamp entre $[0.0, 1.0]$.
  * **Tentativa de desenho fora dos limites:** Caso o G-code instrua um traço para fora da área útil delimitada, o algoritmo converte a ação em trânsito seguro em $Z_{up}$ com comentário de aviso no stream.

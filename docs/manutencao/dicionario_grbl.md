# Documentação de Manutenção: dicionario_grbl.py

* **Objetivo do Script:** 
O arquivo `dicionario_grbl.py` armazena o dicionário de metadados, títulos em português, unidades de medida, categorias e descrições funcionais detalhadas para todos os parâmetros de configuração padrão do firmware GRBL (desde `$0` até `$132`). Ele é consumido pela interface de parâmetros da máquina para enriquecer a exibição e facilitar a calibração pelo operador.

* **Dependências:** 
  * `typing` (`Dict`, `TypedDict`, `Optional`)

* **Guia de Alteração:** 
  * **Adicionar novos parâmetros:** Insira uma nova entrada no dicionário `DICIONARIO_PARAMETROS_GRBL` com os campos `nome`, `unidade`, `descricao`, `categoria` e `tipo_dado`.
  * **Tratamento de parâmetros desconhecidos:** A função `obter_info_parametro(chave)` retorna automaticamente metadados genéricos caso uma chave customizada ou não mapeada seja reportada pelo firmware.

* **Possíveis Falhas:** 
  * **Chaves com formato diferente:** O dicionário mapeia chaves com prefixo cifrão (ex: `"$130"`). A busca trata strings diretamente sem mutação de tipos.



# Pesquisa: Criação de G-code com Pausas para Troca de Cor

**Responsáveis:** Higor Robert Barbist e Vitor Ronald Barbist

**Branch:** `docs_08_pesquisa_gcode_troca_de_cor`

**Data:** 01/07/2026



## 1. Objetivo

Como automatizar a conversão de imagens/vetores para G-code via CLI (`vpype` / `vpype-gcode`) permitindo o gerenciamento eficiente de pausas e trocas de cor/caneta na máquina operando via GRBL?

---

## 2. Contexto / Por que isso importa pro Axis v3

A versão v3 do Axis busca centralizar todo o processo de geração de G-code dentro do software proprietário. Como a máquina utiliza o firmware GRBL (que atua como seguidor de comandos pela porta USB/serial) e não dependemos mais de editores gráficos manuais como o Inkscape, precisamos de um pipeline automatizado para processar imagens, dividir camadas de cores e gerenciar as pausas da impressora sem perder o referenciamento.

---

## 3. O que já sabemos

* O `vpype` e o plugin `vpype-gcode` resolvem a automação da geração de G-code por serem ferramentas CLI (Interface de Linha de Comando) executáveis em segundo plano pelo nosso software.


* A máquina utiliza GRBL. O envio de comandos via serial permite que o software do Axis detecte instruções de interrupção no fluxo de dados para pausar a máquina, mover o cabeçote para uma posição segura e aguardar a autorização do usuário.
* Estrutura base de configuração no `plotter_config.toml` já testada:
```toml
[gwrite.custom_plotter]
unit = "mm"
offset_x = 36.0
offset_y = 35.0
document_start = """G21 ; Define unidades em mm
PEN_UP ; Garante caneta levantada
"""
layer_start = "(Start Layer)\n"
line_start = "(Start Block)\n"
segment_first = """PEN_UP
G01 X{x:.4f} Y{y:.4f} F9000
PEN_DOWN
"""
segment = "G01 X{x:.4f} Y{y:.4f} F9000\n"
line_end = "PEN_UP\n"
document_end = """
PEN_UP
G01 X36.0000 Y274.0000 F9000
M2"""
invert_y = true
```



---

## 4. Pesquisa

### Opção A: Pausa no G-code via GRBL (Arquivo Unificado)

* **Como funciona:** O parâmetro `layer_start` no `plotter_config.toml` injeta um comando de pausa (como `M0` ou `M6`) e move o cabeçote para uma posição segura de troca (`X0 Y200`). O software gerenciador do Axis detecta a instrução ao ler/enviar a linha, pausa a transmissão da porta serial, aguarda a confirmação do usuário no sistema ("Troca de caneta efetuada") e retoma o envio dos dados.
* **Vantagens:**
* Gera um único arquivo G-code contendo a rotina completa da ilustração.
* O controle da pausa fica 100% no software proprietário AXIS.


* **Desvantagens:** Exige que a aplicação cliente trate o evento de interrupção e retome o fluxo via transmissão USB de forma robusta.
* **Custo estimado / peças necessárias:** N/A (Apenas desenvolvimento de software).
* **Fonte(s):** Documentação interna / Testes de streaming GRBL.

### Opção B: Separação Dinâmica por Arquivos Separados via CLI

* **Como funciona:** A imagem vetorial de entrada (SVG) contém as camadas organizadas por cor. O software executa o `vpype` programaticamente através do filtro `--lsel` via linha de comando, gerando um arquivo `.gcode` individual para cada camada/cor:
```bash
# Camada 1 (Cor 1):
vpype read desenho.svg layout --fit-to-margins 1cm 188mmx200mm lsel 1 -c plotter_config.toml gwrite -p ender3_plotter cor1.gcode

# Camada 2 (Cor 2):
vpype read desenho.svg layout --fit-to-margins 1cm 188mmx200mm lsel 2 -c plotter_config.toml gwrite -p ender3_plotter cor2.gcode

```


* **Vantagens:**
* Risco zero de colisão ou continuidade não planejada da máquina.
* Flexibilidade para o usuário executar uma cor por vez ou refazer uma cor específica caso haja falha de caneta.


* **Desvantagens:** Multiplicidade de arquivos G-code gerenciados no diretório do projeto.
* **Custo estimado / peças necessárias:** N/A.
* **Fonte(s):** Documentação do `vpype` (parâmetro `--lsel`).

### Opção C: Decomposição CMYK e Concatenação em G-code Unificado

* **Como funciona:**
1. A imagem original é dividida em 4 canais de cor padrão de impressão (Ciano, Magenta, Amarelo, Preto) ou em uma paleta predefinida de canetas.
2. O algoritmo gera a vetorização/hachuramento para cada canal específico de cor.
3. Cada canal é convertido em um bloco de linhas/camadas dentro do `vpype`.
4. O script concatena o G-code de cada canal em uma sequência lógica contínua, inserindo o bloco de movimentação de segurança (`layer_start`) e a instrução de pausa interativa entre a transição dos canais.


* **Vantagens:**
* Processo totalmente automatizado e centralizado na solução AXIS, convertendo imagens raster diretamente em arte colorida.
* Permite reproduzir imagens ricas utilizando poucas canetas físicas.


* **Desvantagens:** Requer o desenvolvimento prévio do algoritmo de separação de cores e hachuramento.
* **Custo estimado / peças necessárias:** N/A.
* **Fonte(s):** [https://www.youtube.com/shorts/5zpbmh6JIro](https://www.google.com/search?q=https://www.youtube.com/shorts/5zpbmh6JIro)

---

## 5. Recomendação da dupla

Recomendamos a adoção do pipeline baseado na **Opção C (Decomposição CMYK)** para a etapa de processamento de imagens e vetorização, eliminando softwares externos e gerando um fluxo de trabalho limpo para o usuário final.

---

## 6. Perguntas em aberto / pontos pra discutir com o grupo

* [ ] Qual algoritmo/biblioteca utilizaremos para fazer o hachuramento/retícula dos canais CMYK antes de passar para o `vpype`?

---

## 7. Referências

* [https://www.youtube.com/shorts/5zpbmh6JIro](https://www.google.com/search?q=https://www.youtube.com/shorts/5zpbmh6JIro)
* Documentação do vpype: [https://vpype.readthedocs.io/](https://vpype.readthedocs.io/)
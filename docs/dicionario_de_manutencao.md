# Dicionário de Padronização e Estrutura - AXIS

Esse documento define as regras de padronizações para os membros da equipe no desenvolvimento do Projeto Axis. O objetivo é manter o projeto organizado, legível, rastreável e escalável.

---
## 01. Regras universais

Antes de falar de coisas mais específicas, precisamos seguir as regras abaixo para **TODOS** os arquivos que serão utilizado

### 1.1. `snake_case`
Para facilitar a leitura e a diminuição de ambiguidade dentro código, todos os arquivos devem seguir o padrão **snake_case** onde todas as letras são minusculas e as palavras são separadas por `_`

Ex:
    * Desenho 2.png             #ERRADO
    * desenho_2.png             #CERTO
    * desenho DE cachorro.png   #ERRADO
    * desenho_de_cachorro.png 
---

## 02. Estrutura de Diretório

A raiz do projeto deve ser organizada nas seguintes pastas principais:

```text
AXIS/
├── assets/     # Arquivios de midia e recursos estáticos
├── docs/       # Documentação geral do projeto
├── src/        # Código fonte principal

```

### 2.1. `assets/`
Esta pasta armazena todos os arquivos não código consumidos pelo projetos (imagens, áudios, vídeos, modelagem, etc).

**Regra de Nomenclatura:**
Todos os arquivos devem ter nomes descritivos e indicar o contexto de onde são usados
Exemplo:
    - foto_cachorro_exemplo_readme.png
    - print_interface_processamento_readme.png
    - desenho_cachorro_finalizado_exemplo_readme.png

### 2.2. `docs/`
Esta pasta armazena todos os arquivos de documentação textual do projeto, todos eles devem ser arquivo markdown para conseguir manter histórico, atualmente ela possui os diretórios abaixo

```text
docs/
├── manutencao/                     # Arquivos de como fazer a manutenção nos códigos criados dentro de `src/`
├── pesquisa/                       # Pesquisas realizadas dentro do projeto seguindo o modelo `pesquisa.md`
├── templates/                      # Onde os modelos são guardados para a padronização de documentos 
├── tutoriais/                      # Tutoriais necessário para certas coisas
├── dicionario_de_manutencao.md     # Esse arquivo, apenas ele deve ficar na raiz dessa pasta para fácil localização
```

### 2.3. `src/`
Contém todo o código fonte do projeto com os seguintes diretorios abaixo

```text
src/
├── config/             # Arquivos de persistência e configurações JSON (ex: `canetas_plotter.json`)
├── utils/              # Funções auxiliares e simples de uso geral (ex: `formatador_de_texto.py`)
├── resources/          # Modulos principais com regras de negócios (ex: `conversor_de_imagem_para_g-code.py`)
├── main.py             # O orquestrador do programa
```
**OBS:** Como essa é a pasta que mais vai ter alterações dentro do projeto, ela é volátil, portanto sempre deve manter atualizado essa documentação caso algo mude, e antes de mudar, converse com TODOS os membros do time.

---

## 3. Convenções de Código

Para a parte de desenvolvimento, as seguintes regras são obrigatórias para não ter erros e manter a padronização

### 3.1. Nomenclatura de Variáveis
* As variáveis devem seguir o padrão `snake_case` explicado no tópico **1.1**
* Os nomes devem ser descritivos, não se deve abreviar as variáveis. O argumento de que "Dá trabalho para digitar" é inválido devido ao auto-complete das IDEs.
* **Variáveis Ruins:**
    * img
    * c
    * cur_x
* **Variáveis Boas:**
    * imagem_escala_cinza
    * soma_vetores_xy
    * x_atual

### 3.2. Nomenclatura de Funções
* As funções devem seguir o padrão `snake_case` explicado no tópico **1.1**
* O nome de uma função deve representar uma ação
* As funções devem ser o mais genérica possível
* As funções devem possuir Docstrings
* As funções devem possuir Type Hints
    * **Função Ruim:**
    ```python
        def processaTudo(img, v):
            # Faz a conversao da imagem pro AXIS
            c = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return c
    ```
    * **Função Boa:**
    ```python
        def converter_imagem_para_escala_cinza(imagem_referencia: list) -> list:
            """
                Converte a matriz de uma imagem colorida para escala de cinza.
                Args:
                    imagem_referencia (list): Matriz representando a imagem lida do diretório assets.
                Returns:
                    list: Matriz da imagem processada em tons de cinza.
            """
            imagem_cinza = cv2.cvtColor(imagem_referencia, cv2.COLOR_BGR2GRAY)
            return imagem_cinza
    ```

### 3.3. Manipulação de arquivo
* Sempre que uma função for manipular algum arquivo externo, ou seja, do computador, ele deve ter tratamento de erro para garantir que o código não será interrompido por causa de um erro

---
## 4. Controle de Versão e GitHub Projects

Para manter a organização do fluxo de trabalho em equipe, será utilizado o **GitHub Projects** e um padrão de rastreio de tarefas de código

### 4.1. Padronização de Issues
Todas tarefas ou bug deve ser registrado como uma issue no GitHub projects antes de ser desenvolvido.
A issue deve descrever claramente e sem ambiguidade o que precisa ser feito, o contexto da tarefa e os critérios de aceitação.

### 4.2. Nomenclatura de Branches
O nome da branch deve referenciar a issue que está resolvendo, indicando o tipo de alteração e seguindo o padrão abaixo

`<tipo>_<Numero_da_issue>_<Titulo_da_Issue>`

Se recomenda utilizar os seguintes tipos
    * `feat`: Nova funcionalidade ou recurso
    * `fix`: Correção de bug ou erro
    * `update`: Atualização, refatoração ou mudança de contexto
    * `docs`: Inclusão ou alteração de documentação

**Exemplos:**
  * `docs_10_pesquisa_sobre_CMYK`
  * `fix_12_erro_leitura_imagem`
  * `update_15_calibracao_motores`

---

## 5. Documentação e Manutenção de Scripts

Para garantir a continuidade do projeto, **Todo script independente criado na pasta `src/` deve possuir uma documentação de manutenção**
A documentação deve conter:
    * **Objetivo do Script:** O que o Script faz de forma resumida
    * **Dependências:** Módulos e bibliotecas externas necessárias
    * **Guia de Alteração:** Onde um desenvolvedor deve mexer se quiser alterar lógicas cruciais
    * **Possíveis Falhas:** Erros mapeados e como consertá-los caso o código quebre no futuro 
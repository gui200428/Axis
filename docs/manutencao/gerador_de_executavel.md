# Documentação de Manutenção: gerador_de_executavel.py

* **Objetivo do Script:** 
O arquivo `gerador_de_executavel.py` automatiza o processo de compilação do arquivo principal `main.py` utilizando o PyInstaller. Ele cria um aplicativo executável standalone que não requer instalação do Python na máquina destino.

* **Dependências:** 
  * `pyinstaller` (ferramenta de compilação)
  * `os` (nativo do Python)
  * `subprocess` (nativo do Python)
  * `sys` (nativo do Python)

* **Guia de Alteração:** 
  * Para alterar o nome do aplicativo final, edite a variável `nome_executavel` na chamada da função `compilar_executavel()`.
  * Para alterar qual script deve ser compilado, modifique a variável `file` na chamada da função `compilar_executavel()`.
  * Se o projeto necessitar a inclusão de pastas extras de assets (como imagens ou pastas em resources), adicione o parâmetro `--add-data` na lista `comando`. Exemplo: `"--add-data", "assets:assets"`.
  * Para gerar um único arquivo `.exe` (ao invés de uma pasta com várias dependências), troque a flag `"--onedir"` por `"--onefile"`.

* **Possiveis Falhas:** 
  * **Comando pyinstaller não encontrado:** A ferramenta `pyinstaller` pode não estar instalada ou não estar no PATH. Conserte rodando `pip install pyinstaller`.
  * **Falha de permissão:** O script pode falhar se não houver permissão para escrever na pasta `dist/` ou `build/`.
  * **Script main.py não encontrado:** Se o arquivo `main.py` for movido de diretório, o processo de compilação será abortado. Verifique os caminhos do projeto.

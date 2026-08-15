# Como subir sua pesquisa

1. Clone o repositório:
   git clone https://github.com/gui200428/Axis.git

2. Entre na pasta do projeto:
   cd Axis

3. Crie sua branch (troque "seu-tema" pelo tema de vocês):
   git checkout -b pesquisa/seu-tema

4. Coloque seus arquivos dentro de pesquisa/seu-tema/

5. Suba as mudanças:
   > git add . <br>
   > git commit -m "pesquisa: <o que você pesquisou>" <br>
   > git push origin pesquisa/seu-tema

---

## Como a pasta deve ficar no final

Sua pasta final de pesquisas vai ficar com uma estrutura parecida com esta:

```text
Axis/
└── pesquisa/
    ├── README.md                 <-- Este arquivo
    ├── template/
    │   └── template.md           <-- O modelo em branco para ser copiado
    └── cinematica-corexy/        <-- Exemplo: Pasta criada pela sua dupla
        ├── pesquisa.md           <-- O template copiado e preenchido
        ├── imagens/              <-- (Opcional) Fotos, prints do CAD, etc
        └── referencias/          <-- (Opcional) PDFs, datasheets
```
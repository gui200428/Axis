# O que é o padrão de cores CMYK?

É um sistema de cores universal que funciona através da subtração de luz. Isso possibilita a reprodução de cores em produções físicas, como impressões em papel.

A sigla representa as quatro tintas utilizadas como cores primárias para a criação das demais cores. São elas:
* Cyan (Ciano)
* Magenta
* Yellow (Amarelo)
* Key (Preto)

Juntas, essas iniciais formam a sigla CMYK.

Utilizamos essas cores porque o CMYK funciona de forma totalmente oposta ao sistema RGB. Enquanto o RGB atua através da emissão de pontos luminosos a partir de uma tela, o sistema CMYK atua através da subtração de luz refletida pelo papel branco, combinando a intensidade dos pigmentos coloridos aplicados.

Os pigmentos utilizados são divididos em dois grupos principais:
* **Canais básicos (Ciano, Magenta e Amarelo):** São responsáveis pela criação e mistura das cores.
* **Canal chave / Key (Preto):** É responsável pelo ajuste de contraste e profundidade.

Quando juntamos todas os canais básicos chegamos ao canal chave:
$$Cyan+Magenta+Yellow=Black$$

* **O início (Branco):** O papel em branco reflete 100% da luz do ambiente para os nossos olhos.
* **A tinta (Filtro):** Quando riscamos o papel com algum dos canais básicos, essa tinta age como um filtro físico. Ela subtrai parte da luz do ambiente e reflete as outras cores primárias que já conhecemos no sistema RGB.
    * *Exemplo:* Se utilizarmos a tinta ciano, ela irá absorver a luz vermelha (cor oposta ao ciano no sistema RGB) e refletir apenas as cores azul e verde (que, juntas, formam o ciano que enxergamos no papel).
* **A Mistura:** Se você sobrepor marcadores, eles subtraem mais luz. Criando assim mais cores no papel.

## Como aplicar essa teoria no nosso projeto?

Como o AXIS é controlado por comandos G-Code, não podemos simplesmente usar as cores de qualquer maneira. Se a máquina aplicar camadas de Ciano, Magenta e Amarelo exatamente no mesmo local repetidas vezes, o excesso de umidade irá rasgar a superfície do papel.

Para solucionar esse limite físico e reproduzir a mistura real de cores, o algoritmo utilizará a técnica de separação em Meio-tom (Halftoning) focada em Hachuras Cruzadas (Crosshatching).

Em vez de pintar preenchimentos sólidos, o nosso software separará a imagem digital em quatro camadas vetoriais independentes. Cada camada utiliza uma cor distinta e um ângulo específico, sendo formada exclusivamente por linhas finas. A ilusão de novas cores será criada pela interseção matemática dessas linhas. A densidade da cor será controlada pelo espaçamento entre elas:
* linhas desenhadas mais próximas escurecem a região
* linhas mais afastadas deixam o branco do papel atuar, clareando o tom

### Efeito Moiré

O maior desafio físico ao sobrepor malhas de linhas é a criação de um padrão de interferência visual indesejado conhecido como Efeito Moiré. *(Exemplo visual do Efeito Moiré em diferentes ângulos)*

Para evitar que essas falhas óticas ocorram no desenho final, o G-code gerado pelo AXIS deverá aplicar uma rotação matemática precisa para as linhas de cada cor, seguindo o padrão universal da indústria gráfica:
* **Canal Key (Preto):** Linhas geradas a $45^{\circ}$. Como o preto dita o contraste e é a cor mais forte, ele é posicionado no ângulo de menor percepção de falhas para o olho humano.
* **Canal Yellow (Amarelo):** Linhas geradas a $0^{\circ}$ (ou $90^{\circ}$). Por ser a tinta mais clara e menos intrusiva, ela assume o ângulo mais evidente.
* **Canal Cyan (Ciano):** Linhas geradas a $15^{\circ}$.
* **Canal Magenta:** Linhas geradas a $75^{\circ}$.

## Viabilidade Física: Marcadores e Tipos de Papel

Para que o método CMYK funcione no AXIS, as ferramentas físicas devem colaborar com os vetores gerados pelo software:

1. **Marcadores:** Não podemos usar qualquer tipo de marcador. É obrigatório o uso de tintas translúcidas (como tintas de caneta-tinteiro). Pois tintas opacas bloqueariam a luz em vez de filtrá-la, arruinando o efeito subtrativo.
    * **Canetas-tinteiro (Ideal):** São translúcidas e se misturam de forma previsível. É o melhor tipo de tinta possível para o projeto.
    * **Marcadores à Base de Álcool (Usável mas com ressalvas):** Misturam-se reativando a camada inferior, mas tendem a borrar em aplicações plotters como o nosso projeto, ultrapassando as linhas matemáticas.
    * **Marcadores à Base de Água (Inadequado):** A umidade excessiva sem tempo de secagem destrói a precisão geométrica e rasga o papel.

2. **Papel:** Papéis comuns (como o sulfite) possuem alta capilaridade, ou seja, tendem a borrar a precisão das linhas. Para que a sobreposição CMYK seja perfeita, é obrigatório utilizar papéis de superfície selada e baixa absorção, que mantêm a tinta na superfície e garantem o contraste exato do G-code.
    * **Papel Bristol Liso (Ideal):** Por ter superfície selada e baixa absorção, mantém a tinta na superfície, garantindo o contraste exato e suportando a sobreposição úmida sem deformar.

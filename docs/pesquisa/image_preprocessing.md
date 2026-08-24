# Pesquisa: Pré-processamento de imagens

**Responsável:** Thales Enrico<br>
**Branch:** `pesquisa/image-preprocessing`<br>
**Data:** 03/08/2026

---

## 1. Objetivo

Essa pesquisa se propõe a elucidar como imagens são matrizes e aplicação de filtros (que são outras matrizes) para expor bordas e elementos necessários para representa-lás.

_Essa pesquisa tem como objetivo explicar como uma imagem digital pode ser representada por uma matriz de pixels e como operações de convolução, utilizando filtros (kernels), permitem destacar características importantes, como bordas, contornos e regiões de interesse. Esses elementos serão utilizados posteriormente para gerar uma representação simplificada da imagem, adequada para reprodução pelo Axis v3_

---

## 2. Contexto / Por que isso importa pro Axis v3

*Entender como representar a "essência" de uma imagem é o primeiro passso antes de representa-la no papel*

_Antes que o Axis v3 possa desenhar uma imagem, é necessário reduzir a quantidade de informação presente nela e preservar apenas as características essenciais. O pré-processamento de imagens permite identificar essas informações relevantes, servindo como base para a geração dos movimentos que a máquina executará durante o desenho._

---

## 3. O que já sabemos

*Uma imagem colorida possui três canais (RGB) e que muitos algoritmos trabalham apenas com intensidade luminosa de cada um deles. Baseado nisso a ideia existente é efetuar a multiplicação de matrizes determinadas para pegar a "essência"*


---

## 4. Pesquisa

### Opção A: Pipeline de Pré-processamento com OpenCV e G'MIC

- **Como funciona:**

  O pipeline realiza uma sequência de operações de processamento de imagens para transformar uma fotografia em uma representação adequada para desenho. Inicialmente, a imagem é convertida para tons de cinza e submetida ao algoritmo *Pencil Sketch*, que combina inversão da imagem, suavização por filtro Gaussiano e divisão entre imagens para produzir um efeito semelhante a um esboço a lápis.

  Em seguida, é aplicado um filtro bilateral para reduzir ruídos preservando as bordas, seguido do algoritmo CLAHE (*Contrast Limited Adaptive Histogram Equalization*), responsável por aumentar o contraste local da imagem. Com o contraste aprimorado, o detector de bordas Canny identifica os principais contornos.

  As regiões da imagem são então divididas em diferentes níveis de intensidade, sendo cada nível representado por um conjunto de hachuras (linhas paralelas em diferentes direções). Quanto mais escura a região, maior a quantidade de linhas sobrepostas, simulando técnicas tradicionais de desenho artístico.

  Por fim, as linhas podem ser coloridas utilizando as cores da imagem original e a resolução é ampliada por meio do algoritmo *G'MIC Smart Upscale*, preservando os detalhes antes da geração do desenho final.

- **Vantagens:**

  - Pipeline totalmente automatizado.
  - Utiliza bibliotecas consolidadas na área de visão computacional.
  - Preserva os principais contornos da imagem.
  - Produz desenhos com aparência semelhante a esboços técnicos.
  - Permite controlar facilmente a densidade das hachuras.
  - Fácil integração com aplicações desenvolvidas em Python.

- **Desvantagens:**

  - Possui diversos parâmetros que precisam ser ajustados para diferentes tipos de imagem.
  - Pode perder detalhes em regiões muito claras ou muito escuras.
  - A qualidade final depende da resolução da imagem de entrada.
  - O processo de *upscale* adiciona uma dependência externa (G'MIC).
  - Não realiza interpretação semântica da imagem, apenas processamento baseado nos pixels.

- **Fonte(s):**

  - https://opencv.org/
  - https://setosa.io/ev/image-kernels/

### Opção B: Processamento de Imagens Baseado em Grafos (Graph-Based Image Processing)

- **Como funciona:**

  Nesta abordagem, uma imagem é modelada como um grafo, onde cada pixel (ou grupo de pixels) é representado por um nó, enquanto as conexões entre pixels vizinhos formam as arestas do grafo. Cada aresta pode receber um peso baseado em características como diferença de intensidade, cor ou textura.

  A partir dessa representação, algoritmos de teoria dos grafos são utilizados para analisar a estrutura da imagem. Em vez de operar diretamente sobre matrizes de pixels, operações como segmentação, detecção de contornos, agrupamento de regiões e planejamento de trajetórias passam a ser problemas sobre grafos.

  Para aplicações como o Axis v3, essa abordagem possibilita transformar a imagem em uma estrutura conectada, permitindo extrair apenas as regiões relevantes e posteriormente otimizar a ordem de desenho utilizando algoritmos como Dijkstra, A*, Árvores Geradoras Mínimas (Minimum Spanning Tree) e outros métodos de otimização de caminhos.

- **Vantagens:**

  - Representa explicitamente as relações de vizinhança entre os pixels.
  - Permite utilizar algoritmos consolidados da Teoria dos Grafos.
  - Facilita tarefas de segmentação e identificação de objetos.
  - Pode ser utilizada para otimizar a trajetória de desenho de um plotter.
  - Adapta-se facilmente a diferentes critérios de similaridade (cor, intensidade, textura ou distância).
  - Possibilita trabalhar tanto com pixels individuais quanto com regiões (superpixels), reduzindo a complexidade computacional.

- **Desvantagens:**

  - A construção do grafo pode consumir grande quantidade de memória em imagens de alta resolução.
  - Alguns algoritmos possuem custo computacional elevado.
  - A definição dos pesos das arestas influencia diretamente a qualidade dos resultados.
  - Geralmente requer uma etapa posterior para converter o grafo em curvas ou trajetórias utilizáveis pelo plotter.


- **Fonte(s):**

  - Image Processing Using Graphs – Lecture 1, Uppsala University.
    https://user.it.uu.se/~filma606/ImageProcessingUsingGraphs/LectureNotes/Lecture1.pdf


### Opção C: Vetorização de Imagens (Image Vectorization)

- **Como funciona:**

  A vetorização consiste em converter uma imagem raster (composta por pixels, como PNG ou JPG) em uma representação vetorial formada por curvas, linhas e polígonos matemáticos (como SVG). Em vez de armazenar a cor de cada pixel, o algoritmo identifica regiões de mesma cor, contornos e formas geométricas, reconstruindo a imagem por meio de caminhos vetoriais.

  Diferentemente de técnicas tradicionais baseadas apenas em detecção de bordas, a vetorização busca representar a estrutura completa da imagem com o menor número possível de curvas e pontos de controle. Isso produz arquivos escaláveis e facilmente editáveis, além de fornecer trajetórias que podem ser utilizadas diretamente por máquinas como plotters, cortadoras CNC e impressoras.

- **Vantagens:**

  - Gera uma representação baseada em formas, e não em pixels.
  - Produz arquivos escaláveis sem perda de qualidade (SVG, DXF, EPS).
  - Facilita a geração de trajetórias para plotters e máquinas CNC.
  - Reduz a quantidade de informação necessária para representar desenhos simples.
  - Permite edição posterior em softwares vetoriais como Inkscape e Adobe Illustrator.
  - É especialmente eficiente para logotipos, ilustrações, desenhos técnicos e imagens com contornos bem definidos.

- **Desvantagens:**

  - Fotografias com muitos detalhes, texturas e gradientes costumam produzir resultados complexos ou pouco fiéis.
  - Pode gerar grande quantidade de curvas e pontos de controle quando a imagem possui muito ruído.
  - Frequentemente exige simplificação ou ajustes manuais após a vetorização.
  - O desempenho depende da qualidade e resolução da imagem de entrada.


- **Fonte(s):**

  - https://perfectvector.com/blog/what-is-image-vectorization


*Adicionem quantas opções forem relevantes.*

---

## 5. Recomendação da autor

*Pela familiaridade e prévio estudo, observando o que é utilizado massivamente em processamento de imagens, até mesmo nas famosas camadas de convolução de redes neurais, a opção A parece mais devida e amparada por fontes na internet*

---

## 6. Perguntas em aberto / pontos pra discutir com o grupo

*Pipeline adaptativo para cada imagem*

- Algumas imagens tem estilos totalmente diferentes. Propõe-se, a criar uma feature que escolhe os filtros a serem aplicados para cada imagem antes de executá-la no Axis. Com pré-vizualizações
- [ ]

---

## 7. Referências

- notas de aula Jones Ganatyr
- https://setosa.io/ev/image-kernels/

# Pesquisa: Pré-processamento de Imagens para Plotter CMYK

**Responsáveis:** Miguel Motta e Thales Henrico  
**Branch:** Pré-processamento  
**Data:** 03/08/2026  
**Projeto:** Axis v3  

---

## 1. Objetivo
Determinar os algoritmos e fluxos matemáticos mais eficientes para converter imagens rasterizadas (PNG/RGB) em caminhos vetoriais de G-code divididos em 4 camadas físicas (Ciano, Magenta, Amarelo e Preto) para a operação da plotter com canetas.

## 2. Contexto / Por que isso importa pro Axis v3
O módulo de software de pré-processamento é a base da Axis v3. Impressoras a jato de tinta usam matrizes de pontos (halftones), mas como nossa máquina opera com motores e braços mecânicos controlando canetas, enviar comandos baseados em pixels isolados resultaria em tempos de impressão de dezenas de horas. Precisamos de algoritmos que otimizem os trajetos vetoriais para evitar que o papel rasgue (por saturação de tinta) e para minimizar os saltos da caneta no eixo Z.

## 3. O que já sabemos
Com base no que já desenvolvemos e validamos no projeto anterior (código base do repositório do Axis), o sistema aditivo das telas digitais (RGB) precisa ser transposto matematicamente para o subtrativo das tintas (CMYK). Antes de qualquer geração de caminho vetorial para o G-code, a imagem passa pela lógica que já aplicávamos:
- **Normalização:** Os valores RGB (0 a 255) são mapeados para a escala 0.0 a 1.0.
- **Cálculo do Preto (Key):** K = 1 - max(R, G, B).
- **Cálculo CMY:** Se K = 1, os demais são 0. Caso contrário: C = (1 - R - K) / (1 - K), etc.
- **Obrigatoriedade de Contraste:** Ao extrairmos as 4 camadas em tons de cinza, precisamos aplicar um ajuste de curvas/níveis (Levels). Canetas soltam pigmento puro, então áreas com 50% de cinza no digital podem facilmente se transformar em áreas 100% saturadas no papel.

## 4. Pesquisa: Algoritmos de Path Generation

### Opção A: Cross-hatching Direcional (Tradicional)
- **Como funciona:** Divide a matriz da imagem em "baldes" de intensidade e sobrepõe padrões de linhas retas. 0-25% de tinta = diagonais (45°); 25-50% = cruza em 'X' (-45°); 50-75% = adiciona horizontais (0°); 75-100% = adiciona verticais (90°).
- **Vantagens:** Produz um efeito visual clássico de sombreamento técnico, excelente para canetas nanquim.
- **Desvantagens:** O G-code gerado será inundado de retas curtas. O cabeçote passará a maior parte do tempo levantando e abaixando o eixo Z, o que aumenta absurdamente o tempo de plotagem e a fadiga mecânica.

### Opção B: Modulação por Amplitude/Frequência (Recomendado)
- **Como funciona:** O algoritmo traça linhas retas de um lado ao outro da folha. Quando a coordenada passa por um pixel mais escuro da camada CMYK, o código faz a linha "vibrar" (uma onda senoidal ou ruído fractal), adensando a tinta naquele trecho.
- **Vantagens:** A caneta entra em contato com o papel e faz um movimento G1 contínuo por toda a largura. É extremamente rápido e contorna as limitações de aceleração/desaceleração dos motores.
- **Desvantagens:** Requer matemática mais elaborada no script para modular a geometria das retas com base na intensidade do pixel.

### Opção C: TSP (Traveling Salesperson) com Stippling
- **Como funciona:** Converte as áreas escuras da imagem em milhares de pontos (Weighted Voronoi Stippling). Um algoritmo (Heurística Lin-Kernighan) calcula a rota mais curta para passar por todos os pontos em uma linha única, sem cruzar desnecessariamente.
- **Vantagens:** Estética complexa e impressionante. Reduz o Z-hop para o absoluto mínimo.
- **Desvantagens:** O pré-processamento de software exige muita CPU e RAM para calcular milhares de nós antes de gerar o G-code.

## 5. Recomendação da dupla
Recomendamos implementar a Modulação por Amplitude/Frequência (Opção B) como padrão para o módulo de hatchfill, pois oferece a melhor proporção entre velocidade de impressão e qualidade visual para CMYK.

**Ação Crítica (Otimização de Rota):** Independentemente do algoritmo escolhido, precisaremos implementar dois filtros finais no script Python antes do output:
1. **Filtragem de ruído:** Descartar qualquer segmento de linha menor que 0.3mm (espessura da caneta).
2. **Ordenação Gulosa (Greedy Sorting):** Vasculhar a matriz de vetores e ordenar os caminhos conectando o fim de uma linha ao início geográfico mais próximo da próxima. Isso corta o tempo de travel do eixo XY (com o Z levantado) em cerca de 60%.

## 6. Perguntas em aberto / pontos pra discutir com o grupo
- Como faremos o registro/zeramento físico (homing) para garantir que as trocas de canetas (C -> M -> Y -> K) ocorram exatamente no mesmo milímetro de origem?
- Qual marca/modelo de caneta usaremos como padrão no firmware? Precisamos de pontas uniformes (como nanquim técnico 0.3mm) instaladas a exatos 90 graus para evitar desvios no espaçamento matemático das hachuras.
- Faremos a ordem de G-code fixada em Amarelo > Ciano > Magenta > Preto para evitar borrar canetas claras?

## 7. Referências
- Exemplo visual (Modulação/Ondas) - Canal Ginny Gravity (TikTok)
https://www.tiktok.com/@ginnygravity/video/7342646586230525230
- CMYK Drawing com Arduino - Canal Mani Fa (YouTube)
https://www.youtube.com/watch?v=h1n4AyyHRBg
- Machine Setup e Software Hatching - Canal Shop MAKER Q (YouTube)
https://www.youtube.com/watch?v=I4omT2L9aI8
- Tópico sobre separação CMYK no DrawingBotV3 - Comunidade PlotterArt (Reddit)
https://www.reddit.com/r/PlotterArt/comments/16asp7t/cmyk_color_separation_inquiry_drawingbotv3/

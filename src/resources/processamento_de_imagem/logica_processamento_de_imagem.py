import math
from PIL import Image, ImageOps

class ImageProcessor:
    """
    Processador de Imagem que converte raster em vetor SVG (Estilo Squiggle).
    """
    
    def processar(self, imagem: Image.Image, parametros: dict) -> str:
        """
        Converte a imagem PIL para uma string SVG baseada nos parâmetros de squiggle.
        """
        # Converter para tons de cinza
        gray = ImageOps.grayscale(imagem)
        largura, altura = gray.size
        
        # Obter parâmetros
        densidade = parametros.get("densidade", 100) / 100.0
        comp_min = parametros.get("comprimento_min", 1)
        comp_max = parametros.get("comprimento_max", 10)
        n_testes = parametros.get("n_testes", 1)
        apagamento_min = parametros.get("apagamento_min", 0)
        apagamento_max = parametros.get("apagamento_max", 255)
        tom = parametros.get("tom", 0) # 0: Linear, 1: Exponencial
        sq_min = parametros.get("squiggle_min", 0)
        sq_max = parametros.get("squiggle_max", 10)
        desvio_sq = parametros.get("desvio_squiggle", 0)
        resolucao_max = parametros.get("resolucao_max", 10)
        espessura_traco = parametros.get("espessura_traco", 1)
        
        # Garante que a resolução não seja 0
        if resolucao_max < 1:
            resolucao_max = 1
            
        svg_paths = []
        
        # Escanear a imagem em linhas horizontais
        for y in range(0, altura, resolucao_max):
            pontos = []
            x = 0
            
            while x < largura:
                # Amostrar pixel
                pixel = gray.getpixel((x, y))
                
                # Regras de apagamento
                if pixel < apagamento_min or pixel > apagamento_max:
                    x += comp_max
                    # Se tivermos pontos acumulados, fechamos esse segmento
                    if len(pontos) > 1:
                        svg_paths.append(self._gerar_path(pontos))
                    pontos = []
                    continue
                
                # Normalizar brilho (0.0 = preto, 1.0 = branco)
                brilho = pixel / 255.0
                
                # Curva de Tom
                if tom == 1: # Exponencial
                    brilho = brilho ** 2
                
                # O brilho controla a amplitude do squiggle
                # Preto (brilho 0) -> Squiggle Max
                # Branco (brilho 1) -> Squiggle Min
                amplitude = sq_max - (brilho * (sq_max - sq_min))
                
                # O comprimento do passo
                # Preto (brilho 0) -> Passo menor (mais detalhe)
                # Branco (brilho 1) -> Passo maior (menos detalhe)
                passo = comp_min + (brilho * (comp_max - comp_min))
                passo = max(1, int(passo))
                
                # Adicionar variação/desvio
                fase = (x * densidade) + desvio_sq
                
                # Deslocamento Y no formato senoide
                dy = math.sin(fase) * amplitude
                
                pontos.append((x, y + dy))
                x += passo
                
            if len(pontos) > 1:
                svg_paths.append(self._gerar_path(pontos))
                
        # Montar o documento SVG (como bytes para carregar no QSvgWidget se necessario, mas string serve)
        svg_elements = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}">',
            f'<rect width="{largura}" height="{altura}" fill="white" />'
        ]
        
        # Adicionar os paths (com fill="none" para aparecer apenas as linhas)
        path_style = f'fill="none" stroke="black" stroke-width="{espessura_traco}" stroke-linejoin="round"'
        
        for p_str in svg_paths:
            svg_elements.append(f'<path d="{p_str}" {path_style} />')
            
        svg_elements.append('</svg>')
        
        return "\\n".join(svg_elements)
        
    def _gerar_path(self, pontos: list) -> str:
        if not pontos:
            return ""
            
        path = f"M {pontos[0][0]:.2f} {pontos[0][1]:.2f}"
        for px, py in pontos[1:]:
            path += f" L {px:.2f} {py:.2f}"
            
        return path
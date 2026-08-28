"""
Dicionário de metadados e descrições para os parâmetros de configuração do firmware GRBL.

Compatível com GRBL v0.9, v1.1 e GrblHAL.
"""

from typing import Dict, TypedDict, Optional


class InfoParametroGrbl(TypedDict):
    nome: str
    unidade: str
    descricao: str
    categoria: str
    tipo_dado: str  # "float", "int", "bool", "mask"


# Metadados de todos os parâmetros padrão do GRBL
DICIONARIO_PARAMETROS_GRBL: Dict[str, InfoParametroGrbl] = {
    "$0": {
        "nome": "Tempo de pulso de passo",
        "unidade": "µs",
        "descricao": "Duração mínima em microssegundos do sinal de pulso enviado aos drivers de motor de passo.",
        "categoria": "Passos & Motores",
        "tipo_dado": "int"
    },
    "$1": {
        "nome": "Atraso de inatividade dos motores",
        "unidade": "ms",
        "descricao": "Tempo de espera antes de desenergizar os motores após o movimento. 255 mantém os motores sempre energizados (recomendado para precisão).",
        "categoria": "Passos & Motores",
        "tipo_dado": "int"
    },
    "$2": {
        "nome": "Inversão de pulso de passo",
        "unidade": "máscara (0-7)",
        "descricao": "Máscara binária para inverter o nível lógico do sinal de pulso (0=Normal, 1=Invertido).",
        "categoria": "Passos & Motores",
        "tipo_dado": "mask"
    },
    "$3": {
        "nome": "Inversão de direção dos eixos",
        "unidade": "máscara (0-7)",
        "descricao": "Inverte o sentido de rotação dos motores dos eixos (bit 0=X, bit 1=Y, bit 2=Z).",
        "categoria": "Passos & Motores",
        "tipo_dado": "mask"
    },
    "$4": {
        "nome": "Inversão do pino de habilitação (Enable)",
        "unidade": "boolean (0/1)",
        "descricao": "Inverte o sinal do pino de habilitação dos drivers (0=Ativo em nível baixo, 1=Ativo em nível alto).",
        "categoria": "Passos & Motores",
        "tipo_dado": "bool"
    },
    "$5": {
        "nome": "Inversão dos pinos de fim de curso (Limits)",
        "unidade": "boolean (0/1)",
        "descricao": "Inverte a leitura dos pinos de fim de curso (0=Normalmente Aberto [NO], 1=Normalmente Fechado [NC]).",
        "categoria": "Homing & Sensores",
        "tipo_dado": "bool"
    },
    "$6": {
        "nome": "Inversão do pino de sonda (Probe)",
        "unidade": "boolean (0/1)",
        "descricao": "Inverte a leitura do sensor de sonda/probe (0=Normalmente Aberto, 1=Normalmente Fechado).",
        "categoria": "Homing & Sensores",
        "tipo_dado": "bool"
    },
    "$10": {
        "nome": "Opções de relatório de status",
        "unidade": "máscara",
        "descricao": "Configura quais dados são retornados no relatório de status '?' (ex: posição de máquina vs trabalho, buffer RX).",
        "categoria": "Sistema",
        "tipo_dado": "mask"
    },
    "$11": {
        "nome": "Desvio de junção (Junction deviation)",
        "unidade": "mm",
        "descricao": "Determina a velocidade com que a máquina pode fazer curvas e mudanças de direção suaves.",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$12": {
        "nome": "Tolerância de interpolação de arco",
        "unidade": "mm",
        "descricao": "Precisão máxima usada para segmentar comandos de arco (G2 e G3) em pequenos segmentos lineares.",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$13": {
        "nome": "Relatório em polegadas",
        "unidade": "boolean (0/1)",
        "descricao": "Habilita a exibição de relatórios e posições em polegadas em vez de milímetros (0=mm, 1=polegadas).",
        "categoria": "Sistema",
        "tipo_dado": "bool"
    },
    "$20": {
        "nome": "Limites suaves (Soft limits)",
        "unidade": "boolean (0/1)",
        "descricao": "Impede por software que o comando G-code tente mover a máquina além dos limites de curso ($130-$132). Requer homing ativo.",
        "categoria": "Limites de Curso",
        "tipo_dado": "bool"
    },
    "$21": {
        "nome": "Limites rígidos (Hard limits)",
        "unidade": "boolean (0/1)",
        "descricao": "Dispara alarme imediato caso qualquer sensor físico de fim de curso seja acionado durante o movimento.",
        "categoria": "Limites de Curso",
        "tipo_dado": "bool"
    },
    "$22": {
        "nome": "Ciclo de Homing ativado",
        "unidade": "boolean (0/1)",
        "descricao": "Habilita a rotina de busca de ponto zero físico ($H) utilizando as chaves de fim de curso.",
        "categoria": "Homing & Sensores",
        "tipo_dado": "bool"
    },
    "$23": {
        "nome": "Inversão de direção do Homing",
        "unidade": "máscara (0-7)",
        "descricao": "Define em qual direção cada eixo se move para buscar o sensor de homing (bit 0=X, bit 1=Y, bit 2=Z).",
        "categoria": "Homing & Sensores",
        "tipo_dado": "mask"
    },
    "$24": {
        "nome": "Velocidade lenta de homing (Feed rate)",
        "unidade": "mm/min",
        "descricao": "Velocidade lenta e precisa na segunda aproximação ao sensor de fim de curso para obter repetibilidade máxima.",
        "categoria": "Homing & Sensores",
        "tipo_dado": "float"
    },
    "$25": {
        "nome": "Velocidade rápida de busca do homing (Seek rate)",
        "unidade": "mm/min",
        "descricao": "Velocidade rápida inicial na primeira busca em direção aos sensores de fim de curso.",
        "categoria": "Homing & Sensores",
        "tipo_dado": "float"
    },
    "$26": {
        "nome": "Debounce dos sensores de homing",
        "unidade": "ms",
        "descricao": "Atraso para filtragem de ruído elétrico nos contatos das chaves de fim de curso.",
        "categoria": "Homing & Sensores",
        "tipo_dado": "int"
    },
    "$27": {
        "nome": "Distância de recuo do homing (Pull-off)",
        "unidade": "mm",
        "descricao": "Distância que a máquina recua para liberar a chave de fim de curso após completar o ciclo de homing.",
        "categoria": "Homing & Sensores",
        "tipo_dado": "float"
    },
    "$30": {
        "nome": "Velocidade máxima do Spindle / PWM Laser",
        "unidade": "RPM / PWM",
        "descricao": "Valor máximo de rotação do spindle ou valor máximo de potência PWM (corresponde a 100% de laser).",
        "categoria": "Laser & Spindle",
        "tipo_dado": "float"
    },
    "$31": {
        "nome": "Velocidade mínima do Spindle / PWM Laser",
        "unidade": "RPM / PWM",
        "descricao": "Valor mínimo de rotação do spindle ou nível mínimo de ativação do laser.",
        "categoria": "Laser & Spindle",
        "tipo_dado": "float"
    },
    "$32": {
        "nome": "Modo Laser ativado",
        "unidade": "boolean (0/1)",
        "descricao": "Quando ativado (1), o laser ajusta dinamicamente a potência durante acelerações e desliga em movimentos rápidos G0.",
        "categoria": "Laser & Spindle",
        "tipo_dado": "bool"
    },
    "$100": {
        "nome": "Resolução do Eixo X",
        "unidade": "passos/mm",
        "descricao": "Quantidade de pulsos de passo necessários para mover o carro no Eixo X por exatamente 1 milímetro.",
        "categoria": "Passos & Motores",
        "tipo_dado": "float"
    },
    "$101": {
        "nome": "Resolução do Eixo Y",
        "unidade": "passos/mm",
        "descricao": "Quantidade de pulsos de passo necessários para mover o carro no Eixo Y por exatamente 1 milímetro.",
        "categoria": "Passos & Motores",
        "tipo_dado": "float"
    },
    "$102": {
        "nome": "Resolução do Eixo Z",
        "unidade": "passos/mm",
        "descricao": "Quantidade de pulsos de passo necessários para mover o carro no Eixo Z por exatamente 1 milímetro.",
        "categoria": "Passos & Motores",
        "tipo_dado": "float"
    },
    "$110": {
        "nome": "Velocidade máxima do Eixo X",
        "unidade": "mm/min",
        "descricao": "Velocidade máxima de deslocamento do Eixo X (utilizada em movimentos rápidos G0).",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$111": {
        "nome": "Velocidade máxima do Eixo Y",
        "unidade": "mm/min",
        "descricao": "Velocidade máxima de deslocamento do Eixo Y (utilizada em movimentos rápidos G0).",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$112": {
        "nome": "Velocidade máxima do Eixo Z",
        "unidade": "mm/min",
        "descricao": "Velocidade máxima de deslocamento do Eixo Z (utilizada em movimentos rápidos G0).",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$120": {
        "nome": "Aceleração do Eixo X",
        "unidade": "mm/s²",
        "descricao": "Taxa de aceleração e desaceleração máxima permitida para o motor do Eixo X.",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$121": {
        "nome": "Aceleração do Eixo Y",
        "unidade": "mm/s²",
        "descricao": "Taxa de aceleração e desaceleração máxima permitida para o motor do Eixo Y.",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$122": {
        "nome": "Aceleração do Eixo Z",
        "unidade": "mm/s²",
        "descricao": "Taxa de aceleração e desaceleração máxima permitida para o motor do Eixo Z.",
        "categoria": "Velocidade & Aceleração",
        "tipo_dado": "float"
    },
    "$130": {
        "nome": "Curso máximo do Eixo X",
        "unidade": "mm",
        "descricao": "Dimensão total útil de trabalho da mesa no Eixo X (limite máximo de deslocamento).",
        "categoria": "Limites de Curso",
        "tipo_dado": "float"
    },
    "$131": {
        "nome": "Curso máximo do Eixo Y",
        "unidade": "mm",
        "descricao": "Dimensão total útil de trabalho da mesa no Eixo Y (limite máximo de deslocamento).",
        "categoria": "Limites de Curso",
        "tipo_dado": "float"
    },
    "$132": {
        "nome": "Curso máximo do Eixo Z",
        "unidade": "mm",
        "descricao": "Dimensão total útil de deslocamento do atuador da caneta no Eixo Z.",
        "categoria": "Limites de Curso",
        "tipo_dado": "float"
    },
}


def obter_info_parametro(chave: str) -> InfoParametroGrbl:
    """
    Retorna as informações descritivas de um parâmetro do GRBL.
    Caso a chave não esteja no dicionário pré-definido, retorna metadados padrão genéricos.

    Args:
        chave (str): Identificador do parâmetro GRBL (ex: "$130", "$100").

    Returns:
        InfoParametroGrbl: Dicionário contendo nome, unidade, descrição, categoria e tipo de dado.
    """
    if chave in DICIONARIO_PARAMETROS_GRBL:
        return DICIONARIO_PARAMETROS_GRBL[chave]

    return {
        "nome": f"Parâmetro {chave}",
        "unidade": "-",
        "descricao": f"Parâmetro adicional ou customizado do firmware ({chave}).",
        "categoria": "Outros",
        "tipo_dado": "str"
    }

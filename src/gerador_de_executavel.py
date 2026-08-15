import os
import subprocess
import sys

def compilar_executavel(
    file: str,
    nome_executavel: str
    ) -> None:
    """
    Compila o script principal (main.py) em um arquivo executável utilizando o PyInstaller.

    Args:
        file - Nome do arquivo que deve ser compilado
        nome_executavel - O nome que o executavel vai receber 
    """
    caminho_script = os.path.join(os.path.dirname(__file__), file)
    
    if not os.path.exists(caminho_script):
        print(f"Erro: O arquivo {caminho_script} não foi encontrado.")
        return

    comando = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", nome_executavel,
        caminho_script
    ]

    try:
        print("Iniciando a compilação do executável...")
        subprocess.run(comando, check=True)
        print("Compilação concluída com sucesso. Verifique a pasta 'dist/'.")
    except subprocess.CalledProcessError as erro:
        print(f"Erro durante a execução do PyInstaller: {erro}")
    except Exception as erro:
        print(f"Ocorreu um erro inesperado ao tentar compilar: {erro}")

if __name__ == "__main__":
    file = "main.py"
    nome_executavel = "Axis"

    compilar_executavel(file=file, nome_executavel=nome_executavel)

# -*- coding: utf-8 -*-
"""
Converte a imagem de logo de um cliente para .ico (ícone do executável e instalador).

Uso: py tools/convert_logo_to_ico.py <imagem> [saida.ico]
Ex.: py tools/convert_logo_to_ico.py assets/clientes/gih/logo.jpeg
     (saída padrão: assets/icons/logo.ico)
"""

import os
from PIL import Image

def convert_jpeg_to_ico(input_path, output_path):
    """Converte uma imagem JPEG para formato ICO com múltiplas resoluções"""
    try:
        # Abre a imagem
        img = Image.open(input_path)
        
        # Converte para RGBA se necessário
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Cria múltiplas resoluções para o ícone
        # Windows usa diferentes tamanhos dependendo do contexto
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        
        # Salva como ICO com múltiplas resoluções
        img.save(output_path, format='ICO', sizes=icon_sizes)
        
        print(f"✅ Ícone criado com sucesso: {output_path}")
        print(f"   Resoluções incluídas: {', '.join([f'{w}x{h}' for w, h in icon_sizes])}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao converter imagem: {e}")
        return False

if __name__ == "__main__":
    # Caminhos
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        exit(1)
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto
    input_jpeg = sys.argv[1]
    output_ico = sys.argv[2] if len(sys.argv) > 2 else os.path.join(script_dir, "assets", "icons", "logo.ico")
    
    # Verifica se o arquivo de entrada existe
    if not os.path.exists(input_jpeg):
        print(f"❌ Arquivo não encontrado: {input_jpeg}")
        exit(1)
    
    # Garante que o diretório de saída existe
    os.makedirs(os.path.dirname(output_ico), exist_ok=True)
    
    # Converte
    print(f"🔄 Convertendo {input_jpeg} para {output_ico}")
    success = convert_jpeg_to_ico(input_jpeg, output_ico)
    
    if success:
        print(f"\n✅ Conversão concluída!")
        print(f"   O ícone pode ser usado no PyInstaller e Inno Setup")
    else:
        print(f"\n❌ Falha na conversão")
        exit(1)

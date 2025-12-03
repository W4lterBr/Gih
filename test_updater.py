"""
Script de teste do sistema de atualização
Verifica conectividade com GitHub e validação de token
"""

import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.updater import (
    CURRENT_VERSION,
    GITHUB_OWNER, 
    GITHUB_REPO,
    GITHUB_BRANCH,
    VERSION_URL,
    DOWNLOAD_URL,
    GITHUB_TOKEN,
    check_license_status,
    UpdateChecker
)

def print_separator():
    print("=" * 70)

def test_configuration():
    """Testa a configuração básica"""
    print("\n🔧 CONFIGURAÇÃO DO SISTEMA")
    print_separator()
    print(f"Versão atual:     {CURRENT_VERSION}")
    print(f"Repositório:      {GITHUB_OWNER}/{GITHUB_REPO}")
    print(f"Branch:           {GITHUB_BRANCH}")
    print(f"Token GitHub:     {'✅ Configurado' if GITHUB_TOKEN else '❌ Não encontrado'}")
    print(f"URL version.json: {VERSION_URL}")
    print(f"URL download:     {DOWNLOAD_URL}")
    print_separator()

def test_license():
    """Testa o status da licença/token"""
    print("\n🔐 STATUS DA LICENÇA")
    print_separator()
    
    status_code, message = check_license_status()
    
    status_emoji = {
        1: "✅",  # Em dia
        2: "⏳",  # Pendente
        3: "❌",  # Inadimplente
        4: "🌐"   # Sem internet
    }
    
    emoji = status_emoji.get(status_code, "❓")
    print(f"Status: {emoji} {message}")
    print_separator()
    
    return status_code == 1 or status_code == 4  # OK se em dia ou sem internet

def test_check_updates():
    """Testa verificação de atualizações"""
    print("\n🔄 VERIFICAÇÃO DE ATUALIZAÇÕES")
    print_separator()
    
    try:
        checker = UpdateChecker()
        has_update, remote_version, changelog = checker.check_for_updates()
        
        if has_update:
            print(f"✅ Atualização disponível!")
            print(f"   Versão remota: {remote_version}")
            print(f"   Versão atual:  {CURRENT_VERSION}")
            print(f"\n📋 Changelog:")
            for item in changelog:
                print(f"   • {item}")
        else:
            print(f"✅ Sistema está atualizado!")
            print(f"   Versão: {CURRENT_VERSION}")
            if remote_version:
                print(f"   Versão remota: {remote_version}")
        
        print_separator()
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar atualizações: {e}")
        print_separator()
        return False

def main():
    """Executa todos os testes"""
    print("\n" + "="*70)
    print(" 🧪 TESTE DO SISTEMA DE ATUALIZAÇÃO")
    print("="*70)
    
    # 1. Testa configuração
    test_configuration()
    
    # 2. Testa licença/token
    license_ok = test_license()
    
    # 3. Se licença OK, testa verificação de atualizações
    if license_ok:
        test_check_updates()
    else:
        print("\n⚠️  Não foi possível testar atualizações devido ao status da licença")
        print("   Configure o token em 'github_token.txt' se o repositório for privado")
    
    print("\n✅ Testes concluídos!\n")

if __name__ == "__main__":
    main()

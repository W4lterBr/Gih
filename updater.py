# core/updater.py
"""
Sistema de Auto-Atualização Inteligente
Verifica e baixa atualizações do GitHub automaticamente
"""

import os
import sys
import json
import socket
import urllib.request
import urllib.error
import urllib.parse
import shutil
import tempfile
import zipfile
from typing import Optional, Tuple, Dict, Any, Callable
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

# Debug mode
DEBUG_UPDATER = True

# Versão atual do sistema (será atualizada automaticamente)
CURRENT_VERSION = "1.11.45"

# Configurações do GitHub
GITHUB_OWNER = "W4lterBr"
GITHUB_REPO = "Confeitaria-1.1.6"  # Nome do repositório no GitHub
GITHUB_BRANCH = "main"

# URLs do GitHub - API não tem cache (melhor para atualizações)
VERSION_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/version.json?ref={GITHUB_BRANCH}"
DOWNLOAD_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

# Importa logging
try:
    from core.logger import log_event, log_error, log_warning
except ImportError:
    # Fallback caso logger não esteja disponível
    log_event = lambda msg: print(f"[INFO] {msg}")
    log_error = lambda msg, exc=None: print(f"[ERROR] {msg}")
    log_warning = lambda msg: print(f"[WARNING] {msg}")


def get_install_directory() -> str:
    """Retorna o diretório de instalação da aplicação"""
    if getattr(sys, 'frozen', False):
        # Executável PyInstaller - retorna a pasta onde está o .exe
        install_dir = os.path.dirname(sys.executable)
        if DEBUG_UPDATER:
            print(f"[updater] Diretório de instalação (frozen): {install_dir}")
        return install_dir
    else:
        # Modo desenvolvimento
        dev_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if DEBUG_UPDATER:
            print(f"[updater] Diretório de instalação (dev): {dev_dir}")
        return dev_dir


def load_github_token() -> Optional[str]:
    """Carrega o token do GitHub do arquivo local"""
    install_dir = get_install_directory()
    token_file = os.path.join(install_dir, 'github_token.txt')
    
    if DEBUG_UPDATER:
        print(f"[updater] 🔍 Procurando token em: {token_file}")
        print(f"[updater] 📁 Diretório existe: {os.path.exists(install_dir)}")
        print(f"[updater] 📄 Arquivo existe: {os.path.exists(token_file)}")
        
        # Lista arquivos no diretório para debug
        if os.path.exists(install_dir):
            files = os.listdir(install_dir)
            print(f"[updater] 📋 Arquivos no diretório ({len(files)}):")
            for f in files[:10]:  # Mostra apenas os primeiros 10
                print(f"[updater]    - {f}")
    
    try:
        if os.path.exists(token_file):
            with open(token_file, 'r', encoding='utf-8') as f:
                # Lê e limpa o token: remove espaços, quebras de linha, tabs
                token = f.read().strip()
                
                # Remove espaços no meio (caso o usuário tenha copiado com espaços)
                token = ''.join(token.split())
                
                # Valida formato básico do token GitHub (deve começar com ghp_)
                if token and token.startswith('ghp_') and len(token) > 10:
                    if DEBUG_UPDATER:
                        print(f"[updater] 🔑 Token carregado: {token[:8]}...")
                    return token
                elif token:
                    if DEBUG_UPDATER:
                        print(f"[updater] ⚠️ Token inválido (formato incorreto)")
        else:
            if DEBUG_UPDATER:
                print(f"[updater] ⚠️ Arquivo github_token.txt não encontrado")
                print(f"[updater]    Esperado em: {token_file}")
    except Exception as e:
        if DEBUG_UPDATER:
            print(f"[updater] ⚠️ Erro ao carregar token: {e}")
    return None


# Token de acesso (carregado de github_token.txt)
GITHUB_TOKEN = load_github_token()

if DEBUG_UPDATER:
    print(f"[updater] 🔧 Configuração:")
    print(f"[updater]    Repositório: {GITHUB_REPO}")
    print(f"[updater]    Privado: {'Sim' if GITHUB_TOKEN else 'Não'}")
    print(f"[updater]    URL version.json: {VERSION_URL}")


# Configurações de status de licença
IS_PRIVATE_REPO = True  # Este repositório é privado

def check_license_status() -> Tuple[int, str]:
    """
    Verifica o status da licença (token GitHub)
    
    Returns:
        Tuple[int, str]: (status_code, message)
        Status codes:
            1 - Licença em dia (token válido e funcionando)
            2 - Licença pendente (token não encontrado)
            3 - Licença inadimplente (token inválido ou sem permissão)
            4 - Erro de rede (sem conexão com internet)
    """
    # Se não há token, status pendente
    if not GITHUB_TOKEN:
        return (2, "Licença pendente - Token não configurado")
    
    # Tenta fazer uma requisição simples ao GitHub para validar o token
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}",
            headers={'Authorization': f'token {GITHUB_TOKEN}'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return (1, "Licença em dia")
            else:
                return (3, "Licença inadimplente - Token inválido")
                
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            # Token inválido ou sem permissão
            return (3, "Licença inadimplente - Token sem permissão")
        elif e.code == 404:
            # Repositório não encontrado (pode ser token inválido)
            return (3, "Licença inadimplente - Repositório não acessível")
        else:
            # Outro erro HTTP
            return (4, f"Erro de rede - HTTP {e.code}")
            
    except urllib.error.URLError as e:
        # Erro de rede (sem internet)
        return (4, "Erro de rede - Conecte-se à internet")
        
    except Exception as e:
        # Erro genérico
        if DEBUG_UPDATER:
            print(f"[updater] ⚠️ Erro ao verificar licença: {e}")
        return (4, f"Erro ao verificar licença")


def compare_versions(current: str, remote: str) -> int:
    """
    Compara duas versões no formato X.Y.Z
    
    Returns:
        -1 se current < remote (atualização disponível)
         0 se current == remote (versões iguais)
         1 se current > remote (versão local mais nova)
    """
    try:
        # Remove prefixos 'v' se existirem
        current = current.lstrip('v')
        remote = remote.lstrip('v')
        
        # Converte para tuplas de inteiros
        current_parts = tuple(map(int, current.split('.')))
        remote_parts = tuple(map(int, remote.split('.')))
        
        if current_parts < remote_parts:
            return -1
        elif current_parts > remote_parts:
            return 1
        else:
            return 0
    except Exception as e:
        if DEBUG_UPDATER:
            print(f"[updater] Erro ao comparar versões: {e}")
        return 0


def check_for_updates(timeout: float = 10.0) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Verifica se há atualizações disponíveis
    
    Returns:
        Tuple[bool, Optional[Dict], Optional[str]]: 
            (tem_atualizacao, info_versao, mensagem_erro)
    """
    try:
        log_event("🔍 Verificando atualizações disponíveis...")
        if DEBUG_UPDATER:
            print(f"[updater] Verificando atualizações...")
            print(f"[updater] Versão atual: {CURRENT_VERSION}")
            print(f"[updater] URL: {VERSION_URL}")
            print(f"[updater] Timeout: {timeout}s")
        
        # Adiciona cache buster para evitar cache (usa & pois URL já tem ?ref=main)
        url_with_cache_bust = f"{VERSION_URL}&t={int(datetime.now().timestamp())}"
        
        headers = {
            "User-Agent": "Confeitaria-Updater/1.0",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
        
        # Adiciona autenticação se tiver token (repositório privado)
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
            log_event("✅ Usando autenticação GitHub")
            if DEBUG_UPDATER:
                print(f"[updater] ✅ Usando token de autenticação")
        else:
            log_warning("⚠️ Token GitHub não encontrado - falha esperada para repo privado")
            if DEBUG_UPDATER:
                print(f"[updater] ⚠️ SEM TOKEN - Requisição falhará para repo privado!")
        
        log_event("📡 Conectando ao GitHub...")
        if DEBUG_UPDATER:
            print(f"[updater] 📡 Fazendo requisição...")
        
        req = urllib.request.Request(url_with_cache_bust, headers=headers)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            log_event(f"✅ Resposta do GitHub recebida (status: {response.status})")
            if DEBUG_UPDATER:
                print(f"[updater] ✅ Resposta recebida (status: {response.status})")
            
            response_data = json.loads(response.read().decode('utf-8'))
            
            # API do GitHub retorna o conteúdo em base64
            if 'content' in response_data:
                if DEBUG_UPDATER:
                    print(f"[updater] 📦 Decodificando conteúdo base64...")
                import base64
                content_b64 = response_data['content'].replace('\n', '')
                content = base64.b64decode(content_b64).decode('utf-8')
                data = json.loads(content)
                log_event("✅ Arquivo version.json decodificado")
                if DEBUG_UPDATER:
                    print(f"[updater] ✅ version.json decodificado com sucesso")
            else:
                # Fallback para resposta direta (raw.githubusercontent.com)
                if DEBUG_UPDATER:
                    print(f"[updater] ⚠️ Resposta direta (sem base64)")
                data = response_data
        
        remote_version = data.get('version', '0.0.0')
        
        log_event(f"📊 Comparação: Local={CURRENT_VERSION} vs Remoto={remote_version}")
        if DEBUG_UPDATER:
            print(f"[updater] Versão remota: {remote_version}")
        
        comparison = compare_versions(CURRENT_VERSION, remote_version)
        
        if comparison < 0:
            # Atualização disponível
            log_event(f"🎉 ATUALIZAÇÃO DISPONÍVEL: {CURRENT_VERSION} → {remote_version}")
            print("=" * 60)
            print(f"🎉 ATUALIZAÇÃO DISPONÍVEL!")
            print(f"📦 Versão atual:     {CURRENT_VERSION}")
            print(f"🆕 Nova versão:      {remote_version}")
            print(f"📝 Changelog:")
            for item in data.get('changelog', []):
                print(f"   • {item}")
            print("=" * 60)
            return True, data, None
        elif comparison == 0:
            log_event(f"✅ Sistema atualizado na versão {CURRENT_VERSION}")
            print(f"[updater] ✅ Sistema está atualizado na versão {CURRENT_VERSION}")
            return False, data, None
        else:
            log_warning(f"⚠️ Versão local ({CURRENT_VERSION}) mais nova que remota ({remote_version})")
            print(f"[updater] ℹ️ Versão local ({CURRENT_VERSION}) mais nova que a remota ({remote_version})")
            return False, data, None
            
    except urllib.error.HTTPError as e:
        # Erro HTTP específico (404, 403, etc)
        error_msg = ""
        if e.code == 404:
            if not GITHUB_TOKEN and IS_PRIVATE_REPO:
                error_msg = "Token GitHub não encontrado.\n\nPara verificar atualizações:\n1. Copie o arquivo 'github_token.txt' para a pasta do programa\n2. Ou consulte TOKEN_SETUP.md para configurar"
            else:
                error_msg = "Arquivo de versão não encontrado no repositório"
        elif e.code == 403:
            error_msg = "Token inválido ou sem permissão.\nVerifique o arquivo github_token.txt"
        elif e.code == 401:
            error_msg = "Token inválido ou expirado.\nVerifique o arquivo github_token.txt"
        else:
            error_msg = f"Erro HTTP {e.code}: {e.reason}"
        
        log_error(f"❌ Erro HTTP ao verificar atualizações: {error_msg}")
        if DEBUG_UPDATER:
            print(f"[updater] ❌ HTTPError: {e.code} - {e.reason}")
            print(f"[updater]    {error_msg}")
        return False, None, error_msg
    
    except urllib.error.URLError as e:
        error_msg = f"Erro de conexão: {str(e.reason)}\n\nVerifique sua conexão com a internet"
        log_error(f"❌ Erro de conexão: {e.reason}")
        if DEBUG_UPDATER:
            print(f"[updater] ❌ URLError: {e.reason}")
        return False, None, error_msg
    
    except json.JSONDecodeError as e:
        error_msg = f"Erro ao processar dados: Resposta inválida do servidor"
        log_error(f"❌ Erro JSON: {e}")
        if DEBUG_UPDATER:
            print(f"[updater] ❌ JSONDecodeError: {e}")
        return False, None, error_msg
    
    except socket.timeout:
        error_msg = f"Tempo limite excedido ({timeout}s)\n\nTente novamente ou verifique sua conexão"
        log_error(f"❌ Timeout após {timeout}s")
        if DEBUG_UPDATER:
            print(f"[updater] ❌ Timeout após {timeout}s")
        return False, None, error_msg
    
    except Exception as e:
        error_msg = f"Erro inesperado: {str(e)}\n\nTipo: {type(e).__name__}"
        log_error(f"❌ Erro inesperado: {e}", exc_info=True)
        if DEBUG_UPDATER:
            print(f"[updater] ❌ Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        return False, None, error_msg


def download_update(progress_callback: Optional[Callable[[int, str], None]] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Baixa a atualização do GitHub
    
    Args:
        progress_callback: Função chamada com (progresso_percentual, mensagem)
    
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: 
            (sucesso, caminho_arquivo_zip, mensagem_erro)
    """
    try:
        if progress_callback:
            progress_callback(10, "Iniciando download...")
        
        if DEBUG_UPDATER:
            print(f"[updater] Baixando atualização de: {DOWNLOAD_URL}")
        
        # Cria arquivo temporário
        temp_dir = tempfile.gettempdir()
        zip_path = os.path.join(temp_dir, f"confeitaria_update_{int(datetime.now().timestamp())}.zip")
        
        if progress_callback:
            progress_callback(20, "Conectando ao servidor...")
        
        headers = {
            "User-Agent": "Confeitaria-Updater/1.0",
        }
        
        # Adiciona autenticação se tiver token (repositório privado)
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        
        req = urllib.request.Request(DOWNLOAD_URL, headers=headers)
        
        # Download com progresso
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            
            if progress_callback:
                progress_callback(30, f"Baixando... (0%)")
            
            downloaded = 0
            chunk_size = 8192
            
            with open(zip_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0 and progress_callback:
                        percent = int((downloaded / total_size) * 60) + 30  # 30-90%
                        size_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        progress_callback(
                            percent, 
                            f"Baixando... ({size_mb:.1f}/{total_mb:.1f} MB)"
                        )
        
        if progress_callback:
            progress_callback(90, "Download concluído!")
        
        if DEBUG_UPDATER:
            print(f"[updater] ✅ Download concluído: {zip_path}")
        
        return True, zip_path, None
        
    except Exception as e:
        error_msg = f"Erro ao baixar atualização: {e}"
        if DEBUG_UPDATER:
            print(f"[updater] ❌ {error_msg}")
        return False, None, error_msg


def apply_update(zip_path: str, progress_callback: Optional[Callable[[int, str], None]] = None) -> Tuple[bool, Optional[str]]:
    """
    Aplica a atualização baixada
    
    Args:
        zip_path: Caminho do arquivo ZIP baixado
        progress_callback: Função chamada com (progresso_percentual, mensagem)
    
    Returns:
        Tuple[bool, Optional[str]]: (sucesso, mensagem_erro)
    """
    backup_dir = None
    install_dir = None
    
    try:
        if progress_callback:
            progress_callback(92, "Preparando instalação...")
        
        install_dir = get_install_directory()
        
        if DEBUG_UPDATER:
            print(f"[updater] Instalando atualização em: {install_dir}")
        
        # Cria backup antes de atualizar
        backup_dir = os.path.join(tempfile.gettempdir(), f"confeitaria_backup_{int(datetime.now().timestamp())}")
        
        if progress_callback:
            progress_callback(94, "Criando backup de segurança...")
        
        # Faz backup dos arquivos que serão substituídos
        files_to_backup = ['Confeitaria.py', 'core', 'ui', 'src']
        for item in files_to_backup:
            src = os.path.join(install_dir, item)
            if os.path.exists(src):
                dst = os.path.join(backup_dir, item)
                try:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                except Exception as e:
                    if DEBUG_UPDATER:
                        print(f"[updater] Aviso ao fazer backup de {item}: {e}")
        
        if DEBUG_UPDATER:
            print(f"[updater] Backup criado em: {backup_dir}")
        
        if progress_callback:
            progress_callback(96, "Extraindo arquivos...")
        
        # Extrai o ZIP
        temp_extract = os.path.join(tempfile.gettempdir(), f"confeitaria_extract_{int(datetime.now().timestamp())}")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
        
        # O GitHub cria uma pasta com nome do repo-branch
        extracted_folder = None
        for item in os.listdir(temp_extract):
            item_path = os.path.join(temp_extract, item)
            if os.path.isdir(item_path):
                extracted_folder = item_path
                break
        
        if not extracted_folder:
            raise Exception("Estrutura do ZIP inválida")
        
        if DEBUG_UPDATER:
            print(f"[updater] Arquivos extraídos em: {extracted_folder}")
        
        if progress_callback:
            progress_callback(98, "Instalando atualização...")
        
        # Lista de arquivos/pastas para atualizar (exclui dados do usuário)
        items_to_update = [
            'Confeitaria.py',
            'core',
            'ui',
            'src',
            'web',
            'assets',
        ]
        
        # Copia os arquivos atualizados
        for item in items_to_update:
            src = os.path.join(extracted_folder, item)
            dst = os.path.join(install_dir, item)
            
            if not os.path.exists(src):
                if DEBUG_UPDATER:
                    print(f"[updater] Item não encontrado no update: {item}")
                continue
            
            try:
                # Remove o destino se existir
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                
                # Copia o novo
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                
                if DEBUG_UPDATER:
                    print(f"[updater] ✅ Atualizado: {item}")
                    
            except Exception as e:
                if DEBUG_UPDATER:
                    print(f"[updater] ⚠️ Erro ao atualizar {item}: {e}")
                # Não interrompe, tenta continuar com os outros arquivos
        
        # Atualiza o arquivo de versão local
        try:
            version_file = os.path.join(install_dir, 'version.json')
            _, remote_version_info, _ = check_for_updates()
            if remote_version_info:
                with open(version_file, 'w', encoding='utf-8') as f:
                    json.dump(remote_version_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if DEBUG_UPDATER:
                print(f"[updater] Aviso ao salvar version.json: {e}")
        
        # Limpa cache do PyQt6 para forçar recarregamento de recursos
        try:
            import sys
            # Remove módulos em cache para forçar reload
            modules_to_clear = ['ui', 'core', 'src']
            for module_name in list(sys.modules.keys()):
                for prefix in modules_to_clear:
                    if module_name.startswith(prefix):
                        del sys.modules[module_name]
                        if DEBUG_UPDATER:
                            print(f"[updater] Cache limpo: {module_name}")
        except Exception as e:
            if DEBUG_UPDATER:
                print(f"[updater] Aviso ao limpar cache: {e}")
        
        # Limpa arquivos temporários
        try:
            shutil.rmtree(temp_extract)
            os.remove(zip_path)
        except Exception as e:
            if DEBUG_UPDATER:
                print(f"[updater] Aviso ao limpar temporários: {e}")
        
        if progress_callback:
            progress_callback(100, "Atualização concluída!")
        
        if DEBUG_UPDATER:
            print(f"[updater] ✅ Atualização aplicada com sucesso!")
            print(f"[updater] 📁 Backup mantido em: {backup_dir}")
        
        return True, None
        
    except Exception as e:
        error_msg = f"Erro ao aplicar atualização: {e}"
        if DEBUG_UPDATER:
            print(f"[updater] ❌ {error_msg}")
        
        # Tenta restaurar o backup em caso de erro
        if backup_dir is not None and os.path.exists(backup_dir) and install_dir is not None:
            try:
                if DEBUG_UPDATER:
                    print(f"[updater] Tentando restaurar backup...")
                
                for item in os.listdir(backup_dir):
                    src = os.path.join(backup_dir, item)
                    dst = os.path.join(install_dir, item)
                    
                    if os.path.exists(dst):
                        if os.path.isdir(dst):
                            shutil.rmtree(dst)
                        else:
                            os.remove(dst)
                    
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                
                if DEBUG_UPDATER:
                    print(f"[updater] ✅ Backup restaurado")
                    
            except Exception as restore_error:
                if DEBUG_UPDATER:
                    print(f"[updater] ❌ Erro ao restaurar backup: {restore_error}")
        
        return False, error_msg


class UpdaterThread(QThread):
    """Thread para executar atualização em background"""
    
    # Sinais
    progress = pyqtSignal(int, str)  # (percentual, mensagem)
    finished = pyqtSignal(bool, str)  # (sucesso, mensagem)
    
    def __init__(self, auto_apply: bool = False):
        super().__init__()
        self.auto_apply = auto_apply
        self._stop = False
    
    def stop(self):
        """Para a execução da thread"""
        self._stop = True
    
    def run(self):
        """Executa verificação e download da atualização"""
        try:
            if self._stop:
                return
            
            # Verifica se há atualização
            self.progress.emit(5, "Verificando atualizações...")
            has_update, version_info, error = check_for_updates()
            
            if self._stop:
                return
            
            if error:
                self.finished.emit(False, f"Erro ao verificar atualizações: {error}")
                return
            
            if not has_update:
                self.finished.emit(True, "Sistema já está atualizado!")
                return
            
            # Há atualização disponível
            remote_version = version_info.get('version', 'desconhecida') if version_info else 'desconhecida'
            changelog = version_info.get('changelog', []) if version_info else []
            
            if not self.auto_apply:
                # Apenas notifica que há atualização
                msg = f"Atualização disponível: v{remote_version}\n\n"
                if changelog:
                    msg += "Novidades:\n" + "\n".join(f"• {item}" for item in changelog[:5])
                self.finished.emit(True, msg)
                return
            
            # Download automático
            if self._stop:
                return
            
            success, zip_path, error = download_update(
                progress_callback=lambda p, m: self.progress.emit(p, m) if not self._stop else None
            )
            
            if self._stop:
                return
            
            if not success or zip_path is None:
                self.finished.emit(False, f"Erro ao baixar atualização: {error}")
                return
            
            # Aplicar atualização
            if self._stop:
                return
            
            success, error = apply_update(
                zip_path,
                progress_callback=lambda p, m: self.progress.emit(p, m) if not self._stop else None
            )
            
            if self._stop:
                return
            
            if success:
                self.finished.emit(
                    True, 
                    f"✅ Atualização para v{remote_version} concluída!\n\n"
                    "Reinicie o aplicativo para usar a nova versão."
                )
            else:
                self.finished.emit(False, f"Erro ao aplicar atualização: {error}")
                
        except Exception as e:
            if not self._stop:
                self.finished.emit(False, f"Erro inesperado: {e}")


def get_current_version() -> str:
    """Retorna a versão atual do sistema"""
    return CURRENT_VERSION


def update_version_globally(version: str) -> None:
    """
    Atualiza a versão atual do sistema.
    Usado após uma atualização bem-sucedida.
    
    Note: Em Python, não podemos modificar uma constante global diretamente,
    então esta função atualiza o arquivo version.json local.
    """
    try:
        install_dir = get_install_directory()
        version_file = os.path.join(install_dir, 'version.json')
        
        # Lê o arquivo atual
        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
        # Atualiza a versão
        data['version'] = version
        data['release_date'] = datetime.now().strftime('%Y-%m-%d')
        
        # Salva
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        if DEBUG_UPDATER:
            print(f"[updater] Versão atualizada para v{version}")
            
    except Exception as e:
        if DEBUG_UPDATER:
            print(f"[updater] Erro ao atualizar versão: {e}")

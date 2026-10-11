# -*- coding: utf-8 -*-
"""Ponto de entrada: cria QApplication, login, tema e janela principal."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from core.extended_database import ExtendedDatabase
from core.paths import DB_PATH, get_db_path
from ui.main_window import MainWindow
from ui.messages import show_message
from ui.theme.qss import apply_theme


# -----------------------------
# App bootstrap
# -----------------------------
def _install_pt_br_translation(app: QApplication) -> None:
    """Traduz os textos padrão do Qt (OK/Cancel/Save/Close, calendário) para pt-BR."""
    from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
    QLocale.setDefault(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil))
    translator = QTranslator(app)
    if translator.load("qtbase_pt_BR", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)


def main() -> None:
    # =====================================================================
    # FORÇAR UTF-8 NO WINDOWS PARA EVITAR ERROS COM EMOJIS
    # =====================================================================
    if sys.platform == 'win32':
        try:
            import io
            # Forçar codificação UTF-8 no stdout/stderr para suportar emojis
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception as e:
            # Se falhar, continuar sem emojis - não crítico
            print(f"[AVISO] Nao foi possivel configurar UTF-8: {e}")
    
    # =====================================================================
    # =====================================================================
    # APLICAÇÃO LOCAL - SEM VALIDAÇÃO DE LICENÇA
    # =====================================================================
    # =====================================================================
    
    # Auth/Login (usará seus módulos se existirem)
    try:
        from core.services import AuthService
        from ui.dialogs.login_dialog import LoginDialog, load_saved_credentials
        from core.logger import log_event, log_error, log_warning
        from ui.dialogs.custom_messagebox import CustomMessageBox  # apenas para garantir disponibilidade
        from core.config import load_config, get_database_path
        config = load_config()
        theme = config.get("theme", "light")
        
        # Log de inicialização
        log_event("="*60)
        log_event("SISTEMA CONFEITARIA INICIADO")
        log_event(f"Versão do executável: {sys.executable if getattr(sys, 'frozen', False) else 'Script Python'}")
        log_event(f"Tema aplicado: {theme}")
        log_event("="*60)
    except Exception as ex:
        AuthService = None
        LoginDialog = None
        log_event = lambda *args, **kwargs: None
        log_error = lambda *args, **kwargs: None
        log_warning = lambda *args, **kwargs: None
        theme = "light"
        get_database_path = lambda: DB_PATH  # fallback
        print(f"⚠️ Erro ao carregar módulos: {ex}")

    # Cria aplicação Qt
    app = QApplication(sys.argv)
    _install_pt_br_translation(app)
    # Tema aplicado já aqui para login e mensagens de inicialização seguirem o visual
    apply_theme(app, theme)
    
    # Usa o caminho do banco configurado ou o padrão
    try:
        db_path = get_database_path()
        print(f"Usando banco de dados: {db_path}")
        log_event(f"📁 Caminho do banco: {db_path}")
    except Exception as e:
        print(f"Erro ao carregar caminho do banco: {e}. Usando padrão.")
        log_warning(f"Erro ao carregar caminho configurado, usando padrão: {e}")
        db_path = get_db_path()  # Usa função em vez de constante
        log_event(f"📁 Usando caminho padrão: {db_path}")
    
    # Função para verificar se arquivo é um banco SQLite válido
    def is_valid_sqlite_file(path: str) -> bool:
        try:
            if not os.path.exists(path):
                return False
            if os.path.getsize(path) == 0:
                return False
            import sqlite3
            conn = sqlite3.connect(path)
            conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            conn.close()
            return True
        except Exception:
            return False
    
    # Função para criar backup de arquivo corrompido
    def backup_corrupted_file(path: str) -> bool:
        try:
            if os.path.exists(path):
                backup_path = f"{path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Tenta mover primeiro
                try:
                    import shutil
                    shutil.move(path, backup_path)
                    print(f"Arquivo corrompido movido para: {backup_path}")
                    log_warning(f"⚠️ Banco corrompido movido para: {backup_path}")
                    return True
                except (PermissionError, OSError):
                    # Se não consegue mover, tenta deletar
                    print(f"Não foi possível mover arquivo, tentando deletar: {path}")
                    try:
                        os.remove(path)
                        print(f"Arquivo corrompido removido: {path}")
                        return True
                    except (PermissionError, OSError):
                        # Se não consegue deletar, renomeia
                        try:
                            temp_path = f"{path}.temp_corrupted"
                            os.rename(path, temp_path)
                            print(f"Arquivo corrompido renomeado para: {temp_path}")
                            return True
                        except Exception:
                            print(f"Não foi possível remover arquivo corrompido: {path}")
                            return False
        except Exception as e:
            print(f"Erro ao processar arquivo corrompido: {e}")
        return False
    
    # Tenta conectar ao banco
    try:
        # Verifica se o arquivo é válido antes de tentar conectar
        if not is_valid_sqlite_file(db_path):
            raise sqlite3.DatabaseError(f"Arquivo não é um banco de dados SQLite válido: {db_path}")
        
        db = ExtendedDatabase(db_path)
        print(f"Conectado com sucesso ao banco: {db_path}")
    except Exception as e:
        print(f"Erro ao conectar ao banco {db_path}: {e}")
        
        # Se o banco configurado falhou, tenta o padrão
        default_path = get_db_path()
        if db_path != default_path:
            print(f"Tentando banco padrão: {default_path}")
            try:
                if not is_valid_sqlite_file(default_path):
                    # Se arquivo padrão também está corrompido, remove e cria novo
                    if os.path.exists(default_path):
                        backup_corrupted_file(default_path)
                        print("Arquivo padrão corrompido removido, será criado novo banco")
                
                db = ExtendedDatabase(default_path)
                print(f"Conectado com sucesso ao banco padrão: {default_path}")
            except Exception as e2:
                print(f"Erro ao conectar ao banco padrão: {e2}")
                
                # Último recurso: criar banco temporário
                try:
                    from core.config import get_app_data_directory
                    temp_db_path = os.path.join(get_app_data_directory(), f"confeitaria_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
                    os.makedirs(os.path.dirname(temp_db_path), exist_ok=True)
                    print(f"Criando banco temporário: {temp_db_path}")
                    db = ExtendedDatabase(temp_db_path)
                    
                    # Mostra mensagem para o usuário
                    from PyQt6.QtWidgets import QMessageBox
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Banco de Dados Corrompido")
                    msg.setText("Os arquivos de banco de dados estavam corrompidos e foram substituídos.")
                    msg.setInformativeText(f"Um novo banco temporário foi criado:\n\n{temp_db_path}\n\nRecomenda-se restaurar um backup ou reconfigurar o banco nas configurações.")
                    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg.exec()
                    
                except Exception as e3:
                    # Erro fatal - não conseguiu criar nenhum banco
                    try:
                        from PyQt6.QtWidgets import QMessageBox
                        msg = QMessageBox()
                        msg.setIcon(QMessageBox.Icon.Critical)
                        msg.setWindowTitle("Erro Fatal")
                        msg.setText("Não foi possível inicializar nenhum banco de dados.")
                        msg.setDetailedText(f"Erro original: {e}\nErro banco padrão: {e2}\nErro banco temporário: {e3}")
                        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                        msg.exec()
                    except Exception:
                        print(f"ERRO FATAL: Não foi possível inicializar banco de dados.")
                        print(f"Erro original: {e}")
                        print(f"Erro banco padrão: {e2}")
                        print(f"Erro banco temporário: {e3}")
                    sys.exit(1)
        else:
            # Se já estava tentando o banco padrão e falhou
            print("Banco padrão falhou, tentando criar novo banco limpo")
            default_path = get_db_path()
            try:
                # Remove arquivo corrompido se existir
                if os.path.exists(default_path):
                    success = backup_corrupted_file(default_path)
                    if not success:
                        print("Não foi possível remover arquivo corrompido, tentando criar banco em local alternativo")
                        # Cria banco em local alternativo
                        from core.config import get_app_data_directory
                        alt_db_path = os.path.join(get_app_data_directory(), "confeitaria_recovery.db")
                        os.makedirs(os.path.dirname(alt_db_path), exist_ok=True)
                        print(f"Criando banco alternativo: {alt_db_path}")
                        db = ExtendedDatabase(alt_db_path)
                        print(f"Banco alternativo criado com sucesso: {alt_db_path}")
                    else:
                        print("Criando novo banco no local padrão")
                        db = ExtendedDatabase(default_path)
                        print(f"Novo banco criado: {default_path}")
                else:
                    print("Criando novo banco no local padrão")
                    db = ExtendedDatabase(default_path)
                    print(f"Novo banco criado: {default_path}")
                    
            except Exception as e2:
                print(f"Erro ao criar novo banco no local padrão: {e2}")
                try: log_error(f"Erro ao criar banco padrão: {e2}")
                except Exception: pass
                # Último recurso: banco temporário
                try:
                    from core.config import get_app_data_directory
                    temp_db_path = os.path.join(get_app_data_directory(), f"confeitaria_emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
                    os.makedirs(os.path.dirname(temp_db_path), exist_ok=True)
                    print(f"ÚLTIMO RECURSO: Criando banco de emergência: {temp_db_path}")
                    try: log_warning(f"Criando banco de emergência: {temp_db_path}")
                    except Exception: pass
                    db = ExtendedDatabase(temp_db_path)
                    print(f"Banco de emergência criado: {temp_db_path}")
                    try: log_event(f"✅ Banco de emergência criado")
                    except Exception: pass
                except Exception as e3:
                    print(f"ERRO FATAL: Não foi possível criar nenhum banco: {e3}")
                    try: log_error(f"ERRO FATAL: Não foi possível criar banco: {e3}")
                    except Exception: pass
                    sys.exit(1)

    user = None

    # Sempre exige login - usa a tela original do projeto
    if LoginDialog and AuthService:
        log_event("🔐 Iniciando processo de autenticação...")
        auth = AuthService(db)

        # Login automático: se há credenciais salvas ("Lembrar credenciais") e o
        # usuário não está segurando Shift (forma de forçar a tela de login para
        # trocar de conta), tenta autenticar direto sem mostrar o diálogo.
        shift_held = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        if not shift_held:
            saved = load_saved_credentials()
            if saved:
                auto_username, auto_password = saved
                user = auth.authenticate(auto_username, auto_password)
                if user:
                    log_event(f"✅ Login automático: {auto_username} (Perfil: {user.role})")
                else:
                    log_warning(f"❌ Login automático falhou para '{auto_username}' "
                                f"(credenciais salvas inválidas ou conta bloqueada) - pedindo login manual")

        while user is None:
            dlg = LoginDialog()
            if dlg.exec() == QDialog.DialogCode.Accepted:
                username, password = dlg.get_values()
                log_event(f"🔑 Tentativa de login: {username}")
                user = auth.authenticate(username, password)
                if user:
                    log_event(f"✅ Login bem-sucedido: {username} (Perfil: {user.role})")
                else:
                    log_warning(f"❌ Login falhou para usuário: {username}")
                    show_message(None, "Login falhou", auth.last_error or "Usuário ou senha inválidos.", ("OK",))
            else:
                log_event("❌ Login cancelado pelo usuário")
                sys.exit(0)
    else:
        # Se os módulos não carregarem, mostra erro e sai
        log_error("ERRO FATAL: Módulos de autenticação não carregados")
        show_message(None, "Erro", "Não foi possível carregar os módulos de autenticação.", ("OK",))
        sys.exit(1)

    win = MainWindow(user)
    
    # Aplica tema inicial conforme configuração salva
    try:
        from core.config import load_config
        cfg = load_config()
        # Carrega o tema salvo (padrão: light)
        theme = cfg.get('theme', 'light')
    except Exception:
        theme = 'light'
    
    apply_theme(app, theme)
    win.show()
    sys.exit(app.exec())

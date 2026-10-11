# database.py
# Responsável pela conexão e operações com o banco de dados SQLite

import sqlite3
import shutil
import os
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import Any, Iterator, List, Tuple, Union, Mapping

# Parameter type accepted by sqlite3 (positional tuple or named mapping)
Params = Union[Tuple[Any, ...], Mapping[str, Any]]

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Conexão com configurações mais seguras para concorrência (multi-processo)
        # check_same_thread=False permite uso pelo Qt em threads diferentes da principal (quando necessário)
        # timeout define quanto esperar em locks antes de falhar
        self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Quando True (dentro de um "with self.transaction():"), execute() não commita
        # a cada chamada - só no final do bloco. Sem isso, uma exclusão/criação em lote
        # de centenas de itens faz centenas de commits síncronos seguidos, cada um
        # esperando o SQLite gravar em disco, e a janela fica sem responder por vários
        # segundos (o Windows chega a marcar como "não está respondendo").
        self._in_transaction = False
        # PRAGMAs para melhorar concorrência e integridade
        try:
            c = self.conn.cursor()
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA journal_mode=WAL")  # leitores não bloqueiam escritor
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA busy_timeout=5000")  # 5s de espera em lock
            c.execute("PRAGMA temp_store=MEMORY")
            self.conn.commit()
        except Exception:
            pass
        self._init_db()

    def _init_db(self):
        try:
            import bcrypt
        except ImportError:
            bcrypt = None
            
        cur = self.conn.cursor()
        # Tabela de usuários
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
            """
        )
        self.conn.commit()
        # Usuário admin padrão (senha "admin", troca obrigatória no 1º login) só num banco
        # SEM nenhum usuário. Antes bastava não existir alguém chamado "admin": renomear
        # ou excluir o admin fazia o sistema recriar um administrador com senha "admin".
        if not cur.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            if bcrypt:
                password_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            else:
                import hashlib
                password_hash = hashlib.sha256("admin".encode('utf-8')).hexdigest()
            cur.execute("INSERT INTO users(username, password_hash, role) VALUES (?,?,?)", 
                       ("admin", password_hash, "admin"))
            self.conn.commit()

    def execute(self, sql: str, params: Params = ()) -> sqlite3.Cursor:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        if not self._in_transaction:
            self.conn.commit()
        return cur

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        """Agrupa várias chamadas a execute() em um único commit no final.

        Uso: `with self.db.transaction(): ...várias chamadas a self.db.execute()...`
        Essencial para operações em lote (excluir/criar muitos registros de uma vez) -
        sem isso, cada execute() commitava sozinho, e uma exclusão de centenas de itens
        virava centenas de commits síncronos seguidos, travando a interface.
        Reentrante: chamar aninhado só commita/rollback no bloco mais externo.
        """
        already_in_transaction = self._in_transaction
        self._in_transaction = True
        try:
            yield self
            if not already_in_transaction:
                self.conn.commit()
        except Exception:
            if not already_in_transaction:
                self.conn.rollback()
            raise
        finally:
            self._in_transaction = already_in_transaction

    def query(self, sql: str, params: Params = ()) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        except sqlite3.DatabaseError as e:
            if "malformed" in str(e).lower() or "corrupt" in str(e).lower():
                raise sqlite3.DatabaseError(f"Banco de dados corrompido: {e}. Use a função de restaurar backup.")
            raise

    def verify_integrity(self) -> Tuple[bool, str]:
        """Verifica a integridade do banco de dados"""
        try:
            cur = self.conn.cursor()
            result = cur.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] == "ok":
                return True, "Banco de dados íntegro"
            return False, f"Problemas detectados: {result[0] if result else 'desconhecido'}"
        except Exception as e:
            return False, f"Erro ao verificar: {str(e)}"

    def repair_database(self) -> Tuple[bool, str]:
        """Tenta reparar o banco de dados corrompido.

        Antes disso reportava sucesso mesmo quando instruções do dump falhavam
        silenciosamente (bare except) e nunca conferia a integridade do banco
        recriado - podia perder linhas sem avisar. Agora conta quantas
        instruções falharam e só substitui o banco original se o resultado
        passar em PRAGMA integrity_check; senão preserva o original intacto
        (o backup do corrompido já feito continua disponível de qualquer forma).
        """
        try:
            # Cria backup do banco corrompido
            corrupted_backup = f"{self.db_path}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.db_path, corrupted_backup)

            # Tenta recuperar dados
            temp_db = f"{self.db_path}.temp"
            if os.path.exists(temp_db):
                os.remove(temp_db)

            # Cria novo banco
            temp_conn = sqlite3.connect(temp_db)
            temp_conn.row_factory = sqlite3.Row

            # Tenta exportar schema e dados
            try:
                failed_statements: List[str] = []
                total_statements = 0
                for line in self.conn.iterdump():
                    if line.strip() and not line.startswith('COMMIT'):
                        total_statements += 1
                        try:
                            temp_conn.execute(line)
                        except sqlite3.Error as stmt_err:
                            failed_statements.append(f"{line.strip()[:80]} -> {stmt_err}")
                temp_conn.commit()

                # Confere se o banco recriado está íntegro antes de substituir o original
                integrity_ok = False
                try:
                    result = temp_conn.execute("PRAGMA integrity_check").fetchone()
                    integrity_ok = bool(result and result[0] == "ok")
                except sqlite3.Error:
                    integrity_ok = False
                temp_conn.close()

                if not integrity_ok:
                    os.remove(temp_db)
                    return False, (
                        "Reparo abortado: o banco recriado não passou na verificação de "
                        "integridade. O banco original NÃO foi alterado. "
                        f"Backup do corrompido salvo em: {corrupted_backup}"
                    )

                if failed_statements:
                    print(f"⚠️ Reparo do banco: {len(failed_statements)} de {total_statements} instruções "
                          f"do dump falharam e foram descartadas (dados possivelmente perdidos):")
                    for msg in failed_statements[:20]:
                        print(f"   - {msg}")

                # Fecha conexão antiga
                self.conn.close()

                # Substitui banco antigo
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                shutil.move(temp_db, self.db_path)

                # Reconecta
                self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row

                # Garante que o schema está atualizado (idempotente: CREATE TABLE IF NOT
                # EXISTS + checagem de coluna antes de cada ALTER TABLE)
                try:
                    self._init_db()
                except Exception:
                    pass

                if failed_statements:
                    return True, (
                        f"Banco reparado, mas {len(failed_statements)} de {total_statements} "
                        f"instrução(ões) não puderam ser recuperadas - alguns dados podem ter "
                        f"sido perdidos (veja o console para detalhes). "
                        f"Backup do corrompido salvo em: {corrupted_backup}"
                    )
                return True, f"Banco reparado sem perda de dados detectada! Backup do corrompido salvo em: {corrupted_backup}"

            except Exception as e:
                temp_conn.close()
                if os.path.exists(temp_db):
                    os.remove(temp_db)
                return False, f"Erro ao reparar: {str(e)}"

        except Exception as e:
            return False, f"Erro no processo de reparo: {str(e)}"

    def restore_from_backup(self, backup_path: str) -> Tuple[bool, str]:
        """Restaura banco de dados de um backup"""
        try:
            if not os.path.exists(backup_path):
                return False, f"Arquivo de backup não encontrado: {backup_path}"
            
            # Fecha conexão atual
            self.conn.close()
            
            # Faz backup do banco atual antes de substituir
            if os.path.exists(self.db_path):
                old_backup = f"{self.db_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.db_path, old_backup)
            
            # Restaura do backup
            shutil.copy2(backup_path, self.db_path)
            
            # Reconecta
            self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            # Roda as migrações de schema: se o backup for de uma versão mais antiga
            # (ex: sem a coluna stock_movements.category), sem isso o app quebra com
            # "no such column" no primeiro INSERT/SELECT que usar a coluna nova, e o
            # integrity_check abaixo não detectaria isso (ele só olha corrupção de
            # páginas, não colunas/tabelas faltando).
            try:
                self._init_db()
            except Exception as mig_err:
                return False, f"Backup restaurado mas falhou ao atualizar o schema: {mig_err}"

            # Verifica integridade
            is_ok, msg = self.verify_integrity()
            if is_ok:
                return True, f"Backup restaurado com sucesso!\n{msg}"
            else:
                return False, f"Backup restaurado mas com problemas: {msg}"
                
        except Exception as e:
            # Tenta reconectar mesmo com erro
            try:
                self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
            except:
                pass
            return False, f"Erro ao restaurar backup: {str(e)}"

    def create_backup(self, backup_dir: str = None) -> Tuple[bool, str]:
        """Cria um backup do banco de dados"""
        try:
            if backup_dir is None:
                backup_dir = str(Path(self.db_path).parent / "backups")
            
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_name)
            
            # Usa backup API do SQLite para garantir consistência
            backup_conn = sqlite3.connect(backup_path)
            with backup_conn:
                self.conn.backup(backup_conn)
            backup_conn.close()
            
            return True, backup_path
            
        except Exception as e:
            return False, f"Erro ao criar backup: {str(e)}"

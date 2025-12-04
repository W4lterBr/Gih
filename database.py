# database.py
# Responsável pela conexão e operações com o banco de dados SQLite

import sqlite3
from typing import Any, List, Tuple, Union, Mapping

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
        # Cria usuário admin padrão se não existir
        admin = cur.execute("SELECT 1 FROM users WHERE username=?", ("admin",)).fetchone()
        if not admin:
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
        self.conn.commit()
        return cur

    def query(self, sql: str, params: Params = ()) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

# services.py
# Camada de serviços para regras de negócio

import sys
import os
import json
import time
from pathlib import Path

# Adiciona o diretório pai ao path para imports funcionarem
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import bcrypt
except ImportError:
    bcrypt = None  # type: ignore

try:
    from core.models import User
except ImportError:
    # Fallback para quando executado diretamente
    from models import User  # type: ignore

# Bloqueio de tentativas de login: sem isso, um ataque de força bruta local
# contra a tabela `users` era ilimitado (nenhum limite de tentativas existia).
# Persistido em disco (não só em memória) para que reiniciar o app não resete o contador.
MAX_ATTEMPTS_BEFORE_LOCKOUT = 5
BASE_LOCKOUT_SECONDS = 30
MAX_LOCKOUT_SECONDS = 300


def _lockout_file() -> Path:
    from core.config import get_app_data_directory
    return Path(get_app_data_directory()) / "login_attempts.json"


def _load_lockout_state() -> dict:
    try:
        p = _lockout_file()
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def _save_lockout_state(state: dict) -> None:
    try:
        _lockout_file().write_text(json.dumps(state), encoding='utf-8')
    except Exception:
        pass


class AuthService:
    def __init__(self, db):
        self.db = db
        self.last_error: str | None = None

    def _check_lockout(self, username: str) -> tuple[bool, int]:
        """Retorna (bloqueado, segundos_restantes)"""
        state = _load_lockout_state()
        entry = state.get(username.lower())
        if not entry:
            return False, 0
        remaining = entry.get("locked_until", 0) - time.time()
        return (True, int(remaining) + 1) if remaining > 0 else (False, 0)

    def _record_failed_attempt(self, username: str) -> None:
        state = _load_lockout_state()
        key = username.lower()
        entry = state.get(key, {"fails": 0, "locked_until": 0})
        entry["fails"] = entry.get("fails", 0) + 1
        if entry["fails"] >= MAX_ATTEMPTS_BEFORE_LOCKOUT:
            extra = entry["fails"] - MAX_ATTEMPTS_BEFORE_LOCKOUT
            lockout_seconds = min(BASE_LOCKOUT_SECONDS * (2 ** extra), MAX_LOCKOUT_SECONDS)
            entry["locked_until"] = time.time() + lockout_seconds
        state[key] = entry
        _save_lockout_state(state)

    def _clear_failed_attempts(self, username: str) -> None:
        state = _load_lockout_state()
        key = username.lower()
        if key in state:
            del state[key]
            _save_lockout_state(state)

    def authenticate(self, username: str, password: str) -> User | None:
        self.last_error = None

        locked, remaining = self._check_lockout(username)
        if locked:
            self.last_error = f"Muitas tentativas incorretas. Tente novamente em {remaining}s."
            return None

        row = self.db.query("SELECT * FROM users WHERE username=?", (username,))
        if not row:
            self._record_failed_attempt(username)
            return None
        user = row[0]
        stored_hash = user["password_hash"]

        if not stored_hash:
            self._record_failed_attempt(username)
            return None

        try:
            # Verifica se é hash bcrypt (começa com $2a$, $2b$, $2y$)
            is_bcrypt = isinstance(stored_hash, str) and stored_hash.startswith('$2')

            if is_bcrypt:
                # NÃO cair no fallback SHA256 aqui: comparar sha256(password) com um hash
                # bcrypt nunca vai bater, então se o pacote bcrypt estiver ausente o usuário
                # ficava travado para sempre mesmo com a senha certa, sem nenhum aviso claro.
                if not bcrypt:
                    print("Erro de autenticação: hash bcrypt salvo, mas o pacote 'bcrypt' "
                          "não está disponível neste ambiente - não é possível verificar a senha")
                    return None
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                    self._clear_failed_attempts(username)
                    return User(id=user["id"], username=user["username"],
                              password_hash=stored_hash, role=user["role"])
            else:
                # Hash legado em SHA256
                import hashlib
                password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                if password_hash == stored_hash:
                    # Faz upgrade para bcrypt se disponível
                    if bcrypt:
                        try:
                            new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            self.db.execute("UPDATE users SET password_hash=? WHERE id=?",
                                          (new_hash, user["id"]))
                        except Exception:
                            pass
                    self._clear_failed_attempts(username)
                    return User(id=user["id"], username=user["username"],
                              password_hash=stored_hash, role=user["role"])
        except Exception as e:
            print(f"Erro de autenticação: {e}")
            return None

        self._record_failed_attempt(username)
        return None

    def create_user(self, username: str, password: str, role: str = "func"):
        """Cria um novo usuário no banco de dados."""
        try:
            # Usa bcrypt se disponível
            if bcrypt:
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            else:
                # Fallback para sha256
                import hashlib
                password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                
            self.db.execute("INSERT INTO users(username, password_hash, role) VALUES (?,?,?)", 
                          (username, password_hash, role))
        except Exception as e:
            print(f"Erro ao criar usuário: {e}")
            raise

class ProductService:
    pass  # CRUD de produtos

class CustomerService:
    pass  # CRUD de clientes

class OrderService:
    pass  # CRUD de pedidos

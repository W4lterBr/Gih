# services.py
# Camada de serviços para regras de negócio

import sys
import os

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

class AuthService:
    def __init__(self, db):
        self.db = db

    def authenticate(self, username: str, password: str) -> User | None:
        row = self.db.query("SELECT * FROM users WHERE username=?", (username,))
        if not row:
            return None
        user = row[0]
        stored_hash = user["password_hash"]
        
        if not stored_hash:
            return None
        
        try:
            # Verifica se é hash bcrypt (começa com $2a$, $2b$, $2y$)
            is_bcrypt = isinstance(stored_hash, str) and stored_hash.startswith('$2')
            
            if bcrypt and is_bcrypt:
                # Tenta autenticar com bcrypt
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                    return User(id=user["id"], username=user["username"], 
                              password_hash=stored_hash, role=user["role"])
            else:
                # Tenta SHA256 como fallback
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
                    return User(id=user["id"], username=user["username"], 
                              password_hash=stored_hash, role=user["role"])
        except Exception as e:
            print(f"Erro de autenticação: {e}")
            return None
        
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

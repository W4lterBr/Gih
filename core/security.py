# -*- coding: utf-8 -*-
"""Hash e verificação de senhas (bcrypt com fallback SHA-256 legado)."""

from __future__ import annotations

import hashlib


# Senha: usa bcrypt se disponível, senão sha256 como fallback (marcado com prefixo)
try:
    import bcrypt  # type: ignore
except Exception:
    bcrypt = None


def hash_password(password: str) -> str:
    """Retorna o hash da senha usando bcrypt, com fallback para SHA256."""
    if not password:
        return ""
    try:
        if bcrypt:
            h = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            return h.decode('utf-8')
        else:
            # Fallback para SHA256 se bcrypt não estiver disponível
            import hashlib
            return hashlib.sha256(password.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"Error hashing password with bcrypt, trying SHA256 fallback: {e}")
        try:
            # Último recurso: SHA256
            import hashlib
            return hashlib.sha256(password.encode('utf-8')).hexdigest()
        except Exception as e2:
            print(f"Error hashing password with SHA256: {e2}")
            return ""


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica se a senha corresponde ao hash armazenado, suportando bcrypt e SHA256."""
    if not password or not stored_hash:
        return False
    
    try:
        # Verifica se é hash bcrypt (começa com $2a$, $2b$, $2y$)
        is_bcrypt = stored_hash.startswith('$2')

        if is_bcrypt:
            # Não cai no fallback SHA256 aqui: comparar sha256(password) com um hash bcrypt
            # nunca bate, então sem bcrypt instalado o usuário travaria mesmo com senha certa.
            if not bcrypt:
                print("Error verifying password: hash é bcrypt mas o pacote 'bcrypt' não está disponível")
                return False
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        else:
            # Verifica com SHA256 (hash legado)
            import hashlib
            password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            return password_hash == stored_hash
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False

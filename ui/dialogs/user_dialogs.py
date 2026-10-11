# -*- coding: utf-8 -*-
"""Diálogos de usuário e gerenciamento de usuários."""

from __future__ import annotations

import sqlite3
from typing import Any, Optional, cast

from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import Database
from core.security import hash_password
from ui.messages import show_message


class UserDialog(QDialog):
    """Diálogo para criar/editar usuário (username + password + role)."""
    def __init__(self, parent: Optional[QWidget] = None, data: Optional[sqlite3.Row] = None) -> None:
        super().__init__(parent)
        
        from core.config import load_config
        
            
        self.setWindowTitle("Usuário")
        self.resize(360, 280)
        layout = QFormLayout(self)
        
        # Flag para indicar se é edição ou criação
        self._editing = data is not None
        
        self.username: QLineEdit = QLineEdit()
        self.password: QLineEdit = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirm: QLineEdit = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.role: QComboBox = QComboBox()
        self.role.addItems(["admin", "common"])
        
        layout.addRow("Nome de usuário:", self.username)
        layout.addRow("Senha:", self.password)
        layout.addRow("Confirmar senha:", self.password_confirm)
        layout.addRow("Tipo:", self.role)
        
        # Password placeholder text
        if data:
            self.password.setPlaceholderText("Deixe em branco para manter a senha atual")
            self.password_confirm.setPlaceholderText("Confirme a nova senha se alterando")
        else:
            self.password.setPlaceholderText("Digite uma senha (mínimo 4 caracteres)")
            self.password_confirm.setPlaceholderText("Confirme a senha")
        
        # Info label
        info_label = QLabel("⚠️ A senha deve ter pelo menos 4 caracteres")
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addRow(info_label)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        cast(Any, btns.accepted).connect(self.validate_and_accept)
        cast(Any, btns.rejected).connect(self.reject)
        layout.addRow(btns)
        
        if data:
            self.username.setText(data["username"] or "")
            try:
                self.role.setCurrentText(data["role"] or "common")
            except Exception:
                pass

    def validate_and_accept(self) -> None:
        """Valida os dados antes de aceitar o diálogo"""
        username = self.username.text().strip()
        password = self.password.text().strip()
        password_confirm = self.password_confirm.text().strip()
        
        # Validações
        if not username:
            self.show_error("Nome de usuário é obrigatório")
            return
        
        if len(username) < 3:
            self.show_error("Nome de usuário deve ter pelo menos 3 caracteres")
            return
        
        # Se é novo usuário, senha é obrigatória
        if not self._editing and not password:
            self.show_error("Senha é obrigatória para novos usuários")
            return
        
        # Se senha foi fornecida, precisa validar
        if password:
            if len(password) < 4:
                self.show_error("A senha deve ter pelo menos 4 caracteres")
                return
            
            if password != password_confirm:
                self.show_error("As senhas não coincidem")
                return
        
        # Se chegou até aqui, está tudo OK
        self.accept()
    
    def show_error(self, message: str) -> None:
        """Mostra uma mensagem de erro"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Erro", message)

    def get_values(self) -> tuple[str, str, str]:
        """Returns (username, password, role). Password may be empty if unchanged."""
        return (
            self.username.text().strip(),
            self.password.text().strip(),
            self.role.currentText()
        )


class UsersDialog(QDialog):
    """Diálogo simples para listar/criar/editar/excluir usuários.

    Exibirá apenas para administradores (visibilidade controlada externamente).
    """
    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        from core.config import load_config
        
            
        self.db = db
        self.setWindowTitle("Usuários do Sistema")
        self.resize(480, 320)
        v = QVBoxLayout(self)
        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(["Nome de usuário", "Tipo"])
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        if h := self.tbl.horizontalHeader():
            h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            h.setStretchLastSection(True)
        v.addWidget(self.tbl)

        h = QHBoxLayout()
        self.btn_add = QPushButton("Adicionar")
        self.btn_edit = QPushButton("Editar")
        self.btn_del = QPushButton("Excluir")
        h.addWidget(self.btn_add); h.addWidget(self.btn_edit); h.addWidget(self.btn_del); h.addStretch(1)
        v.addLayout(h)

        cast(Any, self.btn_add.clicked).connect(self.add)
        cast(Any, self.btn_edit.clicked).connect(self.edit)
        cast(Any, self.btn_del.clicked).connect(self.delete)

        self.refresh()

    def refresh(self) -> None:
        rows = self.db.query("SELECT id, username, role FROM users ORDER BY username")
        self.tbl.setRowCount(0)
        for r in rows:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            self.tbl.setItem(row, 0, QTableWidgetItem(str(r["username"])))
            self.tbl.setItem(row, 1, QTableWidgetItem(str(r["role"] or "common")))
            self.tbl.setVerticalHeaderItem(row, QTableWidgetItem(str(r["id"])))
        self.tbl.resizeColumnsToContents()

    def current_id(self) -> Optional[int]:
        idx = self.tbl.currentRow()
        if idx < 0:
            return None
        vh = self.tbl.verticalHeaderItem(idx)
        return int(vh.text()) if vh else None

    def add(self) -> None:
        d = UserDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                username, password, role = d.get_values()
                if not username:
                    raise ValueError("Nome de usuário é obrigatório")
                if not password:
                    raise ValueError("Senha é obrigatória para novos usuários")

                # Checagem amigável de duplicidade - sem isso o erro era só o
                # IntegrityError cru do SQLite (UNIQUE constraint failed: users.username)
                # mostrado direto pro usuário via show_message(..., str(e), ...)
                existing = self.db.query("SELECT 1 FROM users WHERE username=?", (username,))
                if existing:
                    raise ValueError(f"Já existe um usuário com o nome '{username}'.")

                # Debug: verificar se a senha não está vazia
                print(f"Debug: Criando usuário '{username}' com senha de {len(password)} caracteres")

                password_hash = hash_password(password)
                if not password_hash:
                    raise ValueError("Erro ao gerar hash da senha. Verifique se a senha foi inserida corretamente.")

                print(f"Debug: Hash gerado: {password_hash[:50]}...")  # Log parcial do hash para debug

                self.db.execute("INSERT INTO users(username, password_hash, role) VALUES (?,?,?)", (username, password_hash, role))
                print(f"Debug: Usuário '{username}' inserido no banco com sucesso")
                self.refresh()
            except Exception as e:
                print(f"Debug: Erro ao adicionar usuário: {e}")
                show_message(self, "Erro", str(e), ("OK",))

    def edit(self) -> None:
        uid = self.current_id()
        if not uid:
            return
        row = self.db.query("SELECT * FROM users WHERE id=?", (uid,))
        if not row:
            return
        d = UserDialog(self, row[0])  # row[0] já faz com que _editing seja True
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                username, password, role = d.get_values()
                if not username:
                    raise ValueError("Nome de usuário é obrigatório")
                    
                # Debug: verificar se a senha foi alterada
                if password:
                    print(f"Debug: Atualizando senha para usuário '{username}' (nova senha tem {len(password)} caracteres)")
                    password_hash = hash_password(password)
                    if not password_hash:
                        raise ValueError("Erro ao gerar hash da nova senha. Verifique se a senha foi inserida corretamente.")
                    print(f"Debug: Novo hash gerado: {password_hash[:50]}...")
                    self.db.execute("UPDATE users SET username=?, password_hash=?, role=? WHERE id=?", 
                                  (username, password_hash, role, uid))
                    
                    # Verificação extra: confirma que foi salvo
                    check = self.db.query("SELECT password_hash FROM users WHERE id=?", (uid,))
                    if check and check[0]['password_hash'] == password_hash:
                        print(f"Debug: ✅ Senha atualizada e verificada no banco")
                    else:
                        print(f"Debug: ❌ ERRO: Senha não foi persistida corretamente!")
                        raise ValueError("Erro: a senha não foi salva corretamente no banco de dados")
                else:
                    print(f"Debug: Atualizando usuário '{username}' sem alterar a senha")
                    self.db.execute("UPDATE users SET username=?, role=? WHERE id=?", 
                                  (username, role, uid))
                print(f"Debug: Usuário '{username}' atualizado com sucesso")
                self.refresh()
            except Exception as e:
                print(f"Debug: Erro ao editar usuário: {e}")
                show_message(self, "Erro", str(e), ("OK",))

    def delete(self) -> None:
        uid = self.current_id()
        if not uid:
            return

        row = self.db.query("SELECT username, role FROM users WHERE id=?", (uid,))
        if not row:
            return
        target_username = row[0]["username"]
        target_role = row[0]["role"]

        # Impede excluir a própria conta logada - sem isso dava pra se auto-excluir
        # no meio da sessão e ficar num estado inconsistente (sessão ativa de um
        # usuário que não existe mais no banco).
        current_user = getattr(self.db, "current_user", None)
        if current_user and str(current_user).lower() == str(target_username).lower():
            show_message(self, "Não é possível excluir",
                         "Você não pode excluir seu próprio usuário enquanto está logado com ele.",
                         ("OK",))
            return

        # Impede excluir o último administrador restante - sem isso dava pra trancar
        # todo mundo fora da tela de Usuários (só admin acessa), sem forma de
        # recuperar o acesso a não ser mexendo direto no banco.
        if target_role == "admin":
            admin_count = self.db.query("SELECT COUNT(*) AS c FROM users WHERE role='admin'")
            if admin_count and int(admin_count[0]["c"]) <= 1:
                show_message(self, "Não é possível excluir",
                             "Este é o único administrador do sistema. Crie outro administrador "
                             "antes de excluir este.",
                             ("OK",))
                return

        res = show_message(self, "Confirmação", "Excluir este usuário?", ("Não", "Sim"), default=1)
        if res == 1:
            try:
                self.db.execute("DELETE FROM users WHERE id=?", (uid,))
                self.refresh()
            except Exception as e:
                show_message(self, "Erro", str(e), ("OK",))

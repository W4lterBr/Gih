# -*- coding: utf-8 -*-
"""Database com migrações de schema, auditoria e reserva de estoque."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from core.database import Database
from core.paths import base_dir


# -----------------------------
# Database helpers
# -----------------------------
class ExtendedDatabase(Database):
    """Extende core Database com schema do app."""
    def _init_db(self) -> None:
        super()._init_db()
        cur = self.conn.cursor()
        # Clientes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                birthday TEXT,
                observation TEXT
            )
        """)
        cur.execute("PRAGMA table_info(customers)")
        _cust_cols = [row[1] for row in cur.fetchall()]
        if "observation" not in _cust_cols:
            cur.execute("ALTER TABLE customers ADD COLUMN observation TEXT")
        if "birthday" not in _cust_cols:
            cur.execute("ALTER TABLE customers ADD COLUMN birthday TEXT")
        self.conn.commit()

        # Auditoria / logs de ações (CRUD)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity TEXT NOT NULL,
                entity_id INTEGER,
                action TEXT NOT NULL,
                user TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

        # Produtos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                size TEXT,
                stock INTEGER NOT NULL DEFAULT 0,
                min_stock INTEGER NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0.0
            )
        """)
        
        # Adicionar coluna price se não existir (migração)
        try:
            cur.execute("ALTER TABLE products ADD COLUMN price REAL NOT NULL DEFAULT 0.0")
        except Exception:
            pass  # Coluna já existe

        # Pedidos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number INTEGER UNIQUE,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                delivery_date TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL,
                label TEXT DEFAULT 'Comum',
                notes TEXT,
                stock_reserved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        """)

        # Migração: adiciona order_number se faltar
        cur.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in cur.fetchall()]
        if "order_number" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN order_number INTEGER")
            self.conn.commit()
        
        # Migração: adiciona stock_reserved se faltar
        cur.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in cur.fetchall()]
        if "stock_reserved" not in columns:
            # Adiciona coluna e marca pedidos com delivery_date <= hoje como já reservados
            cur.execute("ALTER TABLE orders ADD COLUMN stock_reserved INTEGER NOT NULL DEFAULT 0")
            # Marca pedidos antigos (já entregues ou com data passada) como reservados
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("UPDATE orders SET stock_reserved=1 WHERE delivery_date <= ?", (today,))
            self.conn.commit()
            print("✓ Campo stock_reserved adicionado. Pedidos antigos marcados como reservados.")
        
        # Migração: adiciona label (etiqueta) se não existir
        cur.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in cur.fetchall()]
        if "label" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN label TEXT DEFAULT 'Comum'")
            self.conn.commit()
            print("✓ Campo 'label' (etiqueta) adicionado em orders.")
        
        # Migração: adiciona size (tamanho) na tabela products se faltar
        cur.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cur.fetchall()]
        if "size" not in columns:
            cur.execute("ALTER TABLE products ADD COLUMN size TEXT")
            self.conn.commit()
        
        # Migração: remove requires_min_stock (atribuição) de products se existir
        cur.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cur.fetchall()]
        if "requires_min_stock" in columns:
            try:
                print("🔄 Removendo campo 'requires_min_stock' (atribuição) da tabela products...")
                cur.execute("DROP TABLE IF EXISTS products_new")
                cur.execute("PRAGMA foreign_keys=OFF")
                cur.execute("BEGIN IMMEDIATE")
                
                # Cria nova tabela sem requires_min_stock
                cur.execute("""
                    CREATE TABLE products_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        size TEXT,
                        stock INTEGER NOT NULL DEFAULT 0,
                        min_stock INTEGER NOT NULL DEFAULT 0,
                        price REAL NOT NULL DEFAULT 0.0
                    )
                """)
                
                # Copia dados (sem requires_min_stock; price já existe pela migração acima)
                cur.execute("""
                    INSERT INTO products_new (id, name, description, size, stock, min_stock, price)
                    SELECT id, name, description, size, stock, min_stock, COALESCE(price, 0) FROM products
                """)
                
                # Remove tabela antiga e renomeia
                cur.execute("DROP TABLE products")
                cur.execute("ALTER TABLE products_new RENAME TO products")
                
                self.conn.commit()
                cur.execute("PRAGMA foreign_keys=ON")
                print("✓ Campo 'requires_min_stock' removido com sucesso!")
                
            except Exception as e:
                self.conn.rollback()
                try:
                    cur.execute("PRAGMA foreign_keys=ON")
                except:
                    pass
                print(f"⚠️ Não foi possível remover campo requires_min_stock: {e}")
        
        # (Havia aqui uma migração que removia a coluna price. Ela falhava sempre por
        # erro de sintaxe e, se corrigida, apagaria os preços que o app usa hoje
        # (valor estimado, fechamento, perdas). Removida de propósito.)

        # Preenche order_number em pedidos antigos
        cur.execute("SELECT id FROM orders WHERE order_number IS NULL OR order_number = '' ORDER BY id")
        rows = cur.fetchall()
        if rows:
            cur.execute("SELECT MAX(order_number) FROM orders")
            maxnum = cur.fetchone()[0] or 0
            for i, row in enumerate(rows, start=1):
                cur.execute("UPDATE orders SET order_number=? WHERE id=?", (maxnum + i, row[0]))
            self.conn.commit()

        # Movimentações de estoque
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('entrada','saida')),
                quantity INTEGER NOT NULL,
                reason TEXT,
                order_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )
        """)

        # Migração: adiciona 'category' (subtipo: Compra/Produção/Perda/Venda/Ajuste/...)
        # e 'created_by' (quem registrou) para a tela de Movimentação - antes o único
        # jeito de categorizar era o texto livre em 'reason', sem padronização.
        cur.execute("PRAGMA table_info(stock_movements)")
        columns = [row[1] for row in cur.fetchall()]
        if "category" not in columns:
            cur.execute("ALTER TABLE stock_movements ADD COLUMN category TEXT")
            self.conn.commit()
            print("✓ Campo 'category' adicionado em stock_movements.")
        cur.execute("PRAGMA table_info(stock_movements)")
        columns = [row[1] for row in cur.fetchall()]
        if "created_by" not in columns:
            cur.execute("ALTER TABLE stock_movements ADD COLUMN created_by TEXT")
            self.conn.commit()
            print("✓ Campo 'created_by' adicionado em stock_movements.")

        # Etiquetas personalizadas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Tabela de itens da lista de produção (adicionados manualmente)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS production_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                size TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)
        
        # Tabela de configuração da empresa
        cur.execute("""
            CREATE TABLE IF NOT EXISTS company (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL DEFAULT 'Minha Empresa',
                logo_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Migração: dias da semana sem expediente (pedidos não podem ser entregues neles).
        # Números do Python (0 = segunda … 6 = domingo), separados por vírgula. Padrão "0":
        # segunda, a regra que era fixa no código; cada confeitaria ajusta em Configurações.
        cur.execute("PRAGMA table_info(company)")
        if "closed_weekdays" not in [row[1] for row in cur.fetchall()]:
            cur.execute("ALTER TABLE company ADD COLUMN closed_weekdays TEXT DEFAULT '0'")

        # Insere registro padrão se não existir
        existing_company = cur.execute("SELECT 1 FROM company WHERE id=1").fetchone()
        if not existing_company:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("INSERT INTO company(id, name, logo_path, created_at, updated_at) VALUES (1, 'Confeitaria', NULL, ?, ?)", (now, now))
        
        self.conn.commit()
        
        # Adiciona etiquetas padrão se não existirem
        default_labels = [
            ("Comum", "#6B7280"),
            ("Urgente", "#EF4444"),
            ("Especial", "#F59E0B")
        ]
        for label_name, color in default_labels:
            existing = cur.execute("SELECT 1 FROM labels WHERE name=?", (label_name,)).fetchone()
            if not existing:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("INSERT INTO labels(name, color, created_at) VALUES (?,?,?)", (label_name, color, now))
        self.conn.commit()

        self._ensure_indexes(cur)

    def _ensure_indexes(self, cur: Any) -> None:
        """Índices para as consultas mais frequentes (filtros por data/status,
        joins por produto/cliente, histórico de auditoria). Sem eles cada tela
        varre a tabela inteira; com o auto-refresh das telas de estoque isso
        pesa conforme o banco cresce. IF NOT EXISTS: seguro em bancos antigos."""
        indexes = [
            ("idx_orders_delivery_date", "orders(delivery_date)"),
            ("idx_orders_status", "orders(status)"),
            ("idx_orders_created_at", "orders(created_at)"),
            ("idx_orders_customer", "orders(customer_id)"),
            ("idx_orders_product", "orders(product_id)"),
            ("idx_orders_number", "orders(order_number)"),
            ("idx_stock_mov_product", "stock_movements(product_id)"),
            ("idx_stock_mov_created_at", "stock_movements(created_at)"),
            ("idx_stock_mov_order", "stock_movements(order_id)"),
            ("idx_audit_entity", "audit_logs(entity, entity_id)"),
            ("idx_production_items_product", "production_items(product_id)"),
        ]
        for name, target in indexes:
            try:
                cur.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")
            except Exception as e:
                # Coluna ausente num banco muito antigo não deve impedir a abertura
                print(f"Aviso: não foi possível criar índice {name}: {e}")
        self.conn.commit()

    def audit_log(self, entity: str, entity_id: Optional[int], action: str, details: Optional[str] = None, user: Optional[str] = None) -> None:
        """Registra no banco (e em arquivo logs/actions.log) ações importantes do sistema.

        - entity: 'product'|'customer'|'order' etc
        - entity_id: id do registro (pode ser None)
        - action: 'create'|'update'|'delete'
        - details: texto livre com informações adicionais
        - user: usuário executando a ação; se None, usa self.current_user ou 'unknown'
        """
        try:
            u = user or getattr(self, "current_user", None) or "unknown"
            # ISO para armazenar no banco, humano (dd/MM/aaaa HH:mm:ss) para arquivo texto
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            now_human = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.execute(
                "INSERT INTO audit_logs(entity, entity_id, action, user, details, created_at) VALUES (?,?,?,?,?,?)",
                (entity, entity_id, action, str(u), details, now_iso)
            )
            # também grava em arquivo texto (útil fora do DB)
            try:
                logs_dir = os.path.join(base_dir, "logs")
                os.makedirs(logs_dir, exist_ok=True)
                lf = os.path.join(logs_dir, "actions.log")
                with open(lf, "a", encoding="utf-8") as f:
                    f.write(f"{now_human}\t{u}\t{entity}\t{entity_id}\t{action}\t{details or ''}\n")
            except Exception:
                pass
        except Exception:
            # Não propaga erros de logging para não quebrar a operação principal
            pass


def check_and_reserve_stock(db: Any) -> int:
    """
    Verifica pedidos com data de entrega = hoje que ainda não tiveram estoque reservado.
    Baixa o estoque e marca como reservado.
    
    Returns:
        int: Número de pedidos processados
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Busca pedidos com data de entrega hoje OU já vencida (ex: app ficou fechado
        # no dia da entrega) que ainda não tiveram estoque reservado
        rows = db.query("""
            SELECT id, product_id, quantity
            FROM orders
            WHERE DATE(delivery_date) <= ?
            AND stock_reserved = 0
            AND product_id IS NOT NULL
        """, (today,))
        
        if not rows:
            return 0
        
        processed = 0
        for row in rows:
            oid = row["id"]
            try:
                oid = int(row["id"])
                prod_id = int(row["product_id"])
                qty = int(row["quantity"])
                
                # Baixa estoque
                db.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, prod_id))
                
                # Registra movimentação
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                    (prod_id, 'saida', qty, 'Pedido', oid, now)
                )
                
                # Marca como reservado
                db.execute("UPDATE orders SET stock_reserved=1 WHERE id=?", (oid,))
                
                processed += 1
                
            except Exception as e:
                print(f"⚠️ Erro ao reservar estoque do pedido {oid}: {e}")
                continue
        
        print(f"✓ {processed} pedido(s) tiveram estoque reservado automaticamente")
        return processed
        
    except Exception as e:
        print(f"Erro ao verificar reservas de estoque: {e}")
        return 0

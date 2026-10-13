# -*- coding: utf-8 -*-
"""Database com migrações de schema, auditoria e reserva de estoque."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from core.database import Database
from core.paths import base_dir


SQL_SESSOES_WEB = """
    CREATE TABLE IF NOT EXISTS web_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lembrar INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        expires_at REAL NOT NULL,
        last_seen REAL NOT NULL,
        ip TEXT,
        agent TEXT
    )
"""


def encerrar_sessoes_web(db: Any, user_id: int) -> None:
    """Desconecta o usuário do painel web (senha, perfil ou nome trocados; usuário excluído)."""
    try:
        db.execute("DELETE FROM web_sessions WHERE user_id=?", (user_id,))
    except Exception:
        pass


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

        # Migração: unidade de venda do produto. "un" (inteiro) ou "kg" (até 3 casas:
        # gramas). Produtos em kg guardam estoque, pedidos, movimentações e produção em
        # quilos com decimais (as colunas INTEGER do SQLite aceitam 1.5) e o preço é por
        # kg. Depois da migração de requires_min_stock, que recria a tabela.
        cur.execute("PRAGMA table_info(products)")
        if "unit" not in [row[1] for row in cur.fetchall()]:
            cur.execute("ALTER TABLE products ADD COLUMN unit TEXT NOT NULL DEFAULT 'un'")
            self.conn.commit()

        # Preenche order_number em pedidos antigos
        cur.execute("SELECT id FROM orders WHERE order_number IS NULL OR order_number = '' ORDER BY id")
        rows = cur.fetchall()
        if rows:
            cur.execute("SELECT MAX(order_number) FROM orders")
            maxnum = cur.fetchone()[0] or 0
            for i, row in enumerate(rows, start=1):
                cur.execute("UPDATE orders SET order_number=? WHERE id=?", (maxnum + i, row[0]))
            self.conn.commit()

        # Migração: situação do pedido, separada do pagamento (status). "aberto" (a
        # entregar), "entregue" ou "cancelado". Cancelar devolve o estoque reservado;
        # entregue nunca devolve (nem ao excluir). Um pedido pode estar entregue e
        # ainda aguardando pagamento (fiado).
        cur.execute("PRAGMA table_info(orders)")
        if "situacao" not in [row[1] for row in cur.fetchall()]:
            cur.execute("ALTER TABLE orders ADD COLUMN situacao TEXT NOT NULL DEFAULT 'aberto'")
            self.conn.commit()
        # Bancos antigos guardavam a entrega no próprio status ("Entregue", "Cancelado"):
        # passa para a situação. O estoque desses pedidos não é mexido (fica como está).
        cur.execute("""UPDATE orders SET situacao='entregue' WHERE situacao='aberto'
                       AND LOWER(status) IN ('entregue', 'completed', 'concluído', 'concluido')""")
        cur.execute("""UPDATE orders SET situacao='cancelado' WHERE situacao='aberto'
                       AND LOWER(status) IN ('cancelado', 'cancelled')""")
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

        # Etiquetas personalizadas. As padrão só entram quando a tabela é criada: antes
        # eram reinseridas a cada abertura e etiquetas excluídas voltavam sozinhas.
        etiquetas_novas = not cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='labels'").fetchone()
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
            # "Comum" é a etiqueta padrão dos pedidos: garante que exista sempre.
            if not etiquetas_novas and label_name != "Comum":
                continue
            existing = cur.execute("SELECT 1 FROM labels WHERE LOWER(name)=LOWER(?)", (label_name,)).fetchone()
            if not existing:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("INSERT INTO labels(name, color, created_at) VALUES (?,?,?)", (label_name, color, now))
        self.conn.commit()

        self._init_custos(cur)
        self._ensure_indexes(cur)

    def _init_custos(self, cur: Any) -> None:
        """Custos: insumos comprados, histórico de compras e fichas técnicas (receitas).
        Quantidades e valores ficam em TEXT com o número decimal exato digitado
        ("0.395", "4.99"): REAL arredondaria em binário e o custo por grama/ml, que
        depois é multiplicado por milhares de gramas, sairia levemente errado. As contas
        são feitas com Decimal em core/custos.py."""
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'ingrediente',
                base_unit TEXT NOT NULL CHECK (base_unit IN ('g','ml','un')),
                yield_pct TEXT NOT NULL DEFAULT '100',
                density TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingredient_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
                purchased_at TEXT NOT NULL,
                supplier TEXT,
                packages TEXT NOT NULL,
                package_qty TEXT NOT NULL,
                package_unit TEXT NOT NULL,
                total TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                yield_qty TEXT NOT NULL,
                yield_unit TEXT NOT NULL,
                labor_minutes TEXT NOT NULL DEFAULT '0',
                loss_pct TEXT NOT NULL DEFAULT '0',
                extra_cost TEXT NOT NULL DEFAULT '0',
                margin_pct TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recipe_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                ingredient_id INTEGER REFERENCES ingredients(id),
                sub_recipe_id INTEGER REFERENCES recipes(id),
                quantity TEXT NOT NULL,
                unit TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                CHECK ((ingredient_id IS NULL) <> (sub_recipe_id IS NULL))
            )
        """)
        # Sessões do painel web (login com usuário e senha; o cookie guarda só um código
        # aleatório e aqui fica o hash dele). Ver core/web_server.py.
        cur.execute(SQL_SESSOES_WEB)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cost_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cost_basis TEXT NOT NULL DEFAULT 'ultima',
                avg_days INTEGER NOT NULL DEFAULT 90,
                labor_hour TEXT NOT NULL DEFAULT '0',
                fixed_pct TEXT NOT NULL DEFAULT '0',
                tax_pct TEXT NOT NULL DEFAULT '0',
                fee_pct TEXT NOT NULL DEFAULT '0',
                margin_pct TEXT NOT NULL DEFAULT '30',
                rounding TEXT NOT NULL DEFAULT '0.01',
                updated_at TEXT NOT NULL
            )
        """)
        if not cur.execute("SELECT 1 FROM cost_settings WHERE id=1").fetchone():
            cur.execute("INSERT INTO cost_settings(id, updated_at) VALUES (1, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
        self.conn.commit()

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
            ("idx_ing_purchases_ing", "ingredient_purchases(ingredient_id, purchased_at)"),
            ("idx_recipe_items_recipe", "recipe_items(recipe_id)"),
            ("idx_recipe_items_ing", "recipe_items(ingredient_id)"),
            ("idx_recipe_items_sub", "recipe_items(sub_recipe_id)"),
            ("idx_recipes_product", "recipes(product_id)"),
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
    """Baixa o estoque dos pedidos com entrega hoje ou já vencida (o app pode ter
    ficado fechado no dia) que ainda não foram reservados. Pedidos cancelados ficam
    de fora.

    Cada pedido é tudo-ou-nada (marca + baixa + movimentação numa transação) e a
    marca é tomada primeiro com "stock_reserved=0" na condição: uma falha no meio
    não deixa estoque baixado sem a marca (antes a próxima rodada baixava de novo).
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = db.query("""
            SELECT id, product_id, quantity
            FROM orders
            WHERE DATE(delivery_date) <= ?
            AND stock_reserved = 0
            AND COALESCE(situacao, 'aberto') != 'cancelado'
            AND product_id IS NOT NULL
        """, (today,))
        processed = 0
        for row in rows:
            oid = int(row["id"])
            try:
                with db.transaction():
                    cur = db.execute("UPDATE orders SET stock_reserved=1 WHERE id=? AND stock_reserved=0", (oid,))
                    if cur.rowcount != 1:
                        continue  # outro caminho já reservou
                    qty = int(row["quantity"])
                    prod_id = int(row["product_id"])
                    db.execute("UPDATE products SET stock = ROUND(stock - ?, 3) WHERE id=?", (qty, prod_id))
                    db.execute(
                        "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
                        (prod_id, 'saida', qty, 'Pedido', oid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'sistema'),
                    )
                processed += 1
            except Exception as e:
                print(f"⚠️ Erro ao reservar estoque do pedido {oid}: {e}")
        if processed:
            print(f"✓ {processed} pedido(s) tiveram estoque reservado automaticamente")
        return processed
    except Exception as e:
        print(f"Erro ao verificar reservas de estoque: {e}")
        return 0

# -*- coding: utf-8 -*-
"""
Script para popular o banco de dados com dados de exemplo
- 40 clientes
- 40 produtos com preços
- 100 pedidos nos últimos 12 meses
"""

import sqlite3
import os
import sys
import random
from datetime import datetime, timedelta

# Adiciona o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Dados de exemplo
CLIENTES = [
    ("Ana Silva", "(11) 98765-4321", "Rua das Flores, 123", "1985-03-15"),
    ("Bruno Costa", "(11) 97654-3210", "Av. Paulista, 456", "1990-07-22"),
    ("Carla Santos", "(11) 96543-2109", "Rua Augusta, 789", "1988-11-30"),
    ("Daniel Oliveira", "(21) 95432-1098", "Rua do Catete, 321", "1992-05-18"),
    ("Elena Ferreira", "(21) 94321-0987", "Av. Atlântica, 654", "1987-09-25"),
    ("Felipe Souza", "(11) 93210-9876", "Rua Oscar Freire, 987", "1995-01-12"),
    ("Gabriela Lima", "(11) 92109-8765", "Av. Faria Lima, 234", "1991-06-08"),
    ("Henrique Alves", "(21) 91098-7654", "Rua Visconde, 567", "1989-12-03"),
    ("Isabela Martins", "(11) 90987-6543", "Rua Haddock Lobo, 890", "1993-04-27"),
    ("João Pedro", "(21) 89876-5432", "Av. Rio Branco, 123", "1986-08-14"),
    ("Karina Rocha", "(11) 88765-4321", "Rua Consolação, 456", "1994-02-19"),
    ("Lucas Mendes", "(11) 87654-3210", "Av. Rebouças, 789", "1990-10-31"),
    ("Maria Eduarda", "(21) 86543-2109", "Rua Barata Ribeiro, 321", "1988-07-05"),
    ("Nicolas Dias", "(11) 85432-1098", "Rua Pamplona, 654", "1992-03-22"),
    ("Olivia Castro", "(21) 84321-0987", "Av. Nossa Senhora, 987", "1987-11-16"),
    ("Paulo Henrique", "(11) 83210-9876", "Rua Teodoro Sampaio, 234", "1996-05-09"),
    ("Quezia Barbosa", "(11) 82109-8765", "Av. Brigadeiro, 567", "1991-09-28"),
    ("Rafael Gomes", "(21) 81098-7654", "Rua Senador Vergueiro, 890", "1989-01-13"),
    ("Sofia Cardoso", "(11) 80987-6543", "Rua da Consolação, 123", "1993-06-20"),
    ("Thiago Nunes", "(21) 79876-5432", "Av. Presidente Vargas, 456", "1985-12-07"),
    ("Ursula Pinto", "(11) 78765-4321", "Rua Bela Cintra, 789", "1994-04-15"),
    ("Vitor Ribeiro", "(11) 77654-3210", "Av. Nove de Julho, 321", "1990-08-23"),
    ("Wanda Freitas", "(21) 76543-2109", "Rua Santa Clara, 654", "1988-02-11"),
    ("Xavier Moura", "(11) 75432-1098", "Rua Augusta, 987", "1992-10-18"),
    ("Yasmin Teixeira", "(21) 74321-0987", "Av. Atlântica, 234", "1987-06-26"),
    ("Zeca Araujo", "(11) 73210-9876", "Rua Estados Unidos, 567", "1995-02-03"),
    ("Amanda Reis", "(11) 72109-8765", "Av. Paulista, 890", "1991-08-12"),
    ("Bernardo Lopes", "(21) 71098-7654", "Rua Bambina, 123", "1989-04-29"),
    ("Camila Monteiro", "(11) 70987-6543", "Rua Lorena, 456", "1993-12-06"),
    ("Diego Campos", "(21) 69876-5432", "Av. Copacabana, 789", "1986-06-14"),
    ("Eliane Correia", "(11) 68765-4321", "Rua Alameda Santos, 321", "1994-10-21"),
    ("Fabio Azevedo", "(11) 67654-3210", "Av. Ibirapuera, 654", "1990-02-28"),
    ("Giovana Duarte", "(21) 66543-2109", "Rua Prudente de Morais, 987", "1988-09-05"),
    ("Hugo Pacheco", "(11) 65432-1098", "Rua Oscar Freire, 234", "1992-01-12"),
    ("Iris Fonseca", "(21) 64321-0987", "Av. Vieira Souto, 567", "1987-07-19"),
    ("Jorge Batista", "(11) 63210-9876", "Rua Frei Caneca, 890", "1996-03-27"),
    ("Kelly Miranda", "(11) 62109-8765", "Av. Europa, 123", "1991-11-04"),
    ("Leonardo Xavier", "(21) 61098-7654", "Rua Visconde de Pirajá, 456", "1989-05-11"),
    ("Mariana Viana", "(11) 60987-6543", "Rua Bela Vista, 789", "1993-01-18"),
    ("Nuno Carvalho", "(21) 59876-5432", "Av. das Américas, 321", "1985-09-25"),
]

PRODUTOS = [
    ("Bolo de Chocolate", "Bolo com cobertura de chocolate", "Grande (3kg)", 89.90, 15, 5),
    ("Bolo de Morango", "Bolo com morangos frescos", "Grande (3kg)", 95.00, 12, 5),
    ("Bolo Red Velvet", "Bolo vermelho com cream cheese", "Grande (3kg)", 99.90, 10, 3),
    ("Bolo de Cenoura", "Bolo tradicional com cobertura", "Grande (3kg)", 79.90, 18, 5),
    ("Bolo de Limão", "Bolo com recheio de limão", "Grande (3kg)", 85.00, 14, 5),
    ("Bolo de Coco", "Bolo com coco ralado", "Grande (3kg)", 82.50, 16, 5),
    ("Torta de Limão", "Torta com merengue", "Média (1.5kg)", 65.00, 8, 3),
    ("Torta de Maracujá", "Torta com creme de maracujá", "Média (1.5kg)", 68.00, 7, 3),
    ("Torta de Morango", "Torta com morangos frescos", "Média (1.5kg)", 72.00, 6, 2),
    ("Torta Holandesa", "Torta com chocolate belga", "Média (1.5kg)", 75.00, 9, 3),
    ("Brownie", "Brownie de chocolate", "Pequeno (500g)", 35.00, 25, 10),
    ("Cupcake Chocolate", "Cupcake com cobertura", "Unidade", 8.50, 40, 20),
    ("Cupcake Baunilha", "Cupcake de baunilha", "Unidade", 8.00, 45, 20),
    ("Cupcake Red Velvet", "Cupcake vermelho", "Unidade", 9.50, 35, 15),
    ("Brigadeiro Gourmet", "Brigadeiro premium", "Caixa 12 un", 45.00, 30, 15),
    ("Beijinho Gourmet", "Beijinho premium", "Caixa 12 un", 45.00, 28, 15),
    ("Cajuzinho", "Doce de amendoim", "Caixa 12 un", 42.00, 32, 15),
    ("Trufa de Chocolate", "Trufa artesanal", "Caixa 12 un", 55.00, 20, 10),
    ("Cookies", "Cookies de chocolate", "Pacote 6 un", 25.00, 50, 20),
    ("Macaron", "Macaron francês", "Caixa 6 un", 38.00, 15, 8),
    ("Cheesecake", "Cheesecake tradicional", "Grande (2kg)", 95.00, 8, 3),
    ("Pavlova", "Pavlova com frutas", "Grande (2kg)", 88.00, 7, 3),
    ("Profiteroles", "Profiteroles recheados", "Caixa 12 un", 52.00, 12, 5),
    ("Éclair", "Éclair de chocolate", "Unidade", 12.00, 18, 10),
    ("Sonho", "Sonho recheado", "Unidade", 7.50, 30, 15),
    ("Croissant", "Croissant artesanal", "Unidade", 9.00, 25, 12),
    ("Pão de Mel", "Pão de mel com chocolate", "Unidade", 6.50, 40, 20),
    ("Bolo no Pote Chocolate", "Bolo em camadas no pote", "Unidade", 15.00, 35, 15),
    ("Bolo no Pote Morango", "Bolo com morango no pote", "Unidade", 16.00, 32, 15),
    ("Bolo no Pote Ninho", "Bolo de leite ninho no pote", "Unidade", 17.00, 30, 15),
    ("Alfajor", "Alfajor argentino", "Unidade", 8.00, 28, 12),
    ("Mil-folhas", "Mil-folhas tradicional", "Fatia", 14.00, 20, 10),
    ("Quindim", "Quindim caseiro", "Unidade", 5.50, 45, 20),
    ("Pudim", "Pudim de leite condensado", "Médio (1kg)", 42.00, 12, 5),
    ("Mousse de Chocolate", "Mousse aerado", "Pote 500g", 32.00, 18, 8),
    ("Mousse de Maracujá", "Mousse tropical", "Pote 500g", 30.00, 16, 8),
    ("Palha Italiana", "Palha italiana gourmet", "Pote 300g", 28.00, 22, 10),
    ("Bolo de Nozes", "Bolo com nozes e mel", "Grande (3kg)", 92.00, 11, 5),
    ("Bolo de Banana", "Bolo de banana com canela", "Grande (3kg)", 78.00, 17, 5),
    ("Bolo de Fubá", "Bolo de fubá cremoso", "Grande (3kg)", 68.00, 19, 5),
]

def criar_banco_exemplo():
    """Cria e popula o banco de dados com dados de exemplo"""
    
    # Caminho do banco
    db_path = os.path.join(os.path.dirname(__file__), "confeitaria.db")
    
    print(f"🗄️  Conectando ao banco: {db_path}")
    
    # Conecta ao banco
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Criar tabelas se não existirem
    print("\n📋 Verificando estrutura do banco...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            birthday TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            size TEXT,
            price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            min_stock INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            delivery_date TEXT,
            total REAL DEFAULT 0,
            status TEXT DEFAULT 'Pendente',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    conn.commit()
    print("✅ Estrutura do banco verificada!")
    
    # Verifica se já existem dados
    cursor.execute("SELECT COUNT(*) FROM customers")
    clientes_existentes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products")
    produtos_existentes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    pedidos_existentes = cursor.fetchone()[0]
    
    print(f"\n📊 Estado atual do banco:")
    print(f"   Clientes: {clientes_existentes}")
    print(f"   Produtos: {produtos_existentes}")
    print(f"   Pedidos: {pedidos_existentes}")
    
    resposta = input("\n⚠️  Deseja LIMPAR os dados existentes e criar novos? (S/N): ").strip().upper()
    
    if resposta == 'S':
        print("\n🗑️  Limpando dados existentes...")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM customers")
        conn.commit()
        print("✅ Dados limpos!")
    else:
        print("\n📝 Adicionando dados aos existentes...")
    
    # Inserir clientes
    print(f"\n👥 Inserindo {len(CLIENTES)} clientes...")
    for cliente in CLIENTES:
        try:
            cursor.execute(
                "INSERT INTO customers (name, phone, address, birthday) VALUES (?, ?, ?, ?)",
                cliente
            )
        except sqlite3.IntegrityError:
            pass  # Cliente já existe
    conn.commit()
    print(f"✅ {len(CLIENTES)} clientes inseridos!")
    
    # Inserir produtos
    print(f"\n🍰 Inserindo {len(PRODUTOS)} produtos...")
    produtos_ids = []
    for produto in PRODUTOS:
        try:
            cursor.execute(
                "INSERT INTO products (name, description, size, price, stock, min_stock) VALUES (?, ?, ?, ?, ?, ?)",
                produto
            )
            produtos_ids.append(cursor.lastrowid)
        except sqlite3.IntegrityError:
            pass  # Produto já existe
    conn.commit()
    print(f"✅ {len(PRODUTOS)} produtos inseridos!")
    
    # Buscar IDs de clientes e produtos
    cursor.execute("SELECT id FROM customers")
    clientes_ids = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT id, price FROM products")
    produtos_info = [(row[0], row[1]) for row in cursor.fetchall()]
    
    if not clientes_ids or not produtos_info:
        print("❌ Erro: Não há clientes ou produtos no banco!")
        conn.close()
        return
    
    # Criar 100 pedidos nos últimos 12 meses
    print(f"\n📦 Criando 100 pedidos nos últimos 12 meses...")
    
    hoje = datetime.now()
    status_opcoes = ["Pendente", "Produção", "Pronto", "Entregue", "Cancelado"]
    status_pesos = [10, 15, 20, 50, 5]  # Mais pedidos entregues
    
    pedidos_criados = 0
    for i in range(100):
        # Data aleatória nos últimos 12 meses
        dias_atras = random.randint(0, 365)
        data_pedido = hoje - timedelta(days=dias_atras)
        data_entrega = data_pedido + timedelta(days=random.randint(1, 7))
        
        # Cliente aleatório
        customer_id = random.choice(clientes_ids)
        
        # Produto aleatório
        product_id, preco = random.choice(produtos_info)
        
        # Quantidade aleatória
        quantidade = random.randint(1, 5)
        
        # Total
        total = preco * quantidade
        
        # Status (mais pedidos entregues para pedidos antigos)
        if dias_atras > 30:
            status = random.choices(["Entregue", "Cancelado"], weights=[95, 5])[0]
        else:
            status = random.choices(status_opcoes, weights=status_pesos)[0]
        
        # Observações aleatórias (50% dos pedidos)
        observacoes = None
        if random.random() > 0.5:
            obs_opcoes = [
                "Sem glúten, por favor",
                "Escrever 'Parabéns' no bolo",
                "Entregar após 18h",
                "Cliente VIP",
                "Urgente para amanhã",
                "Embalagem especial",
                None
            ]
            observacoes = random.choice(obs_opcoes)
        
        try:
            cursor.execute(
                """INSERT INTO orders 
                   (customer_id, product_id, quantity, delivery_date, total, status, notes, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    customer_id,
                    product_id,
                    quantidade,
                    data_entrega.strftime("%Y-%m-%d"),
                    total,
                    status,
                    observacoes,
                    data_pedido.strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            pedidos_criados += 1
        except Exception as e:
            print(f"⚠️  Erro ao criar pedido {i+1}: {e}")
    
    conn.commit()
    print(f"✅ {pedidos_criados} pedidos criados!")
    
    # Estatísticas finais
    print("\n" + "="*50)
    print("📊 RESUMO FINAL")
    print("="*50)
    
    cursor.execute("SELECT COUNT(*) FROM customers")
    total_clientes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products")
    total_produtos = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_pedidos = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(total) FROM orders WHERE status='Entregue'")
    total_vendas = cursor.fetchone()[0] or 0
    
    print(f"👥 Total de Clientes: {total_clientes}")
    print(f"🍰 Total de Produtos: {total_produtos}")
    print(f"📦 Total de Pedidos: {total_pedidos}")
    print(f"💰 Total de Vendas (Entregues): R$ {total_vendas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    # Status dos pedidos
    print("\n📈 Pedidos por Status:")
    cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY COUNT(*) DESC")
    for status, count in cursor.fetchall():
        print(f"   {status}: {count}")
    
    # Top 5 produtos mais vendidos
    print("\n🏆 Top 5 Produtos Mais Vendidos:")
    cursor.execute("""
        SELECT p.name, COUNT(o.id) as vendas, SUM(o.total) as receita
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.status = 'Entregue'
        GROUP BY p.id
        ORDER BY vendas DESC
        LIMIT 5
    """)
    for i, (nome, vendas, receita) in enumerate(cursor.fetchall(), 1):
        print(f"   {i}. {nome}: {vendas} vendas (R$ {receita:,.2f})".replace(",", "X").replace(".", ",").replace("X", "."))
    
    conn.close()
    
    print("\n" + "="*50)
    print("✅ Banco de dados populado com sucesso!")
    print("="*50)
    print("\n💡 Agora você pode abrir o sistema e ver todos os dados!")

if __name__ == "__main__":
    try:
        criar_banco_exemplo()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n\nPressione ENTER para sair...")

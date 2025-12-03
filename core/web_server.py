"""
Servidor Web Flask para Painel da Cozinha
==========================================
Permite acesso via rede local para atualização de estoque de produtos
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import logging
from pathlib import Path
import socket

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebServer:
    """Servidor web Flask para o painel da cozinha"""
    
    def __init__(self, db_path: str, web_dir: str, port: int = 5000):
        """
        Inicializa o servidor web
        
        Args:
            db_path: Caminho para o banco de dados SQLite
            web_dir: Diretório contendo os arquivos web (HTML, CSS, JS)
            port: Porta para o servidor (padrão: 5000)
        """
        self.db_path = db_path
        self.web_dir = web_dir
        self.port = port
        self.app = Flask(__name__)
        CORS(self.app)  # Permite requisições de qualquer origem
        
        # Configurar rotas
        self._setup_routes()
        
    def _setup_routes(self):
        """Configura as rotas da API"""
        
        # Página de seleção de acesso
        @self.app.route('/')
        def root():
            """Redireciona para página de acesso"""
            # Detectar se é localhost ou rede
            host = request.host.split(':')[0]
            if host in ['localhost', '127.0.0.1', '::1']:
                # Acesso local - vai direto para o painel
                return send_from_directory(self.web_dir, 'index.html')
            else:
                # Acesso de outro dispositivo - mostra página de acesso
                return send_from_directory(self.web_dir, 'acesso.html')
        
        @self.app.route('/index.html')
        def index():
            """Página principal do painel"""
            return send_from_directory(self.web_dir, 'index.html')
        
        @self.app.route('/acesso.html')
        def acesso():
            """Página de seleção de acesso"""
            return send_from_directory(self.web_dir, 'acesso.html')
        
        @self.app.route('/logo.ico')
        def favicon():
            """Servir favicon"""
            return send_from_directory(self.web_dir, 'logo.ico')
        
        @self.app.route('/assets/icons/<path:filename>')
        def serve_icons(filename):
            """Servir ícones"""
            icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icons')
            return send_from_directory(icons_dir, filename)
        
        @self.app.route('/<path:filename>')
        def serve_static(filename):
            """Servir arquivos estáticos"""
            return send_from_directory(self.web_dir, filename)
        
        # API: Listar todos os produtos (estoque geral)
        @self.app.route('/api/products', methods=['GET'])
        def get_products():
            """Retorna lista de todos os produtos"""
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, name, description, size, stock, min_stock
                    FROM products
                    ORDER BY name
                """)
                
                products = []
                for row in cursor.fetchall():
                    products.append({
                        'id': row['id'],
                        'name': row['name'],
                        'quantity': row['stock'],
                        'min_quantity': row['min_stock'],
                        'description': row['description'] or '',
                        'size': row['size'] or ''
                    })
                
                conn.close()
                
                return jsonify({
                    'success': True,
                    'products': products
                })
                
            except Exception as e:
                logger.error(f"Erro ao buscar produtos: {e}")
                print(f"❌ Erro na API /api/products: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Listar produtos com estoque disponível (Pronta Entrega)
        @self.app.route('/api/ready-stock', methods=['GET'])
        def get_ready_stock():
            """Retorna lista de produtos em pronta entrega (stock > 0)"""
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, name, description, size, stock, min_stock
                    FROM products
                    WHERE stock > 0
                    ORDER BY name
                """)
                
                products = []
                for row in cursor.fetchall():
                    products.append({
                        'id': row['id'],
                        'name': row['name'],
                        'description': row['description'] or '',
                        'size': row['size'] or '',
                        'stock': row['stock'],
                        'min_quantity': row['min_stock']
                    })
                
                conn.close()
                
                return jsonify({
                    'success': True,
                    'products': products
                })
                
            except Exception as e:
                logger.error(f"Erro ao buscar pronta entrega: {e}")
                print(f"❌ Erro na API /api/ready-stock: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Listar pedidos de produção
        @self.app.route('/api/production', methods=['GET'])
        def get_production():
            """Retorna lista de produção (production_items + orders pendentes)"""
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 1. Busca itens adicionados manualmente na lista de produção
                cursor.execute("""
                    SELECT 
                        pi.id,
                        'manual' as source,
                        NULL as customer_name,
                        p.name as product_name,
                        pi.size as product_size,
                        pi.quantity,
                        NULL as delivery_date,
                        'pending' as status,
                        pi.notes
                    FROM production_items pi
                    JOIN products p ON pi.product_id = p.id
                    ORDER BY pi.created_at DESC
                """)
                
                manual_items = cursor.fetchall()
                
                # 2. Busca pedidos pendentes/em produção (dos próximos 7 dias)
                from datetime import datetime, timedelta
                today = datetime.now().strftime("%Y-%m-%d")
                week_later = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                
                cursor.execute("""
                    SELECT 
                        o.id,
                        'order' as source,
                        c.name as customer_name,
                        p.name as product_name,
                        p.size as product_size,
                        o.quantity,
                        o.delivery_date,
                        o.status,
                        o.notes
                    FROM orders o
                    LEFT JOIN customers c ON o.customer_id = c.id
                    LEFT JOIN products p ON o.product_id = p.id
                    WHERE o.status IN ('pending', 'in_production', 'Pendente', 'Em produção')
                    AND DATE(o.delivery_date) BETWEEN ? AND ?
                    ORDER BY o.delivery_date, c.name
                """, (today, week_later))
                
                order_items = cursor.fetchall()
                
                # Combina ambos em uma lista
                orders = []
                
                # Adiciona itens manuais
                for row in manual_items:
                    orders.append({
                        'id': f"manual_{row['id']}",  # Prefixo para diferenciar
                        'source': 'manual',
                        'customer': 'Lista Manual',
                        'product': row['product_name'] or 'Produto não especificado',
                        'size': row['product_size'] or '',
                        'quantity': row['quantity'],
                        'delivery_date': '',
                        'status': 'pending',
                        'notes': row['notes'] or ''
                    })
                
                # Adiciona pedidos
                for row in order_items:
                    orders.append({
                        'id': f"order_{row['id']}",  # Prefixo para diferenciar
                        'source': 'order',
                        'customer': row['customer_name'] or 'Cliente não especificado',
                        'product': row['product_name'] or 'Produto não especificado',
                        'size': row['product_size'] or '',
                        'quantity': row['quantity'],
                        'delivery_date': row['delivery_date'],
                        'status': row['status'],
                        'notes': row['notes'] or ''
                    })
                
                conn.close()
                
                return jsonify({
                    'success': True,
                    'orders': orders
                })
                
            except Exception as e:
                logger.error(f"Erro ao buscar produção: {e}")
                print(f"❌ Erro na API /api/production: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Atualizar estoque de um produto (Pronta Entrega)
        @self.app.route('/api/products/<int:product_id>', methods=['PUT'])
        def update_product(product_id):
            """Atualiza a quantidade em estoque de um produto"""
            try:
                data = request.get_json()
                
                if 'quantity' not in data:
                    return jsonify({
                        'success': False,
                        'error': 'Campo "quantity" é obrigatório'
                    }), 400
                
                quantity = int(data['quantity'])
                
                if quantity < 0:
                    return jsonify({
                        'success': False,
                        'error': 'Quantidade não pode ser negativa'
                    }), 400
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Verificar se o produto existe
                cursor.execute("SELECT id, name FROM products WHERE id = ?", (product_id,))
                product = cursor.fetchone()
                
                if not product:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Produto não encontrado'
                    }), 404
                
                # Atualizar quantidade
                cursor.execute("""
                    UPDATE products 
                    SET stock = ?
                    WHERE id = ?
                """, (quantity, product_id))
                
                conn.commit()
                conn.close()
                
                print(f"✅ Estoque atualizado: {product[1]} → {quantity} unidades")
                
                return jsonify({
                    'success': True,
                    'message': 'Estoque atualizado com sucesso',
                    'product_id': product_id,
                    'new_quantity': quantity
                })
                
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Quantidade deve ser um número inteiro'
                }), 400
            except Exception as e:
                logger.error(f"Erro ao atualizar produto: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Atualizar item de produção (manual ou pedido)
        @self.app.route('/api/production/<string:item_id>', methods=['PUT'])
        def update_production_item(item_id):
            """Atualiza a quantidade, tamanho e/ou observações de um item de produção (manual ou pedido)"""
            try:
                data = request.get_json()
                
                if 'quantity' not in data and 'size' not in data and 'notes' not in data:
                    return jsonify({
                        'success': False,
                        'error': 'Pelo menos um campo ("quantity", "size" ou "notes") é obrigatório'
                    }), 400
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Verificar se é item manual ou pedido
                if item_id.startswith('manual_'):
                    # Item da lista manual
                    real_id = int(item_id.replace('manual_', ''))
                    cursor.execute("SELECT id, product_id, quantity FROM production_items WHERE id = ?", (real_id,))
                    item = cursor.fetchone()
                    
                    if not item:
                        conn.close()
                        return jsonify({
                            'success': False,
                            'error': 'Item não encontrado'
                        }), 404
                    
                    old_quantity = item[2]
                    product_id = item[1]
                    
                    # Preparar campos para atualizar
                    updates = []
                    params = []
                    new_quantity = old_quantity
                    
                    if 'quantity' in data:
                        new_quantity = int(data['quantity'])
                        if new_quantity <= 0:
                            conn.close()
                            return jsonify({
                                'success': False,
                                'error': 'Quantidade deve ser maior que zero'
                            }), 400
                        updates.append("quantity = ?")
                        params.append(new_quantity)
                        
                        # Atualiza o estoque do produto com a diferença
                        quantity_change = new_quantity - old_quantity
                        if quantity_change != 0:
                            cursor.execute(
                                "UPDATE products SET stock = stock + ? WHERE id = ?",
                                (quantity_change, product_id)
                            )
                            print(f"📦 Estoque atualizado: produto #{product_id} {quantity_change:+d} → nova qtd produzida: {new_quantity}")
                    
                    if 'size' in data:
                        size = str(data['size']).strip()
                        updates.append("size = ?")
                        params.append(size)
                    
                    if 'notes' in data:
                        notes = str(data['notes']).strip()
                        updates.append("notes = ?")
                        params.append(notes)
                    
                    if updates:
                        params.append(real_id)
                        sql = f"UPDATE production_items SET {', '.join(updates)} WHERE id = ?"
                        cursor.execute(sql, params)
                    
                    conn.commit()
                    conn.close()
                    
                    print(f"✅ Item manual #{real_id} atualizado")
                    
                elif item_id.startswith('order_'):
                    # Pedido da tabela orders
                    real_id = int(item_id.replace('order_', ''))
                    cursor.execute("SELECT id FROM orders WHERE id = ?", (real_id,))
                    order = cursor.fetchone()
                    
                    if not order:
                        conn.close()
                        return jsonify({
                            'success': False,
                            'error': 'Pedido não encontrado'
                        }), 404
                    
                    # Atualizar campos
                    updates = []
                    params = []
                    
                    if 'quantity' in data:
                        quantity = int(data['quantity'])
                        if quantity <= 0:
                            conn.close()
                            return jsonify({
                                'success': False,
                                'error': 'Quantidade deve ser maior que zero'
                            }), 400
                        updates.append("quantity = ?")
                        params.append(quantity)
                    
                    if 'size' in data:
                        size = str(data['size']).strip()
                        updates.append("size = ?")
                        params.append(size)
                    
                    if 'notes' in data:
                        notes = str(data['notes']).strip()
                        updates.append("notes = ?")
                        params.append(notes)
                    
                    if 'status' in data:
                        valid_statuses = ['pending', 'in_production', 'completed', 'cancelled', 'Pendente', 'Em produção', 'Concluído', 'Cancelado']
                        if data['status'] in valid_statuses:
                            updates.append("status = ?")
                            params.append(data['status'])
                    
                    params.append(real_id)
                    sql = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
                    
                    cursor.execute(sql, params)
                    conn.commit()
                    conn.close()
                    
                    print(f"✅ Pedido #{real_id} atualizado")
                else:
                    return jsonify({
                        'success': False,
                        'error': 'ID de item inválido'
                    }), 400
                
                return jsonify({
                    'success': True,
                    'message': 'Item atualizado com sucesso',
                    'item_id': item_id
                })
                
            except ValueError as ve:
                return jsonify({
                    'success': False,
                    'error': f'Erro de validação: {str(ve)}'
                }), 400
            except Exception as e:
                logger.error(f"Erro ao atualizar item de produção: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Adicionar item à lista de produção
        @self.app.route('/api/production', methods=['POST'])
        def add_production_item():
            """Adiciona um item manualmente à lista de produção"""
            try:
                data = request.get_json()
                
                if 'product_id' not in data or 'quantity' not in data:
                    return jsonify({
                        'success': False,
                        'error': 'Campos "product_id" e "quantity" são obrigatórios'
                    }), 400
                
                product_id = int(data['product_id'])
                quantity = int(data['quantity'])
                size = data.get('size', '')
                notes = data.get('notes', 'Adicionado via web')
                
                if quantity <= 0:
                    return jsonify({
                        'success': False,
                        'error': 'Quantidade deve ser maior que zero'
                    }), 400
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Verificar se o produto existe
                cursor.execute("SELECT id, name FROM products WHERE id = ?", (product_id,))
                product = cursor.fetchone()
                
                if not product:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Produto não encontrado'
                    }), 404
                
                # Inserir na tabela production_items
                from datetime import datetime
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute("""
                    INSERT INTO production_items (product_id, quantity, size, notes, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (product_id, quantity, size, notes, now))
                
                new_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                print(f"✅ Item adicionado à produção via web: {product[1]} ({quantity} un)")
                
                return jsonify({
                    'success': True,
                    'message': 'Item adicionado com sucesso',
                    'item_id': f"manual_{new_id}"
                })
                
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Valores inválidos fornecidos'
                }), 400
            except Exception as e:
                logger.error(f"Erro ao adicionar item de produção: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Excluir item da lista de produção
        @self.app.route('/api/production/<string:item_id>', methods=['DELETE'])
        def delete_production_item(item_id):
            """Remove um item da lista de produção"""
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Verificar se é item manual (apenas itens manuais podem ser excluídos)
                if item_id.startswith('manual_'):
                    real_id = int(item_id.replace('manual_', ''))
                    
                    # Buscar informações antes de deletar
                    cursor.execute("""
                        SELECT p.name, pi.quantity
                        FROM production_items pi
                        JOIN products p ON pi.product_id = p.id
                        WHERE pi.id = ?
                    """, (real_id,))
                    item = cursor.fetchone()
                    
                    if not item:
                        conn.close()
                        return jsonify({
                            'success': False,
                            'error': 'Item não encontrado'
                        }), 404
                    
                    # Deletar
                    cursor.execute("DELETE FROM production_items WHERE id = ?", (real_id,))
                    conn.commit()
                    conn.close()
                    
                    print(f"✅ Item removido da produção via web: {item[0]} ({item[1]} un)")
                    
                    return jsonify({
                        'success': True,
                        'message': 'Item removido com sucesso'
                    })
                else:
                    # Pedidos não podem ser excluídos pelo web, apenas pelo desktop
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Apenas itens adicionados manualmente podem ser excluídos. Pedidos devem ser gerenciados no sistema desktop.'
                    }), 403
                
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'ID inválido'
                }), 400
            except Exception as e:
                logger.error(f"Erro ao excluir item de produção: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Listar produtos disponíveis (para adicionar à produção)
        @self.app.route('/api/products-list', methods=['GET'])
        def get_products_list():
            """Retorna lista simplificada de produtos para seleção"""
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, name, size
                    FROM products
                    ORDER BY name
                """)
                
                products = []
                for row in cursor.fetchall():
                    products.append({
                        'id': row['id'],
                        'name': row['name'],
                        'size': row['size'] or ''
                    })
                
                conn.close()
                
                return jsonify({
                    'success': True,
                    'products': products
                })
                
            except Exception as e:
                logger.error(f"Erro ao buscar lista de produtos: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # API: Completar produção e adicionar ao estoque
        @self.app.route('/api/production/complete', methods=['POST'])
        def complete_production():
            """
            Marca produção como concluída:
            - Pega todos os itens de production_items
            - Adiciona as quantidades ao estoque dos produtos
            - Registra movimentos no stock_movements
            - Limpa a tabela production_items
            """
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 1. Buscar todos os itens da produção
                cursor.execute("""
                    SELECT pi.id, pi.product_id, pi.quantity, pi.size, p.name
                    FROM production_items pi
                    JOIN products p ON pi.product_id = p.id
                """)
                
                items = cursor.fetchall()
                
                if not items or len(items) == 0:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Nenhum item na lista de produção'
                    }), 400
                
                # 2. Para cada item, adicionar ao estoque e registrar movimento
                from datetime import datetime
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                total_items = 0
                
                for item in items:
                    item_id, product_id, quantity, size, product_name = item
                    
                    # Atualizar estoque do produto
                    cursor.execute("""
                        UPDATE products 
                        SET stock = stock + ?
                        WHERE id = ?
                    """, (quantity, product_id))
                    
                    # Registrar movimento de entrada
                    cursor.execute("""
                        INSERT INTO stock_movements (product_id, type, quantity, reason, created_at)
                        VALUES (?, 'entrada', ?, 'Produção concluída', ?)
                    """, (product_id, quantity, now))
                    
                    total_items += quantity
                    print(f"✅ Produção concluída: {product_name} +{quantity} un → Estoque atualizado")
                
                # 3. Limpar lista de produção
                cursor.execute("DELETE FROM production_items")
                
                # 4. Commit das alterações
                conn.commit()
                conn.close()
                
                print(f"🎉 PRODUÇÃO CONCLUÍDA: {len(items)} produtos, {total_items} unidades adicionadas ao estoque")
                
                return jsonify({
                    'success': True,
                    'message': f'Produção concluída! {len(items)} produtos ({total_items} unidades) adicionados ao estoque.',
                    'items_count': len(items),
                    'total_quantity': total_items
                })
                
            except Exception as e:
                logger.error(f"Erro ao completar produção: {e}")
                print(f"❌ Erro ao completar produção: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # === ROTAS ANTIGAS (mantidas para compatibilidade) ===
        
        # API: Incrementar/Decrementar estoque
        @self.app.route('/api/products/<int:product_id>/adjust', methods=['POST'])
        def adjust_product(product_id):
            """Incrementa ou decrementa o estoque de um produto"""
            try:
                data = request.get_json()
                
                if 'change' not in data:
                    return jsonify({
                        'success': False,
                        'error': 'Campo "change" é obrigatório'
                    }), 400
                
                change = int(data['change'])
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Buscar quantidade atual
                cursor.execute("""
                    SELECT id, name, stock 
                    FROM products 
                    WHERE id = ?
                """, (product_id,))
                product = cursor.fetchone()
                
                if not product:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Produto não encontrado'
                    }), 404
                
                new_quantity = max(0, product[2] + change)  # Não permite negativo
                
                # Atualizar quantidade
                cursor.execute("""
                    UPDATE products 
                    SET stock = ?
                    WHERE id = ?
                """, (new_quantity, product_id))
                
                conn.commit()
                conn.close()
                
                action = "adicionadas" if change > 0 else "removidas"
                print(f"✅ Estoque ajustado: {product[1]} ({change:+d}) → {new_quantity} unidades")
                
                return jsonify({
                    'success': True,
                    'message': f'{abs(change)} unidades {action}',
                    'product_id': product_id,
                    'new_quantity': new_quantity
                })
                
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Mudança deve ser um número inteiro'
                }), 400
            except Exception as e:
                logger.error(f"Erro ao ajustar produto: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
    
    def get_local_ip(self) -> str:
        """Retorna o IP local da máquina"""
        try:
            # Conectar a um endereço externo para descobrir o IP local
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    def check_firewall_windows(self) -> bool:
        """Verifica se a porta está liberada no firewall do Windows"""
        try:
            import subprocess
            import platform
            
            if platform.system() != "Windows":
                return True  # Não é Windows, não precisa verificar
            
            # Tenta verificar se a regra existe no firewall
            cmd = f'netsh advfirewall firewall show rule name="Confeitaria - Painel Web (Porta {self.port})"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            # Se encontrou a regra, retorna True
            return "Confeitaria - Painel Web" in result.stdout
        except Exception:
            # Em caso de erro, assume que está OK para não bloquear o sistema
            return True
    
    def run(self, debug: bool = False):
        """
        Inicia o servidor Flask
        
        Args:
            debug: Modo debug (padrão: False)
        """
        local_ip = self.get_local_ip()
        firewall_ok = self.check_firewall_windows()
        
        print("=" * 60)
        print("🌐 SERVIDOR WEB INICIADO")
        print("=" * 60)
        print(f"📱 Acesso Local:  http://localhost:{self.port}")
        print(f"🌍 Acesso Rede:   http://{local_ip}:{self.port}")
        
        if not firewall_ok:
            print("=" * 60)
            print("⚠️  ATENÇÃO: FIREWALL PODE ESTAR BLOQUEANDO!")
            print("=" * 60)
            print("Para acessar do celular, execute como ADMINISTRADOR:")
            print(f"   .\\liberar_porta_{self.port}.ps1")
            print("=" * 60)
        else:
            print("=" * 60)
            print("✅ Firewall configurado!")
            print("=" * 60)
        
        print("")
        print("📱 PARA ACESSAR DO CELULAR:")
        print(f"   1. Conecte o celular na MESMA rede Wi-Fi")
        print(f"   2. Abra o navegador e digite: http://{local_ip}:{self.port}")
        print("")
        print("💻 PARA ACESSAR DO PRÓPRIO PC:")
        print(f"   Abra o navegador e digite: http://localhost:{self.port}")
        print("=" * 60)
        
        # Iniciar servidor (acessível na rede local)
        self.app.run(
            host='0.0.0.0',  # Permite acesso de qualquer IP na rede
            port=self.port,
            debug=debug,
            use_reloader=False  # Importante: desabilita reloader em thread
        )


def start_server(db_path: str, web_dir: str, port: int = 5000):
    """
    Função helper para iniciar o servidor em uma thread
    
    Args:
        db_path: Caminho para o banco de dados
        web_dir: Diretório dos arquivos web
        port: Porta do servidor
    """
    try:
        print(f"🔧 Configurando servidor Flask...")
        print(f"   - Banco: {db_path}")
        print(f"   - Web: {web_dir}")
        print(f"   - Porta: {port}")
        
        server = WebServer(db_path, web_dir, port)
        print(f"✅ Servidor Flask configurado")
        print(f"🚀 Iniciando servidor na porta {port}...")
        server.run()
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no servidor Flask: {e}")
        import traceback
        traceback.print_exc()
        raise

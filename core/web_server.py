"""
Servidor Web Flask para Painel da Cozinha
==========================================
Permite acesso via rede local para atualização de estoque de produtos
"""

from flask import Flask, jsonify, redirect, request, send_from_directory, g
import hashlib
import secrets
import sqlite3
import os
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
import socket

# Senha errada repetida (força bruta pela rede): depois de MAX_FALHAS_PIN tentativas
# erradas o aparelho fica BLOQUEIO_PIN_S segundos sem conseguir tentar de novo (além do
# bloqueio por usuário do AuthService, o mesmo do sistema).
MAX_FALHAS_PIN = 8
BLOQUEIO_PIN_S = 300

COOKIE_SESSAO = 'painel_sessao'
DURACAO_LEMBRAR_S = 30 * 24 * 3600  # "manter conectado": 30 dias, renovados a cada uso
DURACAO_SESSAO_S = 12 * 3600         # sem marcar: até fechar o navegador (no máximo 12 h)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _entra_no_painel(papel) -> bool:
    """Administrador e cozinha (e o perfil antigo); recepção não usa o painel."""
    try:
        from api.permissoes import entra_no_painel
        return entra_no_painel(papel)
    except ImportError:  # painel usado sem o motor
        return papel != 'recepcao'


class _BancoPainel:
    """Adaptador mínimo para o AuthService usar a conexão do painel."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _unidade(cursor, product_id) -> str:
    cursor.execute("SELECT unit FROM products WHERE id = ?", (product_id,))
    r = cursor.fetchone()
    return (r[0] or "un") if r else "un"


def _qtd(valor, unidade: str, minimo: float):
    """Quantidade conforme a unidade: "un" inteiro; "kg" até 3 casas (aceita vírgula).
    ValueError vira 400 nas rotas."""
    if unidade == "kg":
        n = round(float(str(valor).replace(",", ".")), 3)
    else:
        f = float(str(valor).replace(",", "."))
        if f != int(f):
            raise ValueError("Este produto é vendido por unidade: use um número inteiro.")
        n = int(f)
    if n < minimo:
        raise ValueError("Quantidade inválida.")
    return int(n) if n == int(n) else n


class WebServer:
    """Servidor web Flask para o painel da cozinha"""
    
    def __init__(self, db_path: str, web_dir: str, port: int = 5000, access_token: str = None):
        """
        Inicializa o servidor web

        Args:
            db_path: Caminho para o banco de dados SQLite
            web_dir: Diretório contendo os arquivos web (HTML, CSS, JS)
            port: Porta para o servidor (padrão: 5000)
            access_token: não é mais usado (era o PIN das versões anteriores); o painel
                agora exige login com usuário e senha (ver _setup_auth).
        """
        self.db_path = db_path
        self.web_dir = web_dir
        # Função que diz se a licença está em modo somente leitura (definida pelo motor).
        self.somente_leitura = None
        self.port = port
        self.access_token = access_token
        self.app = Flask(__name__)
        # Sem CORS: as páginas do painel são servidas por este mesmo servidor, então
        # nenhum outro site precisa (nem deve) chamar esta API pelo navegador.
        self._falhas_pin: dict = {}  # ip -> [falhas, bloqueado_ate]
        self._trava_pin = threading.Lock()

        # Configurar rotas
        self._setup_routes()
        self._setup_auth()
        self._setup_db_teardown()

    def _get_conn(self) -> sqlite3.Connection:
        """Abre (ou reaproveita) a conexão SQLite da requisição atual.

        Guardada em flask.g e fechada no teardown_request - isso garante que a
        conexão é fechada mesmo quando a rota retorna cedo em algum "if" ou
        lança uma exceção, sem precisar de try/finally repetido em cada rota
        (antes disso, várias rotas vazavam a conexão nesses caminhos de erro).
        """
        if 'db_conn' not in g:
            # sqlite3.connect criaria um arquivo vazio no lugar de um banco que sumiu;
            # o motor trata o banco ausente perguntando ao usuário, o painel só recusa.
            if not os.path.isfile(self.db_path):
                raise RuntimeError(f"Banco de dados não encontrado: {self.db_path}")
            g.db_conn = sqlite3.connect(self.db_path)
        return g.db_conn

    def _setup_db_teardown(self):
        @self.app.teardown_request
        def close_db_connection(exception=None):
            for nome in ('db_conn', 'auth_conn'):
                conn = g.pop(nome, None)
                if conn is not None:
                    conn.close()

    def _registrar_movimento(self, cursor, product_id, delta, category, reason, order_id=None):
        """Toda mudança de estoque feita pelo painel vira movimentação (aparece na tela
        Movimentação e nos relatórios) e entra no histórico do produto."""
        if not delta:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO stock_movements(product_id, type, category, quantity, reason, order_id, created_at, created_by) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (product_id, 'entrada' if delta > 0 else 'saida', category, abs(delta), reason, order_id, now, self._quem()),
        )
        try:
            cursor.execute(
                "INSERT INTO audit_logs(entity, entity_id, action, user, details, created_at) VALUES (?,?,?,?,?,?)",
                ('product', product_id, 'update', self._quem(), f"stock: {'+' if delta > 0 else ''}{delta} ({reason})", now),
            )
        except sqlite3.Error:
            pass  # banco sem tabela de auditoria: a movimentação já registra o essencial

    # ------------------------------------------------------------ login (usuário e senha)

    def _conn_auth(self) -> sqlite3.Connection:
        """Conexão própria do login (linhas com nome de coluna), separada da conexão das
        rotas, que esperam tuplas. Fechada no fim da requisição."""
        if 'auth_conn' not in g:
            if not os.path.isfile(self.db_path):
                raise RuntimeError(f"Banco de dados não encontrado: {self.db_path}")
            g.auth_conn = sqlite3.connect(self.db_path, timeout=10)
            g.auth_conn.row_factory = sqlite3.Row
        return g.auth_conn

    def _sessao(self):
        """Usuário da sessão do cookie, conferido no banco a cada requisição: usuário
        excluído, senha/perfil trocados (sessões apagadas) ou perfil sem acesso ao painel
        derrubam o acesso na hora. Renova o prazo a cada uso."""
        token = request.cookies.get(COOKIE_SESSAO) or ''
        if not token or len(token) > 200:
            return None
        conn = self._conn_auth()
        r = conn.execute(
            "SELECT s.id, s.lembrar, s.expires_at, s.last_seen, u.id AS uid, u.username, u.role "
            "FROM web_sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (_hash_token(token),)).fetchone()
        agora = time.time()
        if not r or r["expires_at"] < agora:
            if r:
                conn.execute("DELETE FROM web_sessions WHERE id=?", (r["id"],))
                conn.commit()
            return None
        if not _entra_no_painel(r["role"]):
            return None
        if agora - r["last_seen"] > 300:  # grava no máximo a cada 5 min
            novo_fim = agora + (DURACAO_LEMBRAR_S if r["lembrar"] else DURACAO_SESSAO_S)
            conn.execute("UPDATE web_sessions SET last_seen=?, expires_at=? WHERE id=?", (agora, novo_fim, r["id"]))
            conn.commit()
        return {"id": r["uid"], "username": r["username"], "role": r["role"], "sessao": r["id"], "lembrar": bool(r["lembrar"])}

    def _bloqueado(self, ip: str) -> int:
        with self._trava_pin:
            _, ate, _ = self._falhas_pin.get(ip, (0, 0.0, None))
            return int(ate - time.time()) + 1 if ate > time.time() else 0

    def _falhou(self, ip: str) -> None:
        with self._trava_pin:
            falhas, _, _ = self._falhas_pin.get(ip, (0, 0.0, None))
            falhas += 1
            self._falhas_pin[ip] = (0, time.time() + BLOQUEIO_PIN_S, None) if falhas >= MAX_FALHAS_PIN else (falhas, 0.0, None)

    def _quem(self) -> str:
        """Quem fez a alteração (movimentação, histórico): o usuário logado no painel."""
        u = g.get('usuario')
        return f"{u['username']} (painel)" if u else 'painel-web'

    def _setup_auth(self):
        """Toda a API do painel exige login (cookie de sessão). Livres: páginas,
        arquivos estáticos, nome/logo da empresa e as rotas de entrar/sair."""
        livres = {'/api/login', '/api/logout', '/api/sessao'}

        @self.app.before_request
        def check_sessao():
            if not request.path.startswith('/api/') or request.path in livres:
                return None
            # Contra CSRF: alteração só com o cabeçalho que o próprio painel manda (um
            # formulário de outro site não envia cabeçalho personalizado; o cookie já é
            # SameSite=Strict).
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('X-Painel') != '1':
                return jsonify({'success': False, 'error': 'Requisição recusada.'}), 403
            try:
                u = self._sessao()
            except (sqlite3.Error, RuntimeError) as e:
                return jsonify({'success': False, 'error': f'Banco de dados indisponível: {e}'}), 503
            if not u:
                return jsonify({'success': False, 'error': 'Entre com seu usuário e senha.', 'login': True}), 401
            g.usuario = u
            # Licença DWM bloqueada: o painel continua mostrando, mas não altera nada.
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and self.somente_leitura and self.somente_leitura():
                return jsonify({'success': False,
                                'error': 'Licença DWM bloqueada: o sistema está em modo somente leitura até a fatura ser regularizada.'}), 423
            return None

        @self.app.route('/api/sessao', methods=['GET'])
        def sessao():
            try:
                u = self._sessao()
            except (sqlite3.Error, RuntimeError):
                u = None
            if not u:
                return jsonify({'success': False, 'login': True}), 401
            return jsonify({'success': True, 'usuario': {'username': u['username'], 'lembrar': u['lembrar']}})

        @self.app.route('/api/login', methods=['POST'])
        def login():
            if request.headers.get('X-Painel') != '1':
                return jsonify({'success': False, 'error': 'Requisição recusada.'}), 403
            ip = request.remote_addr or '?'
            espera = self._bloqueado(ip)
            if espera:
                return jsonify({'success': False, 'error': f'Muitas tentativas erradas neste aparelho. Aguarde {espera}s.'}), 429
            dados = request.get_json(silent=True) or {}
            usuario = str(dados.get('usuario') or '').strip()
            senha = str(dados.get('senha') or '')
            lembrar = bool(dados.get('lembrar'))
            if not usuario or not senha:
                return jsonify({'success': False, 'error': 'Informe usuário e senha.'}), 400
            try:
                conn = self._conn_auth()
            except RuntimeError as e:
                return jsonify({'success': False, 'error': str(e)}), 503
            from core.services import AuthService  # mesma conferência e bloqueio do sistema
            auth = AuthService(_BancoPainel(conn))
            u = auth.authenticate(usuario, senha)
            if not u:
                self._falhou(ip)
                return jsonify({'success': False, 'error': auth.last_error or 'Usuário ou senha inválidos.'}), 401
            if not _entra_no_painel(u.role):
                return jsonify({'success': False, 'error': 'Seu perfil não usa o painel da cozinha. Fale com o administrador.'}), 403
            from core.senhas import senha_fraca
            if senha_fraca(u.username, senha):
                return jsonify({'success': False, 'error': 'Sua senha é a padrão ou fácil demais. Troque-a no computador do sistema antes de usar o painel.'}), 403
            with self._trava_pin:
                self._falhas_pin.pop(ip, None)
            token = secrets.token_urlsafe(32)
            agora = time.time()
            duracao = DURACAO_LEMBRAR_S if lembrar else DURACAO_SESSAO_S
            conn.execute("DELETE FROM web_sessions WHERE expires_at < ?", (agora,))
            conn.execute(
                "INSERT INTO web_sessions(token_hash, user_id, lembrar, created_at, expires_at, last_seen, ip, agent) VALUES (?,?,?,?,?,?,?,?)",
                (_hash_token(token), u.id, int(lembrar), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), agora + duracao, agora, ip,
                 (request.headers.get('User-Agent') or '')[:200]))
            conn.commit()
            try:
                from core.logger import log_event
                log_event(f"✅ Login: {u.username} (Perfil: {u.role}) [painel web {ip}]")
            except Exception:
                pass
            resp = jsonify({'success': True, 'usuario': {'username': u.username, 'lembrar': lembrar}})
            # HttpOnly: o JavaScript da página não lê o código; SameSite=Strict: outro site
            # não o usa. Sem "manter conectado" o cookie some ao fechar o navegador.
            resp.set_cookie(COOKIE_SESSAO, token, max_age=DURACAO_LEMBRAR_S if lembrar else None,
                            httponly=True, samesite='Strict', path='/')
            return resp

        @self.app.route('/api/logout', methods=['POST'])
        def logout():
            token = request.cookies.get(COOKIE_SESSAO) or ''
            if token and request.headers.get('X-Painel') == '1':
                try:
                    conn = self._conn_auth()
                    conn.execute("DELETE FROM web_sessions WHERE token_hash=?", (_hash_token(token),))
                    conn.commit()
                except (sqlite3.Error, RuntimeError):
                    pass
            resp = jsonify({'success': True})
            resp.delete_cookie(COOKIE_SESSAO, path='/', samesite='Strict')
            return resp

    def _setup_routes(self):
        """Configura as rotas da API"""

        # Página de seleção de acesso
        @self.app.route('/')
        def root():
            """Painel direto (pede usuário e senha se o aparelho não estiver conectado)."""
            return send_from_directory(self.web_dir, 'index.html')
        
        @self.app.route('/painel-info')
        def painel_info():
            """Nome da confeitaria para o cabeçalho do painel (público: aparece já na tela
            de login; não revela nada além do nome)."""
            nome, tem_logo = "Confeitaria", False
            try:
                conn = self._get_conn()
                r = conn.execute("SELECT name, logo_path FROM company WHERE id=1").fetchone()
                if r:
                    nome = r[0] or nome
                    tem_logo = bool(r[1] and os.path.isfile(r[1]))
            except Exception:
                pass
            return jsonify({'nome': nome, 'logo': tem_logo})

        @self.app.route('/empresa-logo')
        def empresa_logo():
            """Logo escolhida em Configurações → Empresa (só o arquivo registrado no banco)."""
            try:
                r = self._get_conn().execute("SELECT logo_path FROM company WHERE id=1").fetchone()
                caminho = r[0] if r else None
            except Exception:
                caminho = None
            if not caminho or not os.path.isfile(caminho):
                return ('', 404)
            return send_from_directory(os.path.dirname(caminho), os.path.basename(caminho), max_age=300)

        @self.app.route('/index.html')
        def index():
            """Página principal do painel"""
            return send_from_directory(self.web_dir, 'index.html')
        
        @self.app.route('/acesso.html')
        def acesso():
            """Endereço antigo (tela intermediária das versões anteriores): vai ao painel."""
            return redirect('/', code=301)
        
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
                conn = self._get_conn()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, name, description, size, stock, min_stock, unit
                    FROM products
                    ORDER BY name
                """)
                
                products = []
                for row in cursor.fetchall():
                    products.append({
                        'id': row['id'],
                        'name': row['name'],
                        'quantity': row['stock'],
                        'unit': row['unit'] or 'un',
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
            """Retorna todos os produtos (inclusive com stock=0, marcados como esgotados
            no campo 'in_stock' para o front-end exibir) - antes filtrava stock > 0 e o
            produto simplesmente sumia da lista sem nenhum aviso quando zerava."""
            try:
                conn = self._get_conn()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, name, description, size, stock, min_stock, unit
                    FROM products
                    ORDER BY (stock <= 0), name
                """)
                
                products = []
                for row in cursor.fetchall():
                    products.append({
                        'id': row['id'],
                        'name': row['name'],
                        'description': row['description'] or '',
                        'size': row['size'] or '',
                        'stock': row['stock'],
                        'unit': row['unit'] or 'un',
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
            """Retorna a lista de produção (production_items). Pedidos entram na lista
            pelo sistema ("Importar pedidos do dia"); a consulta direta a orders que
            existia aqui filtrava status que o sistema não usa e nunca trazia nada."""
            try:
                conn = self._get_conn()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 1. Busca itens adicionados manualmente na lista de produção
                cursor.execute("""
                    SELECT 
                        pi.id,
                        'manual' as source,
                        NULL as customer_name,
                        p.name as product_name,
                        p.unit as unit,
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
                        'unit': row['unit'] or 'un',
                        'delivery_date': '',
                        'status': 'pending',
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
                
                quantity = _qtd(data['quantity'], _unidade(self._get_conn().cursor(), product_id), 0)
                
                if quantity < 0:
                    return jsonify({
                        'success': False,
                        'error': 'Quantidade não pode ser negativa'
                    }), 400
                
                conn = self._get_conn()
                cursor = conn.cursor()
                
                # Verificar se o produto existe
                cursor.execute("SELECT id, name, stock, unit FROM products WHERE id = ?", (product_id,))
                product = cursor.fetchone()

                if not product:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Produto não encontrado'
                    }), 404

                # Atualizar quantidade (a diferença vira movimentação de ajuste)
                cursor.execute("""
                    UPDATE products
                    SET stock = ?
                    WHERE id = ?
                """, (quantity, product_id))
                self._registrar_movimento(cursor, product_id, round(quantity - (product[2] or 0), 3),
                                          'Ajuste de Inventário', 'Contagem no painel da cozinha')

                conn.commit()
                conn.close()
                
                print(f"✅ Estoque atualizado: {product[1]} → {quantity} {product[3] or 'un'}")
                
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
        
        # API: Atualizar item de produção
        @self.app.route('/api/production/<string:item_id>', methods=['PUT'])
        def update_production_item(item_id):
            """Atualiza quantidade, tamanho e/ou observações de um item da lista.

            Não mexe no estoque: a lista diz o que PRODUZIR, e o estoque só recebe as
            quantidades em "Produção feita" (complete_production). Antes, editar a
            quantidade já lançava a diferença no estoque e "Produção feita" somava a
            quantidade inteira de novo (10 -> 12 virava +14 no estoque).
            Pedidos não são editados por aqui: só pelo sistema."""
            try:
                data = request.get_json(silent=True) or {}
                if not item_id.startswith('manual_'):
                    return jsonify({
                        'success': False,
                        'error': 'Só itens da lista de produção podem ser editados no painel. Pedidos são alterados no sistema.'
                    }), 400
                if not any(k in data for k in ('quantity', 'size', 'notes')):
                    return jsonify({
                        'success': False,
                        'error': 'Pelo menos um campo ("quantity", "size" ou "notes") é obrigatório'
                    }), 400

                real_id = int(item_id.replace('manual_', ''))
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM production_items WHERE id = ?", (real_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'error': 'Item não encontrado'}), 404

                updates, params = [], []
                if 'quantity' in data:
                    cursor.execute("SELECT product_id FROM production_items WHERE id = ?", (real_id,))
                    new_quantity = _qtd(data['quantity'], _unidade(cursor, cursor.fetchone()[0]), 0.001)
                    if new_quantity <= 0:
                        return jsonify({'success': False, 'error': 'Quantidade deve ser maior que zero'}), 400
                    updates.append("quantity = ?")
                    params.append(new_quantity)
                if 'size' in data:
                    updates.append("size = ?")
                    params.append(str(data['size']).strip())
                if 'notes' in data:
                    updates.append("notes = ?")
                    params.append(str(data['notes']).strip())

                params.append(real_id)
                cursor.execute(f"UPDATE production_items SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
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
                quantity = _qtd(data['quantity'], _unidade(self._get_conn().cursor(), product_id), 0.001)
                size = data.get('size', '')
                notes = data.get('notes', 'Adicionado via web')
                
                if quantity <= 0:
                    return jsonify({
                        'success': False,
                        'error': 'Quantidade deve ser maior que zero'
                    }), 400
                
                conn = self._get_conn()
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
                conn = self._get_conn()
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
                conn = self._get_conn()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, name, size, unit
                    FROM products
                    ORDER BY name
                """)
                
                products = []
                for row in cursor.fetchall():
                    products.append({
                        'id': row['id'],
                        'name': row['name'],
                        'size': row['size'] or '',
                        'unit': row['unit'] or 'un'
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
                conn = self._get_conn()
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
                        SET stock = ROUND(stock + ?, 3)
                        WHERE id = ?
                    """, (quantity, product_id))
                    
                    # Registrar movimento de entrada (category='Produção' para aparecer
                    # filtrado na tela de Movimentação do desktop)
                    cursor.execute("""
                        INSERT INTO stock_movements (product_id, type, category, quantity, reason, created_at, created_by)
                        VALUES (?, 'entrada', 'Produção', ?, 'Produção concluída (painel web)', ?, ?)
                    """, (product_id, quantity, now, self._quem()))
                    
                    total_items += quantity

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
                
                change = round(float(str(data['change']).replace(",", ".")), 3)
                
                conn = self._get_conn()
                cursor = conn.cursor()
                
                # Buscar quantidade atual
                cursor.execute("""
                    SELECT id, name, stock, unit
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
                
                new_quantity = max(0, round(product[2] + change, 3))  # Não permite negativo
                new_quantity = int(new_quantity) if new_quantity == int(new_quantity) else new_quantity

                # Atualizar quantidade (a diferença real vira movimentação de ajuste)
                cursor.execute("""
                    UPDATE products
                    SET stock = ?
                    WHERE id = ?
                """, (new_quantity, product_id))
                self._registrar_movimento(cursor, product_id, round(new_quantity - product[2], 3),
                                          'Ajuste de Inventário', 'Ajuste no painel da cozinha (+/−)')

                conn.commit()
                conn.close()
                
                action = "adicionadas" if change > 0 else "removidas"
                print(f"✅ Estoque ajustado: {product[1]} ({change:+g}) → {new_quantity} {product[3] or 'un'}")
                
                return jsonify({
                    'success': True,
                    'message': f'{abs(change):g} {action}',
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


def start_server(db_path: str, web_dir: str, port: int = 5000, access_token: str = None):
    """
    Função helper para iniciar o servidor em uma thread

    Args:
        db_path: Caminho para o banco de dados
        web_dir: Diretório dos arquivos web
        port: Porta do servidor
        access_token: ignorado (PIN das versões anteriores; agora o login é por usuário)
    """
    try:
        print(f"🔧 Configurando servidor Flask...")
        print(f"   - Banco: {db_path}")
        print(f"   - Web: {web_dir}")
        print(f"   - Porta: {port}")
        print("   - Acesso: login com usuário e senha")

        server = WebServer(db_path, web_dir, port, access_token)
        print(f"✅ Servidor Flask configurado")
        print(f"🚀 Iniciando servidor na porta {port}...")
        server.run()
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no servidor Flask: {e}")
        import traceback
        traceback.print_exc()
        raise

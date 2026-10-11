export type View =
  | "inicio" | "pedidos" | "producao" | "pronta" | "clientes" | "produtos" | "movimentacao" | "relatorios"
  | "cfg-empresa" | "cfg-usuarios" | "cfg-banco" | "cfg-cozinha" | "cfg-licenca" | "cfg-aparencia" | "cfg-conta";

export interface Usuario { id: number; username: string; role: "admin" | "common" | string }
export interface Empresa { nome: string; logo: string | null; logo_path: string | null }

export interface Cliente { id: number; name: string; phone: string | null; address: string | null; observation: string | null; birthday?: string | null }

export interface Produto {
  id: number; name: string; description: string | null; size: string | null;
  stock: number; min_stock: number; price: number;
}

export interface Etiqueta { id: number; name: string; color: string }

/** Uma linha da lista de pedidos (itens de um lote vêm juntos). */
export interface PedidoLinha {
  id: number; ids: number[]; itens: number; lote: boolean;
  customer_id: number; cliente: string; telefone: string | null;
  produto: string; produto_size: string | null; quantity: number;
  delivery_date: string; status: string; label: string; label_color: string | null;
  notes: string | null; obs: string; created_at: string; stock_reserved: number;
}

export interface PedidoItem { id: number; product_id: number; produto: string; produto_size: string | null; quantity: number; stock_reserved: number }
export interface PedidoDetalhe {
  id: number; customer_id: number; cliente: string; product_id: number; quantity: number;
  delivery_date: string; status: string; label: string | null; notes: string | null; obs: string;
  stock_reserved: number; created_at: string; itens: PedidoItem[];
}

export interface Movimento {
  id: number; type: "entrada" | "saida"; category: string | null; quantity: number; reason: string | null;
  created_at: string; created_by: string | null; order_id: number | null; product_id: number; product_name: string;
}

export interface ItemProducao { id: number; product_id: number; produto: string; quantity: number; size: string | null; notes: string | null; created_at: string }
export interface EstoqueProducao { id: number; name: string; stock: number; min_stock: number; encomendas: number }

export interface Log { created_at: string; user: string | null; action: string; details: string | null }

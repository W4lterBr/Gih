export type View =
  | "inicio" | "pedidos" | "producao" | "pronta" | "custos" | "clientes" | "produtos" | "movimentacao" | "relatorios"
  | "cfg-empresa" | "cfg-usuarios" | "cfg-banco" | "cfg-cozinha" | "cfg-licenca" | "cfg-aparencia" | "cfg-conta";

/** trocar_senha: entrou com a senha padrão/fraca — o motor só libera depois da troca. */
/** Perfis: admin (tudo), recepcao, cozinha; "common" = perfil das versões antigas. */
export type Papel = "admin" | "recepcao" | "cozinha" | "common";
/** Tela -> "ver" (só consulta) ou "editar". Vem do motor (api/permissoes.py); tela ausente = sem acesso. */
export type Telas = Partial<Record<string, "ver" | "editar">>;
export interface Usuario { id: number; username: string; role: Papel | string; perfil?: string; telas?: Telas; trocar_senha?: boolean }
/** dias_fechados: dias da semana sem expediente, numeração do motor (0 = segunda … 6 = domingo). */
export interface Empresa { nome: string; logo: string | null; logo_path: string | null; dias_fechados?: number[] }

export interface Cliente { id: number; name: string; phone: string | null; address: string | null; observation: string | null; birthday?: string | null }

/** Unidade de venda: "un" (inteiro) ou "kg" (quilos com até 3 casas; preço por kg). */
export type Unidade = "un" | "kg";

export interface Produto {
  id: number; name: string; description: string | null; size: string | null;
  stock: number; min_stock: number; price: number; unit: Unidade;
}

export interface Etiqueta { id: number; name: string; color: string }

/** Entrega do pedido (o pagamento fica em `status`). */
export type Situacao = "aberto" | "entregue" | "cancelado";

/** Uma linha da lista de pedidos (itens de um lote vêm juntos). */
export interface PedidoLinha {
  id: number; ids: number[]; itens: number; lote: boolean;
  customer_id: number; cliente: string; telefone: string | null;
  produto: string; produto_size: string | null; quantity: number; unit: Unidade | "misto";
  delivery_date: string; status: string; situacao: Situacao; label: string; label_color: string | null;
  notes: string | null; obs: string; created_at: string; stock_reserved: number;
}

export interface PedidoItem { id: number; product_id: number; produto: string; produto_size: string | null; unit: Unidade; quantity: number; stock_reserved: number }
export interface PedidoDetalhe {
  id: number; customer_id: number; cliente: string; product_id: number; quantity: number;
  delivery_date: string; status: string; situacao: Situacao; label: string | null; notes: string | null; obs: string;
  stock_reserved: number; created_at: string; itens: PedidoItem[];
}

export interface Movimento {
  id: number; type: "entrada" | "saida"; category: string | null; quantity: number; reason: string | null;
  created_at: string; created_by: string | null; order_id: number | null; product_id: number; product_name: string; unit: Unidade;
}

export interface ItemProducao { id: number; product_id: number; produto: string; unit: Unidade; quantity: number; size: string | null; notes: string | null; created_at: string }
export interface EstoqueProducao { id: number; name: string; unit: Unidade; stock: number; min_stock: number; encomendas: number }

// ---------------------------------------------------------------- custos
// Valores de custo chegam como texto decimal exato ("0.01263291139240506329"):
// converter para número só na hora de exibir.

/** Unidades aceitas na digitação; a base de cada insumo é g, ml ou un. */
export type UnCusto = "mg" | "g" | "kg" | "ml" | "l" | "un" | "dz";
export type BaseCusto = "g" | "ml" | "un";

export interface Insumo {
  id: number; name: string; category: string; base_unit: BaseCusto; yield_pct: string; density: string | null; notes: string | null;
  preco_bruto: string | null; preco_base: string | null; base_custo: string; variacao_pct: string | null; compras: number; usos?: number;
  ultima_compra: { data: string; fornecedor: string | null; embalagens: string; conteudo: string; unidade: UnCusto; total: string } | null;
  unidades: UnCusto[];
}
export interface Compra {
  id: number; data: string; fornecedor: string | null; obs: string | null; embalagens: string; conteudo: string; unidade: UnCusto;
  quantidade_base: string; total: string; preco_base: string; por: string | null;
}
export interface ParametrosCusto {
  cost_basis: "ultima" | "media"; avg_days: number; labor_hour: string; fixed_pct: string; tax_pct: string; fee_pct: string; margin_pct: string; rounding: string;
}
export interface DecomposicaoPreco {
  preco: string; custo: string; despesas_fixas: string; impostos: string; taxas: string; lucro: string;
  margem_real_pct: string | null; markup: string | null; preco_exato?: string;
}
export interface ItemReceita {
  tipo: "insumo" | "receita"; ref_id: number; nome: string; quantity: string; unit: UnCusto; unidade_base?: BaseCusto; unidades?: UnCusto[];
  qtd_base?: string; preco_base?: string; custo: string | null; participacao_pct: string | null; pendencia: string | null;
}
export interface Receita {
  id: number; name: string; product_id: number | null; produto: { id: number; name: string; size: string | null; unit: Unidade; price: number } | null;
  notes: string | null; yield_qty: string; yield_unit: UnCusto; yield_base: BaseCusto; rendimento_base: string;
  labor_minutes: string; loss_pct: string; extra_cost: string; margin_pct: string | null;
  itens: ItemReceita[]; n_itens?: number; usada_em_outras?: boolean; erro?: boolean;
  custo_itens: string; custo_perdas: string; custo_mao_obra: string; custo_extra: string; custo_total: string;
  custo_base: string; venda_unidade: "kg" | "l" | "un"; custo_venda: string | null;
  preco: { margem_pct: string; despesas_pct: string; aviso: string | null; sugerido: DecomposicaoPreco | null; atual: DecomposicaoPreco | null; teste?: DecomposicaoPreco | null; preco_minimo: string | null } | null;
  pendencias: string[];
}

export interface Log { created_at: string; user: string | null; action: string; details: string | null }

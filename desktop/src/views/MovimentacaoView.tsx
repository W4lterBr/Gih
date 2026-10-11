import { useEffect, useMemo, useState } from "react";
import { abrirArquivo, api, escolherSalvar } from "../api";
import { useApp } from "../contexto";
import type { Movimento, Produto } from "../types";
import { fmtBRL, fmtDataHora, fmtInt, isoLocal } from "../format";
import { BarraSelecao, Cabecalho, Campo, CampoBusca, Kpi, Modal, Tabela, useCarregar, useDebounce, Vazio, type Coluna } from "../components/ui";
import { Combo } from "../components/Combo";
import { Icone } from "../components/Icone";

interface Resposta {
  movimentos: Movimento[];
  resumo: { entradas_hoje: number; saidas_hoje: number; producao_mes: number; perdas_qtd: number; perdas_valor: number };
  categorias: Record<"Entrada" | "Saída", string[]>;
  cores: Record<string, string>;
}

function NovoMovimento({ categorias, onClose, onSalvo }: { categorias: Resposta["categorias"]; onClose: () => void; onSalvo: (msg: string) => void }) {
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [tipo, setTipo] = useState<"entrada" | "saida">("entrada");
  const [categoria, setCategoria] = useState(categorias.Entrada[0]);
  const [produto, setProduto] = useState<number | null>(null);
  const [qtd, setQtd] = useState(1);
  const [data, setData] = useState(isoLocal());
  const [obs, setObs] = useState("");
  const [erro, setErro] = useState("");
  useEffect(() => { api.get<{ produtos: Produto[] }>("/produtos").then((r) => setProdutos(r.produtos)).catch(() => {}); }, []);
  useEffect(() => { setCategoria(categorias[tipo === "entrada" ? "Entrada" : "Saída"][0]); }, [tipo, categorias]);
  const p = produtos.find((x) => x.id === produto);
  const opcoes = useMemo(() => produtos.map((x) => ({ id: x.id, rotulo: x.name, detalhe: `${x.stock} em estoque` })), [produtos]);

  const salvar = async () => {
    if (!produto) { setErro("Escolha o produto."); return; }
    if (tipo === "saida" && p && qtd > p.stock) { setErro(`Estoque disponível: ${p.stock} un. Não é possível dar saída de ${qtd} un.`); return; }
    try {
      const r = await api.post<{ produto: string }>("/movimentos", { type: tipo, category: categoria, product_id: produto, quantity: qtd, date: data, notes: obs });
      onSalvo(`${qtd} un ${tipo === "entrada" ? "adicionadas" : "removidas"} (${categoria}) · ${r.produto}`);
    } catch (e) { setErro((e as Error).message); }
  };

  return (
    <Modal titulo="Nova movimentação de estoque" onClose={onClose} largura={520} aoEnviar={salvar}
      rodape={<><button type="button" className="btn" onClick={onClose}>Cancelar</button><button className="btn primary">Registrar</button></>}>
      <div className="form-grid">
        <Campo rotulo="Tipo" largura="1 / -1">
          <div className="seg">
            <button type="button" aria-pressed={tipo === "entrada"} onClick={() => setTipo("entrada")}>Entrada</button>
            <button type="button" aria-pressed={tipo === "saida"} onClick={() => setTipo("saida")}>Saída</button>
          </div>
        </Campo>
        <Campo rotulo="Produto" largura="1 / -1" dica={p ? `Estoque atual: ${p.stock} un` : undefined}>
          <Combo opcoes={opcoes} valor={produto} onChange={setProduto} placeholder="Digite para buscar…" autoFocus />
        </Campo>
        <Campo rotulo="Categoria">
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            {categorias[tipo === "entrada" ? "Entrada" : "Saída"].map((c) => <option key={c}>{c}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Quantidade"><input type="number" min={1} max={999999} value={qtd} onChange={(e) => setQtd(Number(e.target.value))} /></Campo>
        <Campo rotulo="Data"><input type="date" value={data} max={isoLocal()} onChange={(e) => setData(e.target.value)} /></Campo>
        <Campo rotulo="Observações" largura="1 / -1"><input value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Opcional" /></Campo>
      </div>
      {erro && <p className="form-erro">{erro}</p>}
    </Modal>
  );
}

const FILTROS: [string, string][] = [["todas", "Todas"], ["entrada", "Entradas"], ["saida", "Saídas"], ["producao", "Produção"], ["perda", "Perdas"]];
const PERIODOS: [string, string][] = [["hoje", "Hoje"], ["7d", "7 dias"], ["30d", "30 dias"], ["tudo", "Tudo"]];

export function MovimentacaoView() {
  const { toast, confirmar, somenteLeitura } = useApp();
  const [filtro, setFiltro] = useState("todas");
  const [periodo, setPeriodo] = useState("30d");
  const [q, setQ] = useState("");
  const qd = useDebounce(q);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [novo, setNovo] = useState(false);
  const { dados, recarregar } = useCarregar(() => api.get<Resposta>("/movimentos", { filtro, periodo, q: qd }), [filtro, periodo, qd], 5000);
  const linhas = dados?.movimentos ?? [];
  const marcados = linhas.filter((m) => sel.has(m.id));

  const excluir = async () => {
    const dePedido = marcados.filter((m) => m.order_id).length;
    const ok = await confirmar({
      titulo: marcados.length === 1 ? "Excluir movimentação" : `Excluir ${marcados.length} movimentações`, perigo: true, ok: "Excluir",
      texto: <>O estoque de cada produto volta ao valor anterior.{dePedido > 0 && <><br />{dePedido} movimentação(ões) gerada(s) por pedido não podem ser excluídas aqui — ajuste pelo pedido.</>}</>,
    });
    if (!ok) return;
    try {
      const r = await api.post<{ excluidos: number; bloqueados: number }>("/movimentos/excluir", { ids: marcados.map((m) => m.id) });
      toast(r.bloqueados ? `${r.excluidos} excluída(s); ${r.bloqueados} gerada(s) por pedido mantida(s).` : `${r.excluidos} movimentação(ões) excluída(s) e estoque ajustado.`, !!r.bloqueados && !r.excluidos);
      setSel(new Set()); recarregar(true);
    } catch (e) { toast((e as Error).message, true); }
  };

  const exportar = async () => {
    const d = new Date();
    const nome = `movimentacoes_${isoLocal(d).replace(/-/g, "")}_${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")}.xlsx`;
    const caminho = await escolherSalvar(nome, [{ name: "Excel", extensions: ["xlsx"] }]);
    if (!caminho) return;
    try {
      const r = await api.post<{ caminho: string; linhas: number }>("/movimentos/exportar", { caminho, filtros: { filtro, periodo, q: qd } });
      toast(`Exportado: ${r.linhas} linha(s).`);
      abrirArquivo(r.caminho).catch(() => {});
    } catch (e) { toast((e as Error).message, true); }
  };

  const cores = dados?.cores ?? {};
  const colunas: Coluna<Movimento>[] = [
    { id: "data", titulo: "Data", largura: "136px", ordenar: (m) => m.created_at, render: (m) => fmtDataHora(m.created_at) },
    { id: "produto", titulo: "Produto", largura: "minmax(160px,1.6fr)", ordenar: (m) => m.product_name, render: (m) => <b className="peso-500">{m.product_name}</b> },
    { id: "tipo", titulo: "Tipo", largura: "90px", ordenar: (m) => m.type, render: (m) => <span className={`mov ${m.type}`}>{m.type === "entrada" ? "Entrada" : "Saída"}</span> },
    { id: "cat", titulo: "Categoria", largura: "minmax(120px,1fr)", ordenar: (m) => m.category ?? "",
      render: (m) => m.category ? <span className="pill" style={{ color: cores[m.category] ?? "var(--text-2)" }}>{m.category}</span> : <span className="sutil">{m.order_id ? "Pedido" : "—"}</span> },
    { id: "qtd", titulo: "Qtd", largura: "70px", num: true, ordenar: (m) => m.quantity, render: (m) => <span className={m.type === "entrada" ? "pos" : "neg"}>{m.type === "entrada" ? "+" : "−"}{fmtInt(m.quantity)}</span> },
    { id: "motivo", titulo: "Motivo", largura: "minmax(120px,1.3fr)", render: (m) => <span className="sutil">{m.reason ?? ""}</span>, titleAttr: (m) => m.reason ?? "" },
    { id: "user", titulo: "Usuário", largura: "110px", ordenar: (m) => m.created_by ?? "", render: (m) => m.created_by ?? "—" },
  ];

  return (
    <section className="view">
      <Cabecalho titulo="Movimentação de estoque" sub="Entradas, saídas, produção e perdas">
        <button className="btn" onClick={exportar}><Icone nome="download" tam={14} />Exportar Excel</button>
        <button className="btn primary" onClick={() => setNovo(true)} disabled={!dados || somenteLeitura} title={somenteLeitura ? "Licença bloqueada: modo somente leitura" : undefined}><Icone nome="mais" tam={14} />Nova movimentação</button>
      </Cabecalho>
      {dados && (
        <div className="kpis kpis-4">
          <Kpi rotulo="Entradas hoje" valor={dados.resumo.entradas_hoje ? `+${fmtInt(dados.resumo.entradas_hoje)}` : "0"} tom="ok" onClick={() => { setFiltro("entrada"); setPeriodo("hoje"); }} />
          <Kpi rotulo="Saídas hoje" valor={dados.resumo.saidas_hoje ? `−${fmtInt(dados.resumo.saidas_hoje)}` : "0"} onClick={() => { setFiltro("saida"); setPeriodo("hoje"); }} />
          <Kpi rotulo="Produção no mês" valor={fmtInt(dados.resumo.producao_mes)} sub="unidades" tom="brand" onClick={() => { setFiltro("producao"); setPeriodo("30d"); }} />
          <Kpi rotulo="Perdas no mês" valor={fmtInt(dados.resumo.perdas_qtd)} sub={fmtBRL(dados.resumo.perdas_valor)} tom={dados.resumo.perdas_qtd ? "alert" : undefined} onClick={() => { setFiltro("perda"); setPeriodo("30d"); }} />
        </div>
      )}
      <div className="filters">
        <CampoBusca valor={q} onChange={setQ} placeholder="Nome do produto" />
        {FILTROS.map(([k, r]) => <button key={k} className="chip" aria-pressed={filtro === k} onClick={() => setFiltro(k)}>{r}</button>)}
        <div className="seg" role="group" aria-label="Período">
          {PERIODOS.map(([k, r]) => <button key={k} aria-pressed={periodo === k} onClick={() => setPeriodo(k)}>{r}</button>)}
        </div>
      </div>
      <BarraSelecao n={marcados.length} rotulo={["movimentação marcada", "movimentações marcadas"]} onLimpar={() => setSel(new Set())}>
        <button className="btn perigo" onClick={excluir} disabled={somenteLeitura}><Icone nome="lixo" tam={14} />Excluir e desfazer</button>
      </BarraSelecao>
      <Tabela linhas={linhas} colunas={colunas} chave={(m) => m.id} selecionadas={sel} onSelecionar={setSel}
        vazio={<Vazio icone="movimentacao" titulo="Nenhuma movimentação no período" />} />
      {linhas.length >= 500 && <p className="nota-rodape pad">Mostrando as 500 mais recentes. A exportação leva todas.</p>}
      {novo && dados && <NovoMovimento categorias={dados.categorias} onClose={() => setNovo(false)} onSalvo={(m) => { setNovo(false); toast(m); recarregar(true); }} />}
    </section>
  );
}

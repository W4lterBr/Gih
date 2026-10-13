import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp } from "../contexto";
import type { BaseCusto, Compra, Insumo, ParametrosCusto, Produto, Receita, UnCusto } from "../types";
import { custoPorMedida, fmtBRL, fmtCusto, fmtData, fmtInt, fmtNum, fmtPct, fmtTamanho, isoLocal, NOME_UNIDADE, paraCampo } from "../format";
import { Cabecalho, Campo, CampoBusca, Kpi, Modal, Tabela, useCarregar, useDebounce, Vazio, type Coluna } from "../components/ui";
import { Combo } from "../components/Combo";
import { Icone } from "../components/Icone";

type Aba = "receitas" | "insumos" | "parametros";
const CHAVE_ABA = "confeitaria.custos.aba";

const CATEGORIAS: [string, string][] = [["ingrediente", "Ingrediente"], ["embalagem", "Embalagem"], ["decoracao", "Decoração"], ["outro", "Outro"]];
const NOME_CAT = Object.fromEntries(CATEGORIAS);
const MEDIDAS: [BaseCusto, string, UnCusto[]][] = [["g", "Peso", ["g", "kg", "mg"]], ["ml", "Volume", ["ml", "l"]], ["un", "Unidade", ["un", "dz"]]];
const UN_DA_BASE: Record<BaseCusto, UnCusto[]> = { g: ["g", "kg", "mg"], ml: ["ml", "l"], un: ["un", "dz"] };
const FATOR: Record<UnCusto, number> = { mg: 0.001, g: 1, kg: 1000, ml: 1, l: 1000, un: 1, dz: 12 };
const BASE_DE: Record<UnCusto, BaseCusto> = { mg: "g", g: "g", kg: "g", ml: "ml", l: "ml", un: "un", dz: "un" };
const VENDA: Record<string, string> = { kg: "kg", l: "L", un: "unidade" };

/** "1.234,56" / "1,5" / "1.5" -> número (só para prévias; o motor refaz a conta em Decimal). */
const lerNum = (s: string) => {
  const t = String(s ?? "").trim().replace(/\s|R\$/g, "");
  if (!t) return NaN;
  return Number(t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t);
};
const n = (v: string | null | undefined) => (v === null || v === undefined ? NaN : Number(v));

export function CustosView() {
  const { somenteLeitura, motivoBloqueio } = useApp();
  const [aba, setAbaEstado] = useState<Aba>(() => {
    try { const s = localStorage.getItem(CHAVE_ABA); if (s === "insumos" || s === "parametros" || s === "receitas") return s; } catch { /* sem storage */ }
    return "receitas";
  });
  const setAba = (a: Aba) => { setAbaEstado(a); try { localStorage.setItem(CHAVE_ABA, a); } catch { /* sem storage */ } };
  const [novo, setNovo] = useState(0);
  const bloqueio = motivoBloqueio;

  return (
    <section className="view">
      <Cabecalho titulo="Custos" sub="Insumos comprados, fichas técnicas e preço de venda calculado com todas as casas decimais">
        <div className="seg" role="tablist">
          <button role="tab" aria-pressed={aba === "receitas"} onClick={() => setAba("receitas")}>Receitas</button>
          <button role="tab" aria-pressed={aba === "insumos"} onClick={() => setAba("insumos")}>Insumos</button>
          <button role="tab" aria-pressed={aba === "parametros"} onClick={() => setAba("parametros")}>Parâmetros</button>
        </div>
        {aba !== "parametros" && (
          <button className="btn primary" onClick={() => setNovo((x) => x + 1)} disabled={somenteLeitura} title={bloqueio}>
            <Icone nome="mais" tam={14} />{aba === "receitas" ? "Nova receita" : "Novo insumo"}
          </button>
        )}
      </Cabecalho>
      {aba === "receitas" && <AbaReceitas novo={novo} onIrInsumos={() => setAba("insumos")} />}
      {aba === "insumos" && <AbaInsumos novo={novo} />}
      {aba === "parametros" && <AbaParametros />}
    </section>
  );
}

// ================================================================ insumos

function AbaInsumos({ novo }: { novo: number }) {
  const { toast, confirmar, somenteLeitura } = useApp();
  const [q, setQ] = useState("");
  const qd = useDebounce(q);
  const [filtro, setFiltro] = useState<"" | "sem" | "subiu">("");
  const [dialogo, setDialogo] = useState<{ tipo: "editar"; i: Insumo | null } | { tipo: "compra"; i: Insumo } | { tipo: "historico"; i: Insumo } | null>(null);
  const { dados, recarregar } = useCarregar(() => api.get<{ insumos: Insumo[] }>("/custos/insumos", { q: qd }), [qd]);
  useEffect(() => { if (novo) setDialogo({ tipo: "editar", i: null }); }, [novo]);

  const todos = dados?.insumos ?? [];
  const semPreco = todos.filter((i) => i.preco_base === null);
  const subiram = todos.filter((i) => n(i.variacao_pct) > 0);
  const linhas = filtro === "sem" ? semPreco : filtro === "subiu" ? subiram : todos;

  const salvo = (msg: string) => { setDialogo(null); toast(msg); recarregar(true); };

  const excluir = async (i: Insumo) => {
    const ok = await confirmar({ titulo: "Excluir insumo", perigo: true, ok: "Excluir", texto: <><b>{i.name}</b> e o histórico de {i.compras} compra(s) serão excluídos.</> });
    if (!ok) return;
    try { await api.del(`/custos/insumos/${i.id}`); toast("Insumo excluído."); setDialogo(null); recarregar(true); }
    catch (e) { toast((e as Error).message, true); }
  };

  const colunas: Coluna<Insumo>[] = [
    { id: "nome", titulo: "Insumo", largura: "minmax(180px,1.6fr)", ordenar: (i) => i.name,
      render: (i) => <span className="who"><b>{i.name}</b><span className="sutil-sans">{NOME_CAT[i.category] ?? i.category}{n(i.yield_pct) < 100 ? ` · aproveitamento ${fmtPct(i.yield_pct)}` : ""}</span></span> },
    { id: "ultima", titulo: "Última compra", largura: "minmax(150px,1fr)", ordenar: (i) => i.ultima_compra?.data ?? "",
      render: (i) => i.ultima_compra
        ? <span className="who"><b className="b-normal">{fmtNum(i.ultima_compra.embalagens)} × {fmtNum(i.ultima_compra.conteudo, 6)} {NOME_UNIDADE[i.ultima_compra.unidade]} · {fmtBRL(Number(i.ultima_compra.total))}</b>
          <span className="sutil-sans">{fmtData(i.ultima_compra.data)}{i.ultima_compra.fornecedor ? ` · ${i.ultima_compra.fornecedor}` : ""}</span></span>
        : <span className="sutil">nenhuma</span> },
    { id: "custo", titulo: "Custo", largura: "150px", num: true, ordenar: (i) => n(i.preco_base) || 0,
      titleAttr: (i) => i.preco_base ? `${fmtCusto(i.preco_base, 8)} por ${i.base_unit} (${i.base_custo}${n(i.yield_pct) < 100 ? `, já considerando ${fmtPct(i.yield_pct)} de aproveitamento` : ""})` : "Registre uma compra",
      render: (i) => { const c = custoPorMedida(i.preco_base, i.base_unit); return i.preco_base ? <>{c.valor}<span className="sutil">{c.por}</span></> : <span className="estq esgotado">Sem preço</span>; } },
    { id: "var", titulo: "Variação", largura: "90px", num: true, ordenar: (i) => n(i.variacao_pct) || 0,
      titleAttr: () => "Última compra comparada com a anterior (preço por unidade)",
      render: (i) => i.variacao_pct === null ? <span className="sutil">—</span>
        : <span className={n(i.variacao_pct) > 0 ? "neg" : n(i.variacao_pct) < 0 ? "pos" : ""}>{n(i.variacao_pct) > 0 ? "+" : ""}{fmtPct(i.variacao_pct)}</span> },
    { id: "usos", titulo: "Receitas", largura: "80px", num: true, ordenar: (i) => i.usos ?? 0, render: (i) => (i.usos ? fmtInt(i.usos) : <span className="sutil">—</span>) },
    { id: "acoes", titulo: "", largura: "96px", render: (i) => (
      <span className="acoes-linha" onClick={(e) => e.stopPropagation()}>
        <button className="icone-btn" title="Registrar compra" disabled={somenteLeitura} onClick={() => setDialogo({ tipo: "compra", i })}><Icone nome="mais" tam={14} /></button>
        <button className="icone-btn" title="Histórico de compras" onClick={() => setDialogo({ tipo: "historico", i })}><Icone nome="historico" tam={14} /></button>
        <button className="icone-btn" title="Editar" onClick={() => setDialogo({ tipo: "editar", i })}><Icone nome="editar" tam={14} /></button>
      </span>
    ) },
  ];

  return (
    <>
      <div className="kpis kpis-3">
        <Kpi rotulo="Insumos" valor={fmtInt(todos.length)} sub="cadastrados" />
        <Kpi rotulo="Sem preço" valor={fmtInt(semPreco.length)} tom={semPreco.length ? "alert" : "ok"} sub={semPreco.length ? "receitas com eles ficam incompletas" : "todos com compra"} onClick={() => setFiltro((f) => (f === "sem" ? "" : "sem"))} />
        <Kpi rotulo="Subiram na última compra" valor={fmtInt(subiram.length)} tom={subiram.length ? "attn" : undefined} sub="revise os preços de venda" onClick={() => setFiltro((f) => (f === "subiu" ? "" : "subiu"))} />
      </div>
      <div className="filters">
        <CampoBusca valor={q} onChange={setQ} placeholder="Nome do insumo" />
        <button className="chip" aria-pressed={filtro === "sem"} onClick={() => setFiltro((f) => (f === "sem" ? "" : "sem"))}>Sem preço <span className="n">{semPreco.length}</span></button>
        <button className="chip" aria-pressed={filtro === "subiu"} onClick={() => setFiltro((f) => (f === "subiu" ? "" : "subiu"))}>Subiram <span className="n">{subiram.length}</span></button>
      </div>
      <Tabela linhas={linhas} colunas={colunas} chave={(i) => i.id} onAbrir={(i) => setDialogo({ tipo: "historico", i })} alturaLinha={50}
        vazio={<Vazio icone="custos" titulo={q || filtro ? "Nenhum insumo encontrado" : "Nenhum insumo cadastrado"}
          texto={q || filtro ? undefined : "Cadastre o que você compra (leite condensado, chocolate, caixas…) com o preço pago. O custo por grama sai da compra."} />} />
      {dialogo?.tipo === "editar" && <InsumoDialog insumo={dialogo.i} onClose={() => setDialogo(null)} onSalvo={salvo} onExcluir={dialogo.i ? () => excluir(dialogo.i!) : undefined} />}
      {dialogo?.tipo === "compra" && <CompraDialog insumo={dialogo.i} onClose={() => setDialogo(null)} onSalvo={salvo} />}
      {dialogo?.tipo === "historico" && <HistoricoDialog insumo={dialogo.i} onClose={() => { setDialogo(null); recarregar(true); }}
        onCompra={() => setDialogo({ tipo: "compra", i: dialogo.i })} onEditar={() => setDialogo({ tipo: "editar", i: dialogo.i })} />}
    </>
  );
}

interface CompraForm { data: string; fornecedor: string; embalagens: string; conteudo: string; unidade: UnCusto; total: string; obs: string }

function compraVazia(base: BaseCusto, ult?: Insumo["ultima_compra"]): CompraForm {
  return {
    data: isoLocal(), fornecedor: ult?.fornecedor ?? "", embalagens: "1",
    conteudo: ult ? paraCampo(ult.conteudo) : "", unidade: ult?.unidade ?? (base === "g" ? "g" : base === "ml" ? "ml" : "un"),
    total: "", obs: "",
  };
}

/** Prévia do custo da compra (a conta oficial é a do motor). */
function previaCompra(f: CompraForm, aproveitamento: number) {
  const emb = lerNum(f.embalagens || "1"), cont = lerNum(f.conteudo), tot = lerNum(f.total);
  if (!(emb > 0 && cont > 0 && tot > 0)) return null;
  const base = BASE_DE[f.unidade];
  const qtd = emb * cont * FATOR[f.unidade];
  const porBase = tot / qtd / (aproveitamento > 0 ? aproveitamento / 100 : 1);
  const m = custoPorMedida(String(porBase), base);
  return <>Total de {fmtNum(qtd, 3)} {base} · custo <b>{m.valor}{m.por}</b> ({fmtCusto(porBase, 6)} por {base}){aproveitamento < 100 ? `, já com ${fmtNum(aproveitamento)}% de aproveitamento` : ""}</>;
}

function CamposCompra({ f, setF, base, aproveitamento }: { f: CompraForm; setF: (f: CompraForm) => void; base: BaseCusto; aproveitamento: number }) {
  const unidades = UN_DA_BASE[base];
  return (
    <div className="form-grid">
      <Campo rotulo="Data da compra"><input type="date" value={f.data} max={isoLocal()} onChange={(e) => setF({ ...f, data: e.target.value })} /></Campo>
      <Campo rotulo="Fornecedor" largura="2 / -1"><input value={f.fornecedor} onChange={(e) => setF({ ...f, fornecedor: e.target.value })} placeholder="Opcional (mercado, atacado…)" /></Campo>
      <Campo rotulo="Embalagens"><input inputMode="decimal" value={f.embalagens} onChange={(e) => setF({ ...f, embalagens: e.target.value })} /></Campo>
      <Campo rotulo="Conteúdo de cada uma">
        <span className="campo-un">
          <input inputMode="decimal" value={f.conteudo} onChange={(e) => setF({ ...f, conteudo: e.target.value })} placeholder={base === "g" ? "395" : base === "ml" ? "1" : "12"} />
          <select value={unidades.includes(f.unidade) ? f.unidade : unidades[0]} onChange={(e) => setF({ ...f, unidade: e.target.value as UnCusto })}>
            {unidades.map((u) => <option key={u} value={u}>{NOME_UNIDADE[u]}</option>)}
          </select>
        </span>
      </Campo>
      <Campo rotulo="Valor pago (total)"><input inputMode="decimal" value={f.total} onChange={(e) => setF({ ...f, total: e.target.value })} placeholder="R$ 0,00" /></Campo>
      <p className="previa-compra" style={{ gridColumn: "1 / -1" }}>{previaCompra({ ...f, unidade: unidades.includes(f.unidade) ? f.unidade : unidades[0] }, aproveitamento) ?? "Informe conteúdo e valor pago: o custo por grama/ml/unidade aparece aqui. Inclua no valor o frete, se houver."}</p>
    </div>
  );
}

function InsumoDialog({ insumo, onClose, onSalvo, onExcluir }: { insumo: Insumo | null; onClose: () => void; onSalvo: (msg: string) => void; onExcluir?: () => void }) {
  const { somenteLeitura } = useApp();
  const [f, setF] = useState({
    name: insumo?.name ?? "", category: insumo?.category ?? "ingrediente", base_unit: (insumo?.base_unit ?? "g") as BaseCusto,
    yield_pct: paraCampo(insumo?.yield_pct ?? "100"), density: paraCampo(insumo?.density), notes: insumo?.notes ?? "",
  });
  const [compra, setCompra] = useState<CompraForm>(compraVazia("g"));
  const [erro, setErro] = useState("");
  const travaMedida = !!insumo && (insumo.compras > 0 || (insumo.usos ?? 0) > 0);
  const aprov = lerNum(f.yield_pct || "100");

  const salvar = async () => {
    if (!f.name.trim()) { setErro("Nome é obrigatório."); return; }
    const corpo: Record<string, unknown> = { ...f, density: f.base_unit === "un" ? null : f.density };
    if (!insumo && (compra.conteudo.trim() || compra.total.trim())) corpo.compra = { ...compra, unidade: UN_DA_BASE[f.base_unit].includes(compra.unidade) ? compra.unidade : UN_DA_BASE[f.base_unit][0] };
    try {
      if (insumo) { await api.put(`/custos/insumos/${insumo.id}`, corpo); onSalvo("Insumo atualizado."); }
      else { await api.post("/custos/insumos", corpo); onSalvo(corpo.compra ? "Insumo e compra cadastrados." : "Insumo cadastrado. Registre uma compra para ele ter custo."); }
    } catch (e) { setErro((e as Error).message); }
  };

  return (
    <Modal titulo={insumo ? "Editar insumo" : "Novo insumo"} onClose={onClose} largura={620} aoEnviar={salvar}
      rodape={<>
        {onExcluir && <button type="button" className="btn perigo" onClick={onExcluir} disabled={somenteLeitura}><Icone nome="lixo" tam={14} />Excluir</button>}
        <span className="grow" />
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button className="btn primary" disabled={somenteLeitura}>Salvar</button>
      </>}>
      <div className="form-grid">
        <Campo rotulo="Nome" largura="1 / 3"><input autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Ex.: Leite condensado" /></Campo>
        <Campo rotulo="Categoria">
          <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
            {CATEGORIAS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Medido por" largura="1 / -1" dica={travaMedida ? "Já tem compras ou está em receitas: a medida não muda." : "Como você compra e usa nas receitas. Peso: g, kg. Volume: ml, L. Unidade: un, dúzia."}>
          <div className="seg">
            {MEDIDAS.map(([b, r]) => <button type="button" key={b} aria-pressed={f.base_unit === b} disabled={travaMedida} onClick={() => setF({ ...f, base_unit: b })}>{r}</button>)}
          </div>
        </Campo>
        <Campo rotulo="Aproveitamento (%)" dica="O que sobra para usar. Ex.: morango limpo 80%, ovo sem casca 88%. Embalagens: 100%.">
          <input inputMode="decimal" value={f.yield_pct} onChange={(e) => setF({ ...f, yield_pct: e.target.value })} />
        </Campo>
        {f.base_unit !== "un" && (
          <Campo rotulo="Densidade (g por ml)" largura="2 / -1" dica="Opcional. Permite usar em ml um insumo comprado em g (e o contrário). Ex.: óleo 0,92; leite 1,03; mel 1,42.">
            <input inputMode="decimal" value={f.density} onChange={(e) => setF({ ...f, density: e.target.value })} placeholder="—" />
          </Campo>
        )}
        <Campo rotulo="Observações" largura="1 / -1"><input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Marca preferida, onde comprar…" /></Campo>
      </div>
      {!insumo && (
        <div className="bloco-compra">
          <span className="sect-t">Primeira compra (opcional)</span>
          <CamposCompra f={compra} setF={setCompra} base={f.base_unit} aproveitamento={aprov} />
        </div>
      )}
      {erro && <p className="form-erro" role="alert">{erro}</p>}
    </Modal>
  );
}

function CompraDialog({ insumo, onClose, onSalvo }: { insumo: Insumo; onClose: () => void; onSalvo: (msg: string) => void }) {
  const { somenteLeitura } = useApp();
  const [f, setF] = useState<CompraForm>(() => compraVazia(insumo.base_unit, insumo.ultima_compra));
  const [erro, setErro] = useState("");
  const salvar = async () => {
    try { await api.post(`/custos/insumos/${insumo.id}/compras`, f); onSalvo(`Compra de ${insumo.name} registrada.`); }
    catch (e) { setErro((e as Error).message); }
  };
  const ult = insumo.ultima_compra;
  return (
    <Modal titulo={`Registrar compra · ${insumo.name}`} onClose={onClose} largura={620} aoEnviar={salvar}
      rodape={<><button type="button" className="btn" onClick={onClose}>Cancelar</button><button className="btn primary" disabled={somenteLeitura}>Registrar</button></>}>
      {ult && <p className="nota-topo">Última: {fmtData(ult.data)} · {fmtNum(ult.embalagens)} × {fmtNum(ult.conteudo, 6)} {NOME_UNIDADE[ult.unidade]} por {fmtBRL(Number(ult.total))}{(() => { const m = custoPorMedida(insumo.preco_base, insumo.base_unit); return insumo.preco_base ? ` (${m.valor}${m.por})` : ""; })()}</p>}
      <CamposCompra f={f} setF={setF} base={insumo.base_unit} aproveitamento={lerNum(insumo.yield_pct)} />
      <Campo rotulo="Observações"><input value={f.obs} onChange={(e) => setF({ ...f, obs: e.target.value })} placeholder="Opcional (promoção, marca…)" /></Campo>
      {erro && <p className="form-erro" role="alert">{erro}</p>}
    </Modal>
  );
}

function HistoricoDialog({ insumo, onClose, onCompra, onEditar }: { insumo: Insumo; onClose: () => void; onCompra: () => void; onEditar: () => void }) {
  const { toast, confirmar, somenteLeitura } = useApp();
  const { dados, recarregar } = useCarregar(() => api.get<{ insumo: Insumo; compras: Compra[]; usos: string[] }>(`/custos/insumos/${insumo.id}/compras`), [insumo.id]);
  const i = dados?.insumo ?? insumo;
  const m = custoPorMedida(i.preco_base, i.base_unit);
  const excluir = async (c: Compra) => {
    if (!(await confirmar({ titulo: "Excluir compra", perigo: true, ok: "Excluir", texto: `Compra de ${fmtData(c.data)} (${fmtBRL(Number(c.total))}) sai do histórico e o custo é recalculado.` }))) return;
    try { await api.del(`/custos/compras/${c.id}`); toast("Compra excluída."); recarregar(true); }
    catch (e) { toast((e as Error).message, true); }
  };
  return (
    <Modal titulo={i.name} onClose={onClose} largura={760}
      rodape={<>
        <button type="button" className="btn" onClick={onEditar}><Icone nome="editar" tam={14} />Editar insumo</button>
        <span className="grow" />
        <button type="button" className="btn" onClick={onClose}>Fechar</button>
        <button type="button" className="btn primary" onClick={onCompra} disabled={somenteLeitura}><Icone nome="mais" tam={14} />Registrar compra</button>
      </>}>
      <div className="kpis kpis-3 sem-pad">
        <Kpi rotulo="Custo usado nas receitas" valor={i.preco_base ? <>{m.valor}<small className="sutil">{m.por}</small></> : "Sem preço"} tom={i.preco_base ? "brand" : "alert"}
          sub={i.preco_base ? `${fmtCusto(i.preco_base, 8)} por ${i.base_unit}` : "registre uma compra"} />
        <Kpi rotulo="Base do custo" valor={<span className="kpi-texto">{i.base_custo}</span>} sub={n(i.yield_pct) < 100 ? `÷ aproveitamento de ${fmtPct(i.yield_pct)}` : "aproveitamento 100%"} />
        <Kpi rotulo="Usado em" valor={fmtInt(dados?.usos.length ?? 0)} sub={dados?.usos.length ? dados.usos.slice(0, 3).join(", ") + (dados.usos.length > 3 ? "…" : "") : "nenhuma receita"} />
      </div>
      <div className="tabela-simples">
        <div className="ts-cab ts-compras"><span>Data</span><span>Compra</span><span>Fornecedor</span><span className="num">Pago</span><span className="num">Custo</span><span /></div>
        {(dados?.compras ?? []).map((c, k, l) => {
          const anterior = l[k + 1];
          const varia = anterior ? (Number(c.preco_base) / Number(anterior.preco_base) - 1) * 100 : null;
          const cm = custoPorMedida(c.preco_base, i.base_unit);
          return (
            <div className="ts-linha ts-compras" key={c.id} title={c.obs ?? undefined}>
              <span>{fmtData(c.data)}</span>
              <span>{fmtNum(c.embalagens)} × {fmtNum(c.conteudo)} {NOME_UNIDADE[c.unidade]}</span>
              <span className="sutil-sans">{c.fornecedor ?? "—"}{c.por ? ` · por ${c.por}` : ""}</span>
              <span className="num">{fmtBRL(Number(c.total))}</span>
              <span className="num" title={`${fmtCusto(c.preco_base, 8)} por ${i.base_unit} (sem aproveitamento)`}>
                {cm.valor}<span className="sutil">{cm.por}</span>
                {varia !== null && Math.abs(varia) >= 0.05 && <small className={varia > 0 ? "neg" : "pos"}> {varia > 0 ? "+" : ""}{fmtNum(varia, 1)}%</small>}
              </span>
              <span><button className="icone-btn" title="Excluir compra" disabled={somenteLeitura} onClick={() => excluir(c)}><Icone nome="lixo" tam={13} /></button></span>
            </div>
          );
        })}
        {dados && !dados.compras.length && <div className="ts-vazio">Nenhuma compra registrada.</div>}
      </div>
    </Modal>
  );
}

// ================================================================ receitas

function AbaReceitas({ novo, onIrInsumos }: { novo: number; onIrInsumos: () => void }) {
  const [q, setQ] = useState("");
  const qd = useDebounce(q);
  const [filtro, setFiltro] = useState<"" | "pend" | "margem">("");
  const [editar, setEditar] = useState<{ id: number | null } | null>(null);
  const { toast } = useApp();
  const { dados, recarregar } = useCarregar(() => api.get<{ receitas: Receita[]; parametros: ParametrosCusto }>("/custos/receitas", { q: qd }), [qd]);
  useEffect(() => { if (novo) setEditar({ id: null }); }, [novo]);

  const todas = dados?.receitas ?? [];
  const prm = dados?.parametros;
  const desejada = (r: Receita) => n(r.margin_pct ?? prm?.margin_pct ?? "0");
  const abaixo = (r: Receita) => !!r.preco?.atual && n(r.preco.atual.margem_real_pct) < desejada(r) - 0.05;
  const pend = todas.filter((r) => r.pendencias?.length);
  const baixas = todas.filter(abaixo);
  const linhas = filtro === "pend" ? pend : filtro === "margem" ? baixas : todas;

  const colunas: Coluna<Receita>[] = [
    { id: "nome", titulo: "Receita", largura: "minmax(190px,1.6fr)", ordenar: (r) => r.name,
      render: (r) => <span className="who"><b>{r.name}{r.pendencias?.length ? <span className="pend-ic" title={r.pendencias.join("\n")}><Icone nome="alerta" tam={12} /></span> : null}</b>
        <span className="sutil-sans">{r.produto ? `Produto: ${r.produto.name}${r.produto.size ? ` (${fmtTamanho(r.produto.size)})` : ""}` : r.usada_em_outras ? "Usada em outras receitas" : "Sem produto vinculado"}</span></span> },
    { id: "rend", titulo: "Rende", largura: "100px", num: true, render: (r) => r.erro ? "—" : `${fmtNum(r.yield_qty)} ${NOME_UNIDADE[r.yield_unit]}` },
    { id: "lote", titulo: "Custo do lote", largura: "120px", num: true, ordenar: (r) => n(r.custo_total) || 0, render: (r) => fmtCusto(r.custo_total, 2) },
    { id: "unit", titulo: "Custo por venda", largura: "130px", num: true, ordenar: (r) => n(r.custo_venda) || 0,
      titleAttr: (r) => (r.custo_venda ? `${fmtCusto(r.custo_venda, 8)} por ${VENDA[r.venda_unidade]}` : ""),
      render: (r) => r.custo_venda ? <>{fmtCusto(r.custo_venda)}<span className="sutil">/{r.venda_unidade === "un" ? "un" : VENDA[r.venda_unidade]}</span></> : <span className="sutil">—</span> },
    { id: "sug", titulo: "Preço sugerido", largura: "120px", num: true, ordenar: (r) => n(r.preco?.sugerido?.preco) || 0,
      render: (r) => r.preco?.sugerido ? <b>{fmtBRL(Number(r.preco.sugerido.preco))}</b> : <span className="sutil">—</span> },
    { id: "atual", titulo: "Preço atual", largura: "110px", num: true, ordenar: (r) => r.produto?.price ?? 0,
      render: (r) => r.produto ? fmtBRL(r.produto.price) : <span className="sutil">—</span> },
    { id: "margem", titulo: "Lucro real", largura: "100px", num: true, ordenar: (r) => n(r.preco?.atual?.margem_real_pct) || -999,
      titleAttr: (r) => (r.preco?.atual ? `Lucro de ${fmtCusto(r.preco.atual.lucro)} por ${VENDA[r.venda_unidade]} no preço atual (desejado: ${fmtPct(desejada(r))})` : ""),
      render: (r) => r.preco?.atual ? <span className={abaixo(r) ? "neg" : "pos"}>{fmtPct(r.preco.atual.margem_real_pct)}</span> : <span className="sutil">—</span> },
  ];

  return (
    <>
      <div className="kpis kpis-3">
        <Kpi rotulo="Receitas" valor={fmtInt(todas.length)} sub={`lucro desejado padrão ${fmtPct(prm?.margin_pct)}`} />
        <Kpi rotulo="Incompletas" valor={fmtInt(pend.length)} tom={pend.length ? "attn" : "ok"} sub={pend.length ? "insumo sem preço ou rendimento" : "custos completos"} onClick={() => setFiltro((f) => (f === "pend" ? "" : "pend"))} />
        <Kpi rotulo="Preço abaixo do lucro desejado" valor={fmtInt(baixas.length)} tom={baixas.length ? "alert" : "ok"} sub={baixas.length ? "clique para ver" : "todos cobrem o lucro"} onClick={() => setFiltro((f) => (f === "margem" ? "" : "margem"))} />
      </div>
      <div className="filters">
        <CampoBusca valor={q} onChange={setQ} placeholder="Receita ou produto" />
        <button className="chip" aria-pressed={filtro === "pend"} onClick={() => setFiltro((f) => (f === "pend" ? "" : "pend"))}>Incompletas <span className="n">{pend.length}</span></button>
        <button className="chip" aria-pressed={filtro === "margem"} onClick={() => setFiltro((f) => (f === "margem" ? "" : "margem"))}>Abaixo do lucro <span className="n">{baixas.length}</span></button>
      </div>
      <Tabela linhas={linhas} colunas={colunas} chave={(r) => r.id} onAbrir={(r) => setEditar({ id: r.id })} alturaLinha={50}
        linhaClasse={(r) => (abaixo(r) ? "linha-alerta" : undefined)}
        vazio={<Vazio icone="custos" titulo={q || filtro ? "Nenhuma receita encontrada" : "Nenhuma receita cadastrada"}
          texto={q || filtro ? undefined : "Monte a ficha técnica do produto com os insumos e as quantidades. O custo e o preço de venda saem sozinhos."}>
          {!q && !filtro && <button className="btn" onClick={onIrInsumos}>Cadastrar insumos primeiro</button>}
        </Vazio>} />
      {editar && <ReceitaEditor id={editar.id} onClose={() => setEditar(null)}
        onSalvo={(msg, fechar) => { toast(msg); recarregar(true); if (fechar) setEditar(null); }}
        onTrocar={(id) => setEditar({ id })} />}
    </>
  );
}

interface ItemForm { chave: number; tipo: "insumo" | "receita"; ref_id: number | null; quantity: string; unit: UnCusto }
interface FormReceita { name: string; product_id: number | null; yield_qty: string; yield_unit: UnCusto; labor_minutes: string; loss_pct: string; extra_cost: string; margin_pct: string; notes: string }

/** Combo único para insumos e receitas: receitas ganham +1.000.000 no id. */
const OFFSET = 1_000_000;

function ReceitaEditor({ id, onClose, onSalvo, onTrocar }: { id: number | null; onClose: () => void; onSalvo: (msg: string, fechar: boolean) => void; onTrocar: (id: number) => void }) {
  const { toast, confirmar, somenteLeitura } = useApp();
  const [carregado, setCarregado] = useState(id === null);
  const [f, setF] = useState<FormReceita>({ name: "", product_id: null, yield_qty: "1", yield_unit: "un", labor_minutes: "", loss_pct: "", extra_cost: "", margin_pct: "", notes: "" });
  const [itens, setItens] = useState<ItemForm[]>([{ chave: 1, tipo: "insumo", ref_id: null, quantity: "", unit: "g" }]);
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [receitas, setReceitas] = useState<Receita[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [prm, setPrm] = useState<ParametrosCusto | null>(null);
  const [calc, setCalc] = useState<Receita | null>(null);
  /** Corpo (JSON) que gerou `calc`: se o formulário mudou, os custos por linha ficam ocultos até o novo cálculo. */
  const [calcDe, setCalcDe] = useState("");
  const [erroCalc, setErroCalc] = useState("");
  const [erro, setErro] = useState("");
  const [teste, setTeste] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [sujo, setSujo] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<{ insumos: Insumo[] }>("/custos/insumos"),
      api.get<{ receitas: Receita[]; parametros: ParametrosCusto }>("/custos/receitas"),
      api.get<{ produtos: Produto[] }>("/produtos"),
      id ? api.get<Receita>(`/custos/receitas/${id}`) : Promise.resolve(null),
    ]).then(([i, r, p, rec]) => {
      setInsumos(i.insumos); setReceitas(r.receitas); setProdutos(p.produtos); setPrm(r.parametros);
      if (rec) {
        setF({
          name: rec.name, product_id: rec.product_id, yield_qty: paraCampo(rec.yield_qty), yield_unit: rec.yield_unit,
          labor_minutes: rec.labor_minutes === "0" ? "" : paraCampo(rec.labor_minutes), loss_pct: rec.loss_pct === "0" ? "" : paraCampo(rec.loss_pct),
          extra_cost: rec.extra_cost === "0" ? "" : paraCampo(rec.extra_cost), margin_pct: paraCampo(rec.margin_pct), notes: rec.notes ?? "",
        });
        setItens(rec.itens.length ? rec.itens.map((it, k) => ({ chave: k + 1, tipo: it.tipo, ref_id: it.ref_id, quantity: paraCampo(it.quantity), unit: it.unit })) : [{ chave: 1, tipo: "insumo", ref_id: null, quantity: "", unit: "g" }]);
        setCalc(rec);
        setCarregado(true);
      }
    }).catch((e) => { toast(String(e.message), true); onClose(); });
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const insPorId = useMemo(() => new Map(insumos.map((i) => [i.id, i])), [insumos]);
  const recPorId = useMemo(() => new Map(receitas.map((r) => [r.id, r])), [receitas]);
  const opcoes = useMemo(() => [
    ...insumos.map((i) => { const m = custoPorMedida(i.preco_base, i.base_unit); return { id: i.id, rotulo: i.name, detalhe: i.preco_base ? `${m.valor}${m.por}` : "sem preço" }; }),
    ...receitas.filter((r) => r.id !== id && !r.erro).map((r) => ({ id: OFFSET + r.id, rotulo: `${r.name}`, detalhe: `receita · rende ${fmtNum(r.yield_qty)} ${NOME_UNIDADE[r.yield_unit]}` })),
  ], [insumos, receitas, id]);
  const opProdutos = useMemo(() => [{ id: 0, rotulo: "— Nenhum (receita base, ex.: recheio) —" }, ...produtos.map((p) => ({ id: p.id, rotulo: p.name, detalhe: `${fmtBRL(p.price)}${p.unit === "kg" ? "/kg" : ""}${p.size ? ` · ${fmtTamanho(p.size)}` : ""}` }))], [produtos]);
  const produto = f.product_id ? produtos.find((p) => p.id === f.product_id) ?? null : null;

  const corpo = useMemo(() => ({
    id, ...f, name: f.name.trim() || "Receita", preco_teste: teste || undefined,
    itens: itens.filter((i) => i.ref_id && i.quantity.trim()).map((i) => ({ tipo: i.tipo, ref_id: i.ref_id, quantity: i.quantity, unit: i.unit })),
  }), [id, f, itens, teste]);
  const corpoD = useDebounce(corpo, 250);

  // Recalcula no motor (Decimal) a cada mudança: a prévia é a conta oficial.
  useEffect(() => {
    if (!carregado) return;
    let vivo = true;
    const chave = JSON.stringify(corpoD);
    api.post<Receita>("/custos/simular", corpoD).then((r) => { if (vivo) { setCalc(r); setCalcDe(chave); setErroCalc(""); } })
      .catch((e) => { if (vivo) { setCalcDe(""); setErroCalc((e as Error).message); } });
    return () => { vivo = false; };
  }, [corpoD, carregado]);

  const mudar = (p: Partial<FormReceita>) => { setF((x) => ({ ...x, ...p })); setSujo(true); };
  const mudarItem = (chave: number, p: Partial<ItemForm>) => { setItens((l) => l.map((i) => (i.chave === chave ? { ...i, ...p } : i))); setSujo(true); };
  const adicionar = () => setItens((l) => [...l, { chave: Math.max(0, ...l.map((i) => i.chave)) + 1, tipo: "insumo", ref_id: null, quantity: "", unit: "g" }]);
  const escolher = (chave: number, v: number | null) => {
    if (v === null) { mudarItem(chave, { ref_id: null }); return; }
    if (v >= OFFSET) {
      const r = recPorId.get(v - OFFSET);
      mudarItem(chave, { tipo: "receita", ref_id: v - OFFSET, unit: r ? UN_DA_BASE[r.yield_base][0] : "g" });
    } else {
      const i = insPorId.get(v);
      mudarItem(chave, { tipo: "insumo", ref_id: v, unit: i ? i.base_unit : "g" });
    }
  };
  const unidadesItem = (i: ItemForm): UnCusto[] => {
    if (!i.ref_id) return ["g", "kg", "ml", "l", "un", "dz"];
    if (i.tipo === "insumo") return insPorId.get(i.ref_id)?.unidades ?? ["g"];
    const r = recPorId.get(i.ref_id);
    return r ? UN_DA_BASE[r.yield_base] : ["g"];
  };

  const gravar = async (): Promise<number | null> => {
    if (!f.name.trim()) { setErro("Dê um nome à receita."); return null; }
    setErro(""); setSalvando(true);
    const { preco_teste: _t, ...dados } = corpo; // eslint-disable-line @typescript-eslint/no-unused-vars
    try {
      if (id) { await api.put(`/custos/receitas/${id}`, { ...dados, name: f.name }); setSujo(false); return id; }
      const r = await api.post<{ id: number }>("/custos/receitas", { ...dados, name: f.name });
      setSujo(false);
      return r.id;
    } catch (e) { setErro((e as Error).message); return null; }
    finally { setSalvando(false); }
  };

  const salvar = async () => { const r = await gravar(); if (r) onSalvo(id ? "Receita salva." : "Receita criada.", true); };

  const aplicar = async (preco: string) => {
    if (!produto) return;
    const ok = await confirmar({ titulo: "Aplicar preço ao produto", ok: "Aplicar",
      texto: <><b>{produto.name}</b> passa de {fmtBRL(produto.price)} para <b>{fmtBRL(Number(preco))}</b>{produto.unit === "kg" ? " por kg" : ""}. Pedidos já feitos não mudam.</> });
    if (!ok) return;
    const rid = await gravar();
    if (!rid) return;
    try {
      await api.post(`/custos/receitas/${rid}/aplicar-preco`, { price: preco });
      setProdutos((l) => l.map((p) => (p.id === produto.id ? { ...p, price: Number(preco) } : p)));
      onSalvo(`Preço de ${produto.name} atualizado para ${fmtBRL(Number(preco))}.`, false);
      if (!id) onTrocar(rid);
    } catch (e) { toast((e as Error).message, true); }
  };

  const fechar = async () => {
    if (sujo && !(await confirmar({ titulo: "Descartar alterações?", texto: "A receita tem mudanças que não foram salvas.", ok: "Descartar", perigo: true }))) return;
    onClose();
  };

  const excluir = async () => {
    if (!id) return;
    if (!(await confirmar({ titulo: "Excluir receita", perigo: true, ok: "Excluir", texto: <><b>{f.name}</b> será excluída. O produto vinculado não muda.</> }))) return;
    try { await api.del(`/custos/receitas/${id}`); onSalvo("Receita excluída.", true); }
    catch (e) { toast((e as Error).message, true); }
  };

  const duplicar = async () => {
    if (!id) return;
    if (sujo && !(await confirmar({ titulo: "Duplicar a versão salva?", texto: "A cópia é feita da receita salva; as mudanças ainda não salvas serão descartadas.", ok: "Duplicar" }))) return;
    setSujo(false);
    try { const r = await api.post<{ id: number }>(`/custos/receitas/${id}/duplicar`); onSalvo("Receita duplicada (sem produto vinculado).", false); onTrocar(r.id); }
    catch (e) { toast((e as Error).message, true); }
  };

  const calcAtual = calcDe === JSON.stringify(corpo);
  const linhaCalc = (k: number) => {
    if (!calcAtual) return undefined;
    // Itens válidos, na mesma ordem que foram para o motor.
    const validos = itens.filter((i) => i.ref_id && i.quantity.trim());
    const pos = validos.indexOf(itens[k]);
    return pos >= 0 ? calc?.itens[pos] : undefined;
  };
  const margemPadrao = prm ? fmtNum(prm.margin_pct, 2) : "";
  const vendaRot = calc ? (calc.venda_unidade === "un" ? "unidade" : calc.venda_unidade === "kg" ? "kg" : "litro") : "";

  return (
    <Modal titulo={id ? `Receita · ${f.name || "…"}` : "Nova receita"} onClose={fechar} largura={1080} aoEnviar={salvar}
      rodape={<>
        {id && <button type="button" className="btn perigo" onClick={excluir} disabled={somenteLeitura}><Icone nome="lixo" tam={14} />Excluir</button>}
        {id && <button type="button" className="btn" onClick={duplicar} disabled={somenteLeitura}><Icone nome="copiar" tam={14} />Duplicar</button>}
        <span className="grow" />
        <button type="button" className="btn" onClick={fechar}>Cancelar</button>
        <button type="submit" className="btn primary" disabled={salvando || somenteLeitura}>{salvando ? "Salvando…" : "Salvar receita"}</button>
      </>}>
      {!carregado ? <div className="inicializando" style={{ minHeight: 240 }}><div className="spinner" /></div> : (
        <div className="receita-grade">
          <div className="receita-form">
            <div className="form-grid">
              <Campo rotulo="Nome da receita" largura="1 / 3"><input autoFocus={!id} value={f.name} onChange={(e) => mudar({ name: e.target.value })} placeholder="Ex.: Bolo de chocolate 20cm" /></Campo>
              <Campo rotulo="Rende" dica={produto ? (produto.unit === "kg" ? "Vendido por kg: rendimento em peso." : "Vendido por unidade: quantas peças.") : "Receita base: rendimento em g/ml para usar em outras."}>
                <span className="campo-un">
                  <input inputMode="decimal" value={f.yield_qty} onChange={(e) => mudar({ yield_qty: e.target.value })} />
                  <select value={f.yield_unit} onChange={(e) => mudar({ yield_unit: e.target.value as UnCusto })}>
                    {(["un", "dz", "g", "kg", "ml", "l"] as UnCusto[]).map((u) => <option key={u} value={u}>{NOME_UNIDADE[u]}</option>)}
                  </select>
                </span>
              </Campo>
              <Campo rotulo="Produto do catálogo" largura="1 / -1" dica="Vincule para comparar com o preço atual e aplicar o preço sugerido.">
                <Combo opcoes={opProdutos} valor={f.product_id ?? 0} onChange={(v) => {
                  const p = v ? produtos.find((x) => x.id === v) : null;
                  const muda: Partial<FormReceita> = { product_id: v || null };
                  if (p && !f.name.trim()) muda.name = p.name;
                  if (p?.unit === "kg" && BASE_DE[f.yield_unit] !== "g") muda.yield_unit = "kg";
                  if (p?.unit === "un" && BASE_DE[f.yield_unit] !== "un") muda.yield_unit = "un";
                  mudar(muda);
                }} placeholder="Digite para buscar o produto…" />
              </Campo>
            </div>

            <div className="itens-pedido itens-receita">
              <div className="itens-cab">
                <span className="sect-t">Ingredientes e embalagens</span>
                <button type="button" className="btn mini" onClick={adicionar}><Icone nome="mais" tam={12} />Adicionar item</button>
              </div>
              <div className="item-rec item-rec-cab"><span /><span>Insumo ou receita</span><span className="num">Quantidade</span><span /><span className="num">Custo</span><span /></div>
              {itens.map((i, k) => {
                const c = linhaCalc(k);
                const uns = unidadesItem(i);
                return (
                  <div className={`item-rec${c?.pendencia ? " com-pend" : ""}`} key={i.chave}>
                    <span className="item-n">{k + 1}</span>
                    <Combo opcoes={opcoes} valor={i.ref_id ? (i.tipo === "receita" ? OFFSET + i.ref_id : i.ref_id) : null} onChange={(v) => escolher(i.chave, v)}
                      placeholder="Digite para buscar…" autoFocus={k > 0 && !i.ref_id} />
                    <input className="qtd" inputMode="decimal" value={i.quantity} onChange={(e) => mudarItem(i.chave, { quantity: e.target.value })} aria-label="Quantidade" placeholder="0" />
                    <select className="ctl" value={i.unit} onChange={(e) => mudarItem(i.chave, { unit: e.target.value as UnCusto })} aria-label="Unidade">
                      {!uns.includes(i.unit) && <option value={i.unit}>{NOME_UNIDADE[i.unit]} ⚠</option>}
                      {uns.map((u) => <option key={u} value={u}>{NOME_UNIDADE[u]}</option>)}
                    </select>
                    <span className="num item-custo" title={c?.custo ? `${fmtCusto(c.custo, 10)} = ${fmtNum(c.qtd_base, 6)} ${c.unidade_base} × ${fmtCusto(c.preco_base, 10)}` : c?.pendencia ?? undefined}>
                      {c?.pendencia && !c.custo ? <span className="pend-ic"><Icone nome="alerta" tam={13} /></span>
                        : c?.custo ? <>{fmtCusto(c.custo)}<small className="sutil">{fmtPct(c.participacao_pct, 0)}</small></> : <span className="sutil">—</span>}
                    </span>
                    <button type="button" className="icone-btn" onClick={() => { setItens((l) => (l.length > 1 ? l.filter((x) => x.chave !== i.chave) : [{ ...l[0], ref_id: null, quantity: "" }])); setSujo(true); }} aria-label="Remover item"><Icone nome="lixo" tam={14} /></button>
                    {c?.pendencia && <small className="item-pend">{c.pendencia}</small>}
                  </div>
                );
              })}
            </div>

            <div className="form-grid">
              <Campo rotulo="Perdas no preparo (%)" dica="Sobre os ingredientes: o que fica na tigela, quebra, prova.">
                <input inputMode="decimal" value={f.loss_pct} onChange={(e) => mudar({ loss_pct: e.target.value })} placeholder="0" />
              </Campo>
              <Campo rotulo="Tempo de trabalho (min)" dica={prm && Number(prm.labor_hour) > 0 ? `× ${fmtBRL(Number(prm.labor_hour))}/hora (Parâmetros)` : "Defina o valor da hora em Parâmetros."}>
                <input inputMode="decimal" value={f.labor_minutes} onChange={(e) => mudar({ labor_minutes: e.target.value })} placeholder="0" />
              </Campo>
              <Campo rotulo="Outros custos do lote (R$)" dica="Gás, energia do forno, entrega…">
                <input inputMode="decimal" value={f.extra_cost} onChange={(e) => mudar({ extra_cost: e.target.value })} placeholder="0,00" />
              </Campo>
              <Campo rotulo="Lucro desejado (%)" dica={`Vazio = padrão dos Parâmetros (${margemPadrao}%).`}>
                <input inputMode="decimal" value={f.margin_pct} onChange={(e) => mudar({ margin_pct: e.target.value })} placeholder={margemPadrao} />
              </Campo>
              <Campo rotulo="Observações" largura="2 / -1"><input value={f.notes} onChange={(e) => mudar({ notes: e.target.value })} placeholder="Modo de preparo, forma, temperatura…" /></Campo>
            </div>
          </div>

          <aside className="receita-resumo">
            {erroCalc && <p className="form-erro">{erroCalc}</p>}
            {calc && (
              <>
                <span className="sect-t">Custo do lote</span>
                <dl className="contas">
                  <dt>Ingredientes</dt><dd title={fmtCusto(calc.custo_itens, 10)}>{fmtCusto(calc.custo_itens, 2)}</dd>
                  <dt>Perdas ({fmtPct(calc.loss_pct)})</dt><dd title={fmtCusto(calc.custo_perdas, 10)}>{fmtCusto(calc.custo_perdas, 2)}</dd>
                  <dt>Mão de obra</dt><dd title={fmtCusto(calc.custo_mao_obra, 10)}>{fmtCusto(calc.custo_mao_obra, 2)}</dd>
                  <dt>Outros</dt><dd>{fmtCusto(calc.custo_extra, 2)}</dd>
                  <dt className="total">Total</dt><dd className="total" title={fmtCusto(calc.custo_total, 10)}>{fmtCusto(calc.custo_total, 2)}</dd>
                </dl>
                <div className="custo-un">
                  <span>Custo por {vendaRot}</span>
                  <b title={calc.custo_venda ? fmtCusto(calc.custo_venda, 10) : undefined}>{calc.custo_venda ? fmtCusto(calc.custo_venda) : "—"}</b>
                  {calc.yield_base !== "un" && <small className="sutil">{fmtCusto(calc.custo_base, 6)} por {calc.yield_base}</small>}
                </div>

                {calc.preco?.aviso && <p className="form-erro">{calc.preco.aviso}</p>}
                {calc.preco?.sugerido && (
                  <>
                    <span className="sect-t">Preço sugerido</span>
                    <div className="preco-sug">
                      <b>{fmtBRL(Number(calc.preco.sugerido.preco))}</b>
                      <span className="sutil">por {vendaRot} · lucro {fmtPct(calc.preco.margem_pct)}</span>
                    </div>
                    <BarraPreco d={calc.preco.sugerido} />
                    <p className="nota-mini">Conta exata: {fmtCusto(calc.preco.sugerido.preco_exato, 6)}{prm && prm.rounding !== "0.01" ? `, arredondado para cima em ${fmtBRL(Number(prm.rounding))}` : ""}. Mínimo sem lucro: {fmtCusto(calc.preco.preco_minimo, 2)}.</p>
                    {produto && (
                      <button type="button" className="btn primary largo" disabled={somenteLeitura || Math.abs(produto.price - Number(calc.preco.sugerido.preco)) < 0.005} onClick={() => aplicar(calc.preco!.sugerido!.preco)}>
                        {Math.abs(produto.price - Number(calc.preco.sugerido.preco)) < 0.005 ? "Produto já está com este preço" : `Aplicar ${fmtBRL(Number(calc.preco.sugerido.preco))} ao produto`}
                      </button>
                    )}
                  </>
                )}
                {calc.preco?.atual && (
                  <>
                    <span className="sect-t">Preço atual do produto</span>
                    <div className="preco-sug pequeno">
                      <b>{fmtBRL(Number(calc.preco.atual.preco))}</b>
                      <span className={n(calc.preco.atual.margem_real_pct) < n(calc.preco.margem_pct) - 0.05 ? "neg" : "pos"}>lucro {fmtPct(calc.preco.atual.margem_real_pct)} · {fmtCusto(calc.preco.atual.lucro, 2)}</span>
                    </div>
                    <BarraPreco d={calc.preco.atual} />
                  </>
                )}
                {calc.custo_venda && (
                  <>
                    <span className="sect-t">Testar um preço</span>
                    <input className="ctl teste-preco" inputMode="decimal" value={teste} onChange={(e) => setTeste(e.target.value)} placeholder="R$ 0,00" />
                    {calc.preco?.teste && (
                      <>
                        <div className="preco-sug pequeno">
                          <span className={n(calc.preco.teste.margem_real_pct) < n(calc.preco.margem_pct) - 0.05 ? "neg" : "pos"}>lucro {fmtPct(calc.preco.teste.margem_real_pct)} · {fmtCusto(calc.preco.teste.lucro, 2)} por {vendaRot}</span>
                        </div>
                        {produto && <button type="button" className="btn largo" disabled={somenteLeitura} onClick={() => aplicar(calc.preco!.teste!.preco)}>Aplicar {fmtBRL(Number(calc.preco.teste.preco))} ao produto</button>}
                      </>
                    )}
                  </>
                )}
                {calc.pendencias.length > 0 && (
                  <div className="pendencias">
                    <b><Icone nome="alerta" tam={13} /> Custo incompleto</b>
                    <ul>{calc.pendencias.map((p, k) => <li key={k}>{p}</li>)}</ul>
                  </div>
                )}
              </>
            )}
          </aside>
        </div>
      )}
      {erro && <p className="form-erro" role="alert">{erro}</p>}
    </Modal>
  );
}

/** Para onde vai cada real do preço: custo, despesas fixas, impostos, taxas e lucro. */
function BarraPreco({ d }: { d: NonNullable<NonNullable<Receita["preco"]>["sugerido"]> }) {
  const preco = Number(d.preco) || 1;
  const partes: [string, string, string][] = [
    ["Custo", d.custo, "var(--text-3)"], ["Despesas fixas", d.despesas_fixas, "var(--info)"], ["Impostos", d.impostos, "var(--warn)"],
    ["Taxas", d.taxas, "var(--violet)"], ["Lucro", d.lucro, Number(d.lucro) >= 0 ? "var(--ok)" : "var(--bad)"],
  ];
  return (
    <div className="barra-preco">
      <div className="bp-barra">
        {partes.map(([r, v, cor]) => Number(v) > 0 && <i key={r} style={{ width: `${(Number(v) / preco) * 100}%`, background: cor }} title={`${r}: ${fmtCusto(v, 2)}`} />)}
      </div>
      <dl className="contas compacto">
        {partes.filter(([r, v]) => Number(v) !== 0 || r === "Custo" || r === "Lucro").map(([r, v, cor]) => (
          <div key={r} style={{ display: "contents" }}>
            <dt><span className="bp-cor" style={{ background: cor }} />{r}</dt>
            <dd className={r === "Lucro" && Number(v) < 0 ? "neg" : undefined}>{fmtCusto(v, 2)} <small className="sutil">{fmtPct((Number(v) / preco) * 100)}</small></dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

// ================================================================ parâmetros

function AbaParametros() {
  const { toast, somenteLeitura } = useApp();
  const { dados, recarregar } = useCarregar(() => api.get<ParametrosCusto>("/custos/parametros"), []);
  const [f, setF] = useState<ParametrosCusto | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    if (dados) setF({ ...dados, labor_hour: paraCampo(dados.labor_hour), fixed_pct: paraCampo(dados.fixed_pct), tax_pct: paraCampo(dados.tax_pct), fee_pct: paraCampo(dados.fee_pct), margin_pct: paraCampo(dados.margin_pct) });
  }, [dados]);
  if (!f) return <div className="inicializando"><div className="spinner" /></div>;

  const soma = ["fixed_pct", "tax_pct", "fee_pct", "margin_pct"].reduce((s, k) => s + (lerNum(String(f[k as keyof ParametrosCusto] || "0")) || 0), 0);
  const exemplo = soma < 100 ? 10 / (1 - soma / 100) : NaN;

  const salvar = async () => {
    setErro("");
    try { await api.put("/custos/parametros", f); toast("Parâmetros salvos. Os custos e preços sugeridos já usam os novos valores."); recarregar(true); }
    catch (e) { setErro((e as Error).message); }
  };

  return (
    <div className="parametros">
      <form className="card pad" onSubmit={(e) => { e.preventDefault(); salvar(); }}>
        <span className="sect-t">Custo dos insumos</span>
        <div className="form-grid">
          <Campo rotulo="Usar o preço" largura="1 / 3">
            <div className="seg">
              <button type="button" aria-pressed={f.cost_basis === "ultima"} onClick={() => setF({ ...f, cost_basis: "ultima" })}>Da última compra</button>
              <button type="button" aria-pressed={f.cost_basis === "media"} onClick={() => setF({ ...f, cost_basis: "media" })}>Média ponderada</button>
            </div>
          </Campo>
          {f.cost_basis === "media" && (
            <Campo rotulo="Período da média (dias)" dica="Compras dentro do período, pesadas pela quantidade.">
              <input inputMode="numeric" value={String(f.avg_days)} onChange={(e) => setF({ ...f, avg_days: Number(e.target.value.replace(/\D/g, "")) || 0 })} />
            </Campo>
          )}
          <Campo rotulo="Valor da sua hora de trabalho (R$)" largura="1 / 3" dica="Quanto você quer ganhar por hora. Entra como mão de obra pelo tempo de cada receita.">
            <input inputMode="decimal" value={f.labor_hour} onChange={(e) => setF({ ...f, labor_hour: e.target.value })} placeholder="0,00" />
          </Campo>
        </div>

        <span className="sect-t pad-top">Formação do preço (% sobre o preço de venda)</span>
        <div className="form-grid">
          <Campo rotulo="Despesas fixas (%)" dica="Aluguel, luz, internet, MEI… ÷ faturamento do mês.">
            <input inputMode="decimal" value={f.fixed_pct} onChange={(e) => setF({ ...f, fixed_pct: e.target.value })} placeholder="0" />
          </Campo>
          <Campo rotulo="Impostos (%)" dica="Ex.: Simples Nacional. MEI paga fixo: use 0 e inclua nas despesas fixas.">
            <input inputMode="decimal" value={f.tax_pct} onChange={(e) => setF({ ...f, tax_pct: e.target.value })} placeholder="0" />
          </Campo>
          <Campo rotulo="Taxas de venda (%)" dica="Maquininha, iFood, comissão…">
            <input inputMode="decimal" value={f.fee_pct} onChange={(e) => setF({ ...f, fee_pct: e.target.value })} placeholder="0" />
          </Campo>
          <Campo rotulo="Lucro desejado (%)" dica="Padrão das receitas (cada uma pode ter o seu).">
            <input inputMode="decimal" value={f.margin_pct} onChange={(e) => setF({ ...f, margin_pct: e.target.value })} placeholder="30" />
          </Campo>
          <Campo rotulo="Arredondar preço para cima" largura="2 / -1">
            <select value={f.rounding} onChange={(e) => setF({ ...f, rounding: e.target.value })}>
              <option value="0.01">Centavo (R$ 0,01) — exato</option>
              <option value="0.05">R$ 0,05</option>
              <option value="0.10">R$ 0,10</option>
              <option value="0.50">R$ 0,50</option>
              <option value="1.00">R$ 1,00</option>
            </select>
          </Campo>
        </div>
        {erro && <p className="form-erro" role="alert">{erro}</p>}
        <div className="acoes-form"><button className="btn primary" disabled={somenteLeitura}>Salvar parâmetros</button></div>
      </form>

      <div className="card pad explica">
        <span className="sect-t">Como o preço é calculado</span>
        <p><b>Custo do insumo</b> = valor pago ÷ quantidade comprada ÷ aproveitamento. Ex.: R$ 4,99 ÷ 395 g = R$ 0,0126329… por grama, usado com todas as casas.</p>
        <p><b>Custo do lote</b> = ingredientes + perdas + mão de obra + outros custos. <b>Custo por venda</b> = lote ÷ rendimento.</p>
        <p><b>Preço</b> = custo ÷ (1 − despesas − impostos − taxas − lucro). Assim o lucro é {fmtPct(lerNum(f.margin_pct || "0"))} do <i>preço</i>, depois de pagar tudo.</p>
        <div className={`exemplo${soma >= 100 ? " ruim" : ""}`}>
          {soma >= 100 ? <>Os percentuais somam {fmtPct(soma)}: precisa ser menos de 100%.</>
            : <>Com estes valores ({fmtPct(soma)} do preço), um produto que custa <b>R$ 10,00</b> sai por <b>{fmtCusto(exemplo, 2)}</b> (markup {fmtNum(exemplo / 10, 2)}×).</>}
        </div>
        <p className="sutil">Ninguém mais vê esta tela: custos, margens e lucro aparecem só para administradores.</p>
      </div>
    </div>
  );
}

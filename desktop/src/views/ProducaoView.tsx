import { useEffect, useMemo, useState } from "react";
import { abrirUrl, api } from "../api";
import { useApp } from "../contexto";
import type { EstoqueProducao, ItemProducao, Produto } from "../types";
import { fmtData, fmtInt, fmtTamanho, isoLocal } from "../format";
import { Cabecalho, Campo, CampoBusca, Modal, useCarregar, useDebounce, Vazio } from "../components/ui";
import { Combo } from "../components/Combo";
import { Icone } from "../components/Icone";

function NovoItem({ onClose, onSalvo }: { onClose: () => void; onSalvo: (msg: string) => void }) {
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [produto, setProduto] = useState<number | null>(null);
  const [qtd, setQtd] = useState(1);
  const [tam, setTam] = useState("");
  const [obs, setObs] = useState("");
  const [erro, setErro] = useState("");
  useEffect(() => { api.get<{ produtos: Produto[] }>("/produtos").then((r) => setProdutos(r.produtos)).catch(() => {}); }, []);
  const p = produtos.find((x) => x.id === produto);
  const tamanhos = p?.size ? p.size.split(",").map((t) => t.trim()).filter(Boolean) : [];
  useEffect(() => { setTam(tamanhos[0] ?? ""); }, [produto]); // eslint-disable-line react-hooks/exhaustive-deps
  const opcoes = useMemo(() => produtos.map((x) => ({ id: x.id, rotulo: x.name, detalhe: `${x.stock} em estoque` })), [produtos]);

  const salvar = async () => {
    if (!produto) { setErro("Escolha o produto."); return; }
    try {
      await api.post("/producao", { product_id: produto, quantity: qtd, size: tam, notes: obs });
      onSalvo(`Item adicionado: ${p?.name ?? ""}`);
    } catch (e) { setErro((e as Error).message); }
  };
  return (
    <Modal titulo="Adicionar à lista de produção" onClose={onClose} largura={480} aoEnviar={salvar}
      rodape={<><button type="button" className="btn" onClick={onClose}>Cancelar</button><button className="btn primary">Adicionar</button></>}>
      <div className="form-grid">
        <Campo rotulo="Produto" largura="1 / -1"><Combo opcoes={opcoes} valor={produto} onChange={setProduto} placeholder="Digite para buscar…" autoFocus /></Campo>
        <Campo rotulo="Quantidade"><input type="number" min={1} max={1000000} value={qtd} onChange={(e) => setQtd(Number(e.target.value))} /></Campo>
        <Campo rotulo="Tamanho">
          <input list="tam-op" value={tam} onChange={(e) => setTam(e.target.value)} placeholder="Opcional" />
          <datalist id="tam-op">{tamanhos.map((t) => <option key={t} value={t}>{fmtTamanho(t)}</option>)}</datalist>
        </Campo>
        <Campo rotulo="Observação" largura="1 / -1"><input value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Opcional" /></Campo>
      </div>
      <p className="nota-rodape">Adicionar não mexe no estoque. A cozinha marca "Produção feita" no painel e as quantidades entram no estoque.</p>
      {erro && <p className="form-erro">{erro}</p>}
    </Modal>
  );
}

/** Célula editável: salva ao sair do campo ou com Enter; Esc desfaz. */
function Editavel({ valor, tipo = "text", onSalvar, exibir, placeholder }: {
  valor: string; tipo?: "text" | "number"; onSalvar: (v: string) => void; exibir?: (v: string) => string; placeholder?: string;
}) {
  const [ed, setEd] = useState<string | null>(null);
  if (ed === null) {
    return <button className="editavel" onClick={() => setEd(valor)} title="Clique para editar">{(exibir ? exibir(valor) : valor) || <span className="sutil">{placeholder ?? "—"}</span>}</button>;
  }
  const fim = (salvar: boolean) => { if (salvar && ed !== valor) onSalvar(ed); setEd(null); };
  return (
    <input className="editando-cel" autoFocus type={tipo} min={tipo === "number" ? 1 : undefined} value={ed}
      onChange={(e) => setEd(e.target.value)} onBlur={() => fim(true)}
      onKeyDown={(e) => { if (e.key === "Enter") fim(true); if (e.key === "Escape") { e.stopPropagation(); fim(false); } }} />
  );
}

export function ProducaoView() {
  const { toast, confirmar, somenteLeitura } = useApp();
  const [dia, setDia] = useState(isoLocal());
  const [q, setQ] = useState("");
  const qd = useDebounce(q);
  const [novo, setNovo] = useState(false);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const { dados, recarregar } = useCarregar(() => api.get<{ itens: ItemProducao[]; estoque: EstoqueProducao[] }>("/producao", { data: dia, q: qd }), [dia, qd], 3000);
  const itens = dados?.itens ?? [];
  const estoque = dados?.estoque ?? [];
  const totalUn = itens.reduce((s, i) => s + i.quantity, 0);
  const encomendas = estoque.filter((e) => e.encomendas > 0);

  const editar = async (i: ItemProducao, campo: "quantity" | "size" | "notes", v: string) => {
    try {
      const corpo = campo === "quantity" ? { quantity: Number(v) } : { [campo]: v };
      const r = await api.put<{ estoque: number }>(`/producao/${i.id}`, corpo);
      toast(campo === "quantity" && r.estoque ? `Quantidade atualizada (estoque ${r.estoque > 0 ? "+" : ""}${r.estoque}).` : "Item atualizado.");
      recarregar(true);
    } catch (e) { toast((e as Error).message, true); }
  };

  const importar = async (confirmar_ = false) => {
    try {
      const r = await api.post<{ precisa_confirmar?: boolean; itens_atuais?: number; pedidos?: number; importados?: number }>("/producao/importar", { data: dia, confirmar: confirmar_ });
      if (r.precisa_confirmar) {
        const ok = await confirmar({
          titulo: "Substituir a lista de produção?", ok: "Substituir", perigo: true,
          texto: <>A lista atual tem <b>{r.itens_atuais}</b> item(ns), incluindo os adicionados à mão. Ela será trocada pelos <b>{r.pedidos}</b> pedido(s) com entrega em {fmtData(dia)}.</>,
        });
        if (ok) await importar(true);
        return;
      }
      toast(`${r.importados} item(ns) importado(s) dos pedidos de ${fmtData(dia)}.`);
      recarregar(true);
    } catch (e) { toast((e as Error).message, true); }
  };

  const remover = async (ids: number[]) => {
    try {
      await api.post("/producao/remover", { ids });
      toast(ids.length === 1 ? "Item removido." : `${ids.length} itens removidos.`);
      setSel(new Set()); recarregar(true);
    } catch (e) { toast((e as Error).message, true); }
  };

  const limpar = async () => {
    if (!itens.length) { toast("A lista já está vazia."); return; }
    const ok = await confirmar({ titulo: "Limpar lista de produção", perigo: true, ok: "Limpar", texto: `Remover todos os ${itens.length} item(ns) da lista? O estoque não muda.` });
    if (!ok) return;
    try { await api.post("/producao/limpar"); toast("Lista de produção limpa."); recarregar(true); }
    catch (e) { toast((e as Error).message, true); }
  };

  const abrirPainel = async () => {
    try {
      const p = await api.get<{ url: string; local: string; pin: string }>("/painel-cozinha");
      await navigator.clipboard.writeText(`${p.url} (PIN: ${p.pin})`).catch(() => {});
      toast(`Painel da cozinha: ${p.url} · PIN ${p.pin} (copiado)`);
      abrirUrl(p.local).catch(() => {});
    } catch (e) { toast((e as Error).message, true); }
  };

  return (
    <section className="view">
      <Cabecalho titulo="Produção" sub={`${itens.length} item(ns) na lista · ${fmtInt(totalUn)} unidades · a cozinha vê esta lista no painel`}>
        <button className="btn" onClick={abrirPainel}><Icone nome="celular" tam={14} />Painel da cozinha</button>
        <button className="btn" onClick={() => importar()} disabled={somenteLeitura} title={somenteLeitura ? "Licença bloqueada: modo somente leitura" : undefined}><Icone nome="download" tam={14} />Importar pedidos do dia</button>
        <button className="btn primary" onClick={() => setNovo(true)} disabled={somenteLeitura} title={somenteLeitura ? "Licença bloqueada: modo somente leitura" : undefined}><Icone nome="mais" tam={14} />Adicionar item</button>
      </Cabecalho>
      <div className="filters">
        <div className="periodo"><label>Dia dos pedidos <input type="date" value={dia} onChange={(e) => setDia(e.target.value || isoLocal())} /></label></div>
        <span className="sutil">Usado para importar e para a coluna "Encomendas".</span>
        <span className="grow" />
        {sel.size > 0 && <button className="btn perigo" onClick={() => remover([...sel])}><Icone nome="lixo" tam={14} />Remover {sel.size}</button>}
        <button className="btn" onClick={limpar} disabled={somenteLeitura}>Limpar lista</button>
      </div>
      <div className="producao">
        <div className="card prod-lista">
          <div className="card-cab"><b>Lista de produção</b><span className="sutil">clique num valor para editar</span></div>
          {itens.length === 0 ? (
            <Vazio icone="producao" titulo="Lista vazia" texto="Importe os pedidos do dia ou adicione itens à mão.">
              <button className="btn" onClick={() => importar()}>Importar pedidos de {fmtData(dia)}</button>
            </Vazio>
          ) : (
            <div className="prod-itens">
              {itens.map((i) => (
                <div key={i.id} className="prod-item" data-marcada={sel.has(i.id)}>
                  <label className="marca"><input type="checkbox" checked={sel.has(i.id)} onChange={(e) => setSel((s) => { const n = new Set(s); if (e.target.checked) n.add(i.id); else n.delete(i.id); return n; })} /></label>
                  <div className="pi-qtd"><Editavel valor={String(i.quantity)} tipo="number" onSalvar={(v) => editar(i, "quantity", v)} /></div>
                  <div className="pi-info">
                    <b>{i.produto}</b>
                    <div className="pi-sub">
                      <Editavel valor={i.size ?? ""} exibir={fmtTamanho} placeholder="sem tamanho" onSalvar={(v) => editar(i, "size", v)} />
                      <span className="sep">·</span>
                      <Editavel valor={i.notes ?? ""} placeholder="sem observação" onSalvar={(v) => editar(i, "notes", v)} />
                    </div>
                  </div>
                  <button className="icone-btn perigo" title="Remover" onClick={() => remover([i.id])}><Icone nome="fechar" tam={14} /></button>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="card prod-estoque">
          <div className="card-cab"><b>Estoque atual</b><span className="sutil">{encomendas.length} produto(s) com encomenda em {fmtData(dia)}</span></div>
          <div className="pad-h"><CampoBusca valor={q} onChange={setQ} placeholder="Produto" /></div>
          <div className="estoque-lista">
            <div className="el-cab"><span>Produto</span><span className="num">Estoque</span><span className="num">Encomendas</span></div>
            {estoque.map((e) => (
              <div key={e.id} className={`el-linha${e.encomendas > e.stock ? " falta" : ""}`}>
                <span title={e.name}>{e.name}</span>
                <span className="num"><span className={`estq${e.stock <= 0 ? " esgotado" : e.stock < 5 ? " baixo" : ""}`}>{e.stock <= 0 ? `Esgotado${e.stock < 0 ? ` (${e.stock})` : ""}` : e.stock}</span></span>
                <span className="num">{e.encomendas ? <b>{e.encomendas}</b> : <span className="sutil">—</span>}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      {novo && <NovoItem onClose={() => setNovo(false)} onSalvo={(m) => { setNovo(false); toast(m); recarregar(true); }} />}
    </section>
  );
}

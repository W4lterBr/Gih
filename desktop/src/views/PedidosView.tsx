import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp } from "../contexto";
import type { Etiqueta, PedidoDetalhe, PedidoLinha } from "../types";
import { fmtData, fmtEntrega, fmtInt, fmtQtd, fmtTamanho, isoLocal, somarDias } from "../format";
import { BarraSelecao, Cabecalho, CampoBusca, Etiqueta as Chip, Kpi, Situacao, Status, Tabela, useCarregar, useDebounce, Vazio, type Coluna } from "../components/ui";
import { Icone } from "../components/Icone";
import { PedidoDialog, STATUS } from "./PedidoDialog";
import { EtiquetasDialog, LogsDialog, RelatorioPedidosDialog } from "./Dialogos";

type Periodo = "hoje" | "amanha" | "semana" | "todos" | "livre";

function intervalo(p: Periodo, de: string, ate: string): [string, string] {
  const h = isoLocal();
  if (p === "hoje") return [h, h];
  if (p === "amanha") return [somarDias(h, 1), somarDias(h, 1)];
  if (p === "semana") return [h, somarDias(h, 6)];
  if (p === "todos") return ["", ""];
  return [de, ate];
}

export function PedidosView({ novoPedido, onNovoConsumido }: { novoPedido: boolean; onNovoConsumido: () => void }) {
  const { toast, confirmar, admin, dadosMudaram, somenteLeitura, motivoBloqueio } = useApp();
  const [periodo, setPeriodo] = useState<Periodo>("hoje");
  const [de, setDe] = useState(isoLocal());
  const [ate, setAte] = useState(isoLocal());
  const [q, setQ] = useState("");
  const qd = useDebounce(q, 150);
  const [fStatus, setFStatus] = useState("");
  const [fEtiqueta, setFEtiqueta] = useState("");
  // "" = abertos e entregues (cancelados escondidos); ou uma situação; ou "todas".
  const [fSituacao, setFSituacao] = useState("");
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [aberto, setAberto] = useState<PedidoLinha | null>(null);
  const [dialogo, setDialogo] = useState<{ tipo: "novo" } | { tipo: "editar"; pedido: PedidoDetalhe } | { tipo: "etiquetas" } | { tipo: "relatorio" } | { tipo: "logs"; id: number } | null>(null);
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([]);

  const [ini, fim] = intervalo(periodo, de, ate);
  const { dados, carregando, recarregar } = useCarregar(
    () => api.get<{ pedidos: PedidoLinha[] }>("/pedidos", { de: ini, ate: fim, q: qd, situacao: fSituacao }),
    [ini, fim, qd, fSituacao], 15000,
  );
  useEffect(() => { api.get<{ etiquetas: Etiqueta[] }>("/etiquetas").then((r) => setEtiquetas(r.etiquetas)).catch(() => {}); }, [dialogo]);
  useEffect(() => { if (novoPedido) { setDialogo({ tipo: "novo" }); onNovoConsumido(); } }, [novoPedido, onNovoConsumido]);

  const linhas = useMemo(() => (dados?.pedidos ?? []).filter((p) => (!fStatus || p.status === fStatus) && (!fEtiqueta || p.label === fEtiqueta)), [dados, fStatus, fEtiqueta]);
  const porId = useMemo(() => new Map(linhas.map((l) => [l.id, l])), [linhas]);
  const marcadas = [...sel].map((id) => porId.get(id)).filter(Boolean) as PedidoLinha[];
  // Painel aberto acompanha a versão nova da linha depois de recarregar.
  useEffect(() => { setAberto((a) => (a ? porId.get(a.id) ?? null : null)); }, [porId]);

  const kpis = useMemo(() => {
    let n = 0, itens = 0, aguardando = 0, pagos = 0;
    for (const l of linhas) {
      if (l.situacao === "cancelado") continue;
      n++;
      itens += l.unit === "un" ? l.quantity : l.itens;
      if (l.status === "Pago") pagos++;
      else if (l.status === "Aguardando Pagamento" || l.status === "Pagamento na Retirada") aguardando++;
    }
    return { n, itens, aguardando, pagos };
  }, [linhas]);

  const depoisDeSalvar = (msg: string) => { setDialogo(null); toast(msg); recarregar(true); dadosMudaram(); };

  const editar = async (l: PedidoLinha) => {
    try {
      const r = await api.get<{ pedido: PedidoDetalhe }>(`/pedidos/${l.id}`);
      setDialogo({ tipo: "editar", pedido: r.pedido });
    } catch (e) { toast((e as Error).message, true); }
  };

  const excluir = async (alvo: PedidoLinha[]) => {
    if (!alvo.length) return;
    const ids = alvo.flatMap((l) => l.ids);
    const { itens, devolve } = await api.post<{ itens: number; devolve: number }>("/pedidos/excluir/contar", { ids });
    const ok = await confirmar({
      titulo: itens === 1 ? "Excluir pedido" : `Excluir ${itens} pedidos`, perigo: true, ok: "Excluir",
      texto: <>{alvo.length === 1 ? <>O pedido de <b>{alvo[0].cliente}</b> será excluído.</> : <>{alvo.length} linhas selecionadas ({itens} itens) serão excluídas.</>}<br />
        {devolve ? <>{devolve} unidade(s) reservada(s) voltam ao estoque.</> : <>Nada volta ao estoque.</>}{" "}
        Pedidos entregues ou com a data já passada não devolvem estoque. Se o pedido não vai mais acontecer, prefira <b>Cancelar</b>.</>,
    });
    if (!ok) return;
    try {
      const r = await api.post<{ excluidos: number }>("/pedidos/excluir", { ids });
      toast(r.excluidos === 1 ? "Pedido excluído." : `${r.excluidos} pedidos excluídos.`);
      setSel(new Set()); setAberto(null); recarregar(true); dadosMudaram();
    } catch (e) { toast((e as Error).message, true); }
  };

  const cancelar = async (alvo: PedidoLinha[]) => {
    const ok = await confirmar({
      titulo: alvo.length === 1 ? "Cancelar pedido" : `Cancelar ${alvo.length} pedidos`, perigo: true, ok: "Cancelar pedido", cancelar: "Voltar",
      texto: <>O pedido continua na lista (filtro "Cancelados") e o estoque já reservado volta para o produto. Dá para reabrir depois.</>,
    });
    if (ok) alterar(alvo, { situacao: "cancelado" }, alvo.length === 1 ? "Pedido cancelado." : `${alvo.length} pedidos cancelados.`);
  };

  const alterar = async (alvo: PedidoLinha[], campos: Record<string, string>, msg: string) => {
    try {
      await api.put("/pedidos/lote", { ids: alvo.flatMap((l) => l.ids), ...campos });
      toast(msg); recarregar(true); dadosMudaram();
    } catch (e) { toast((e as Error).message, true); }
  };

  // Atalhos da tela.
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (dialogo || (e.target as HTMLElement)?.closest?.("input, textarea, select")) return;
      if (e.key === "Delete" && marcadas.length) { e.preventDefault(); excluir(marcadas); }
      if (e.key === "Enter" && aberto) { e.preventDefault(); editar(aberto); }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });

  const colunas: Coluna<PedidoLinha>[] = [
    { id: "entrega", titulo: "Entrega", largura: "104px", ordenar: (l) => l.delivery_date,
      render: (l) => <span className={`entrega${l.delivery_date === isoLocal() ? " hoje" : l.delivery_date < isoLocal() ? " passou" : ""}`}>{fmtEntrega(l.delivery_date)}</span>,
      titleAttr: (l) => fmtData(l.delivery_date) },
    { id: "cliente", titulo: "Cliente", largura: "minmax(150px,1.3fr)", ordenar: (l) => l.cliente,
      render: (l) => <span className="who"><b>{l.cliente}</b>{l.telefone && <span className="sutil-sans">{l.telefone}</span>}</span> },
    { id: "produto", titulo: "Produtos", largura: "minmax(180px,2fr)", ordenar: (l) => l.produto, titleAttr: (l) => l.produto,
      render: (l) => <>{l.lote && <span className="lote-tag" title="Pedido com vários produtos">{l.itens}</span>}{l.produto}{l.produto_size && <span className="sutil"> · {fmtTamanho(l.produto_size)}</span>}</> },
    { id: "qtd", titulo: "Qtd", largura: "72px", num: true, ordenar: (l) => l.quantity,
      render: (l) => (l.unit === "misto" ? <span className="sutil" title="Lote com produtos em unidade e em kg">{l.itens} itens</span> : fmtQtd(l.quantity, l.unit)) },
    { id: "status", titulo: "Pagamento", largura: "236px", ordenar: (l) => l.status, render: (l) => <span className="pills"><Status valor={l.status} /><Situacao valor={l.situacao} /></span> },
    { id: "etiqueta", titulo: "Etiqueta", largura: "120px", ordenar: (l) => l.label, render: (l) => <Chip nome={l.label} cor={l.label_color} /> },
    { id: "obs", titulo: "Observações", largura: "minmax(120px,1.4fr)", render: (l) => <span className="sutil">{l.obs}</span>, titleAttr: (l) => l.obs },
  ];

  return (
    <section className="view com-drawer">
      <Cabecalho titulo="Pedidos" sub={periodo === "todos" ? "Todos os pedidos" : ini === fim ? `Entrega em ${fmtData(ini)}` : `Entrega de ${fmtData(ini)} a ${fmtData(fim)}`}>
        <button className="btn" onClick={() => setDialogo({ tipo: "etiquetas" })} disabled={somenteLeitura} title={somenteLeitura ? motivoBloqueio : undefined}><Icone nome="etiqueta" tam={14} />Etiquetas</button>
        <button className="btn" onClick={() => setDialogo({ tipo: "relatorio" })}><Icone nome="download" tam={14} />Relatório</button>
        <button className="btn primary" onClick={() => setDialogo({ tipo: "novo" })} disabled={somenteLeitura} title={somenteLeitura ? motivoBloqueio : "Novo pedido (Ctrl+N)"}><Icone nome="mais" tam={14} />Novo pedido</button>
      </Cabecalho>

      <div className="kpis kpis-3">
        <Kpi rotulo="Pedidos no período" valor={fmtInt(kpis.n)} sub={`${fmtInt(kpis.itens)} itens (sem cancelados)`} />
        <Kpi rotulo="A receber" valor={fmtInt(kpis.aguardando)} sub="aguardando ou na retirada" tom={kpis.aguardando ? "attn" : undefined} onClick={() => setFStatus(fStatus ? "" : "Aguardando Pagamento")} />
        <Kpi rotulo="Pagos" valor={fmtInt(kpis.pagos)} sub="pagamento confirmado" tom="ok" onClick={() => setFStatus(fStatus === "Pago" ? "" : "Pago")} />
      </div>

      <div className="filters">
        <CampoBusca valor={q} onChange={setQ} placeholder="Cliente, produto, etiqueta ou observação" />
        <div className="seg" role="group" aria-label="Período">
          {([["hoje", "Hoje"], ["amanha", "Amanhã"], ["semana", "7 dias"], ["todos", "Todos"]] as [Periodo, string][]).map(([p, r]) => (
            <button key={p} aria-pressed={periodo === p} onClick={() => setPeriodo(p)}>{r}</button>
          ))}
        </div>
        <div className="periodo" role="group" aria-label="Período personalizado">
          <label>De <input type="date" value={ini} onChange={(e) => { setDe(e.target.value); setAte(fim || e.target.value); setPeriodo("livre"); }} /></label>
          <label>Até <input type="date" value={fim} min={ini || undefined} onChange={(e) => { setAte(e.target.value); setDe(ini || e.target.value); setPeriodo("livre"); }} /></label>
        </div>
        <select className="chip" value={fStatus} onChange={(e) => setFStatus(e.target.value)} aria-label="Pagamento">
          <option value="">Todos os pagamentos</option>
          {STATUS.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select className="chip" value={fSituacao} onChange={(e) => { setFSituacao(e.target.value); setSel(new Set()); }} aria-label="Situação">
          <option value="">A entregar e entregues</option>
          <option value="aberto">Só a entregar</option>
          <option value="entregue">Entregues</option>
          <option value="cancelado">Cancelados</option>
          <option value="todas">Todos (com cancelados)</option>
        </select>
        <select className="chip" value={fEtiqueta} onChange={(e) => setFEtiqueta(e.target.value)} aria-label="Etiqueta">
          <option value="">Todas as etiquetas</option>
          {etiquetas.map((e) => <option key={e.id}>{e.name}</option>)}
        </select>
      </div>

      <BarraSelecao n={marcadas.length} rotulo={["pedido marcado", "pedidos marcados"]} onLimpar={() => setSel(new Set())}>
        <select className="chip" value="" onChange={(e) => e.target.value && alterar(marcadas, { status: e.target.value }, "Pagamento atualizado.")} aria-label="Mudar pagamento">
          <option value="">Mudar pagamento…</option>
          {STATUS.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select className="chip" value="" onChange={(e) => e.target.value && alterar(marcadas, { label: e.target.value }, "Etiqueta atualizada.")} aria-label="Mudar etiqueta">
          <option value="">Mudar etiqueta…</option>
          {etiquetas.map((e) => <option key={e.id}>{e.name}</option>)}
        </select>
        <button className="btn" onClick={() => alterar(marcadas, { situacao: "entregue" }, "Marcado como entregue.")} disabled={somenteLeitura}>Marcar entregue</button>
        <button className="btn" onClick={() => cancelar(marcadas)} disabled={somenteLeitura}>Cancelar</button>
        <button className="btn perigo" onClick={() => excluir(marcadas)}><Icone nome="lixo" tam={14} />Excluir</button>
      </BarraSelecao>

      {!dados && carregando ? <div className="loading">Carregando pedidos…</div> : (
        <Tabela linhas={linhas} colunas={colunas} chave={(l) => l.id} selecionadas={sel}
          onSelecionar={(s) => { setSel(s); if (s.size === 1) setAberto(porId.get([...s][0]) ?? null); }}
          onAbrir={somenteLeitura ? undefined : editar} ativa={aberto?.id}
          linhaClasse={(l) => (l.situacao === "cancelado" ? "linha-cancelada" : l.situacao === "entregue" ? "linha-entregue" : undefined)}
          vazio={<Vazio icone="pedidos" titulo="Nenhum pedido neste período" texto={q ? "Tente outra busca ou outro período." : "Crie um pedido ou mude o período."}>
            <button className="btn primary" onClick={() => setDialogo({ tipo: "novo" })} disabled={somenteLeitura}><Icone nome="mais" tam={14} />Novo pedido</button>
          </Vazio>} />
      )}

      <PainelPedido linha={aberto} admin={admin} somenteLeitura={somenteLeitura} etiquetas={etiquetas} onClose={() => { setAberto(null); setSel(new Set()); }}
        onEditar={editar} onExcluir={(l) => excluir([l])} onLogs={(l) => setDialogo({ tipo: "logs", id: l.id })}
        onAlterar={(l, campos, msg) => alterar([l], campos, msg)} onCancelar={(l) => cancelar([l])} />

      {dialogo?.tipo === "novo" && <PedidoDialog onClose={() => setDialogo(null)} onSalvo={depoisDeSalvar} />}
      {dialogo?.tipo === "editar" && <PedidoDialog editar={dialogo.pedido} onClose={() => setDialogo(null)} onSalvo={depoisDeSalvar} />}
      {dialogo?.tipo === "etiquetas" && <EtiquetasDialog onClose={() => { setDialogo(null); recarregar(true); }} />}
      {dialogo?.tipo === "relatorio" && <RelatorioPedidosDialog de={ini} ate={fim} onClose={() => setDialogo(null)} />}
      {dialogo?.tipo === "logs" && <LogsDialog entidade="order" id={dialogo.id} titulo={`pedido #${dialogo.id}`} onClose={() => setDialogo(null)} />}
    </section>
  );
}

function PainelPedido({ linha, admin, somenteLeitura, etiquetas, onClose, onEditar, onExcluir, onLogs, onAlterar, onCancelar }: {
  linha: PedidoLinha | null; admin: boolean; somenteLeitura: boolean; etiquetas: Etiqueta[];
  onClose: () => void; onEditar: (l: PedidoLinha) => void; onExcluir: (l: PedidoLinha) => void; onLogs: (l: PedidoLinha) => void;
  onAlterar: (l: PedidoLinha, campos: Record<string, string>, msg: string) => void;
  onCancelar: (l: PedidoLinha) => void;
}) {
  const [detalhe, setDetalhe] = useState<PedidoDetalhe | null>(null);
  useEffect(() => {
    setDetalhe(null);
    if (linha) api.get<{ pedido: PedidoDetalhe }>(`/pedidos/${linha.id}`).then((r) => setDetalhe(r.pedido)).catch(() => {});
  }, [linha]);
  const l = linha;
  return (
    <aside className={`drawer${l ? " open" : ""}`} aria-hidden={!l} aria-label="Detalhes do pedido">
      {l && (
        <>
          <div className="dr-head">
            <div className="top">
              <span className="sutil">Pedido #{l.id}</span>
              <Chip nome={l.label} cor={l.label_color} />
              <button className="x" aria-label="Fechar painel" onClick={onClose}><Icone nome="fechar" tam={12} /></button>
            </div>
            <h2>{l.cliente}</h2>
            <div style={{ color: "var(--text-2)" }}>Entrega {fmtEntrega(l.delivery_date).toLowerCase()} · {fmtData(l.delivery_date)}{l.telefone ? ` · ${l.telefone}` : ""}</div>
          </div>
          <div className="dr-body">
            <div className="dr-actions">
              <button className="btn primary" onClick={() => onEditar(l)} disabled={somenteLeitura}><Icone nome="editar" tam={14} />Editar</button>
              {admin && <button className="btn" onClick={() => onLogs(l)}><Icone nome="historico" tam={14} />Histórico</button>}
              <button className="btn perigo" onClick={() => onExcluir(l)} disabled={somenteLeitura}><Icone nome="lixo" tam={14} />Excluir</button>
            </div>
            <div>
              <p className="sect-t">Entrega</p>
              <div className="linha-acoes">
                {l.situacao === "aberto" && <>
                  <button className="btn" disabled={somenteLeitura} onClick={() => onAlterar(l, { situacao: "entregue" }, "Marcado como entregue.")}>Marcar como entregue</button>
                  <button className="btn" disabled={somenteLeitura} onClick={() => onCancelar(l)}>Cancelar pedido</button>
                </>}
                {l.situacao !== "aberto" && <>
                  <Situacao valor={l.situacao} />
                  <button className="btn" disabled={somenteLeitura} onClick={() => onAlterar(l, { situacao: "aberto" }, "Pedido reaberto.")}>Reabrir</button>
                </>}
              </div>
            </div>
            <div>
              <p className="sect-t">Pagamento</p>
              <div className="seg seg-larga">
                {STATUS.map((s) => (
                  <button key={s} aria-pressed={l.status === s} disabled={somenteLeitura} onClick={() => l.status !== s && onAlterar(l, { status: s }, `Pagamento: ${s}.`)}>{s.replace("Pagamento na ", "Na ").replace("Aguardando Pagamento", "Aguardando")}</button>
                ))}
              </div>
            </div>
            <div>
              <p className="sect-t">Produtos</p>
              <ul className="itens-lista">
                {(detalhe?.itens ?? []).map((i) => (
                  <li key={i.id}>
                    <span className="qtd-badge">{i.unit === "kg" ? fmtQtd(i.quantity, "kg") : `${i.quantity}×`}</span>
                    <span>{i.produto}{i.produto_size && <span className="sutil"> · {fmtTamanho(i.produto_size)}</span>}</span>
                    <span className="sutil" title={i.stock_reserved ? "Estoque já baixado" : "O estoque será baixado no dia da entrega"}>
                      {i.stock_reserved ? "estoque baixado" : "a reservar"}
                    </span>
                  </li>
                ))}
                {!detalhe && <li className="sutil">Carregando…</li>}
              </ul>
            </div>
            {l.obs && (
              <div>
                <p className="sect-t">Observações</p>
                <p className="obs-texto">{l.obs}</p>
              </div>
            )}
            <div>
              <p className="sect-t">Etiqueta</p>
              <div className="etq-escolha">
                {etiquetas.map((e) => (
                  <button key={e.id} className="etq-botao" disabled={somenteLeitura} aria-pressed={e.name.toLowerCase() === l.label.toLowerCase()}
                    onClick={() => onAlterar(l, { label: e.name }, `Etiqueta: ${e.name}.`)}>
                    <Chip nome={e.name} cor={e.color} />
                  </button>
                ))}
              </div>
            </div>
            <dl className="dl">
              <dt>Criado em</dt><dd>{detalhe ? fmtData(detalhe.created_at) : "…"}</dd>
              <dt>Itens</dt><dd>{l.itens} {l.itens === 1 ? "produto" : "produtos"}{l.unit !== "misto" ? ` · ${fmtQtd(l.quantity, l.unit, true)}` : ""}</dd>
            </dl>
          </div>
        </>
      )}
    </aside>
  );
}

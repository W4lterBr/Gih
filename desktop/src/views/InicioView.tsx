import { api } from "../api";
import { useApp } from "../contexto";
import type { View } from "../types";
import { fmtBRL, fmtData, fmtInt, fmtQtd, isoLocal } from "../format";
import { Cabecalho, Etiqueta, Kpi, Situacao, Status, useCarregar, Vazio } from "../components/ui";
import { Icone } from "../components/Icone";

interface Painel {
  kpis: {
    pedidos_hoje: number; itens_hoje: number; aguardando_pagamento: number; proximos_7_dias: number;
    estoque_baixo: number; esgotados: number; clientes: number; valor_mes: number | null;
  };
  por_dia: { dia: string; pedidos: number; itens: number }[];
  status: { status: string; n: number }[];
  top: { name: string; unit: string; quantidade: number; preco: number }[];
  entregas_hoje: { id: number; cliente: string; telefone: string | null; status: string; situacao: string; label: string; label_color: string | null; produtos: string }[];
  estoque_baixo: { id: number; name: string; stock: number; min_stock: number; unit: string }[];
}

const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

/** Barras de pedidos por dia: 6 dias para trás, hoje e 7 para frente. */
function GraficoDias({ dados }: { dados: Painel["por_dia"] }) {
  const hoje = isoLocal();
  const mapa = new Map(dados.map((d) => [d.dia, d]));
  const dias = Array.from({ length: 14 }, (_, i) => {
    const [a, m, d] = hoje.split("-").map(Number);
    const dt = new Date(a, m - 1, d - 6 + i);
    const iso = isoLocal(dt);
    return { iso, dt, n: mapa.get(iso)?.pedidos ?? 0, itens: mapa.get(iso)?.itens ?? 0 };
  });
  const max = Math.max(1, ...dias.map((d) => d.n));
  return (
    <div className="barras" role="img" aria-label="Pedidos por dia de entrega">
      {dias.map((d) => (
        <div key={d.iso} className={`barra${d.iso === hoje ? " hoje" : d.iso < hoje ? " passado" : ""}`} title={`${fmtData(d.iso)}: ${d.n} pedido(s), ${d.itens} itens`}>
          <span className="barra-n">{d.n || ""}</span>
          <i style={{ height: `${Math.max(d.n ? 6 : 2, (d.n / max) * 100)}%` }} />
          <span className="barra-rot">{d.iso === hoje ? "hoje" : DIAS[d.dt.getDay()]}<small>{String(d.dt.getDate()).padStart(2, "0")}</small></span>
        </div>
      ))}
    </div>
  );
}

export function InicioView({ onView, onNovoPedido }: { onView: (v: View) => void; onNovoPedido: () => void }) {
  const { empresa, usuario, somenteLeitura, motivoBloqueio, ve, pode } = useApp();
  const { dados } = useCarregar(() => api.get<Painel>("/dashboard"), [], 30000);
  const hora = new Date().getHours();
  const saudacao = hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
  const dataLonga = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  const hojeTexto = dataLonga.charAt(0).toUpperCase() + dataLonga.slice(1);

  return (
    <section className="view">
      <Cabecalho titulo={`${saudacao}, ${usuario.username}`} sub={<>{hojeTexto} · {empresa.nome}</>}>
        {ve("producao") && <button className={`btn${pode("pedidos") ? "" : " primary"}`} onClick={() => onView("producao")}><Icone nome="producao" tam={14} />Produção</button>}
        {pode("pedidos") && <button className="btn primary" onClick={onNovoPedido} disabled={somenteLeitura} title={somenteLeitura ? motivoBloqueio : undefined}><Icone nome="mais" tam={14} />Novo pedido</button>}
      </Cabecalho>
      {!dados ? <div className="loading">Carregando…</div> : (
        <div className="pane">
          <div className="kpis kpis-4 sem-pad">
            <Kpi rotulo="Entregas hoje" valor={fmtInt(dados.kpis.pedidos_hoje)} sub={`${fmtInt(dados.kpis.itens_hoje)} itens`} tom="brand" onClick={() => onView("pedidos")} />
            <Kpi rotulo="Próximos 7 dias" valor={fmtInt(dados.kpis.proximos_7_dias)} sub="pedidos agendados" onClick={() => onView("pedidos")} />
            <Kpi rotulo="A receber" valor={fmtInt(dados.kpis.aguardando_pagamento)} sub="não pagos (inclui entregues fiado)" tom={dados.kpis.aguardando_pagamento ? "attn" : undefined} onClick={() => onView("pedidos")} />
            <Kpi rotulo="Estoque" valor={dados.kpis.esgotados ? `${fmtInt(dados.kpis.esgotados)} esgotado(s)` : "OK"}
              sub={`${fmtInt(dados.kpis.estoque_baixo)} abaixo do mínimo`} tom={dados.kpis.esgotados ? "alert" : dados.kpis.estoque_baixo ? "attn" : "ok"} onClick={() => onView("pronta")} />
          </div>

          <div className="grade-2">
            <div className="card">
              <div className="card-cab"><b>Entregas de hoje</b><button className="link" onClick={() => onView("pedidos")}>Ver pedidos</button></div>
              {dados.entregas_hoje.length === 0 ? (
                <Vazio icone="calendario" titulo="Nenhuma entrega para hoje" />
              ) : (
                <ul className="entregas">
                  {dados.entregas_hoje.map((e) => (
                    <li key={e.id}>
                      <div className="ent-cli"><b>{e.cliente}</b>{e.telefone && <span>{e.telefone}</span>}</div>
                      <div className="ent-prod">{e.produtos}</div>
                      <div className="ent-tags"><Etiqueta nome={e.label} cor={e.label_color} /><Status valor={e.status} /><Situacao valor={e.situacao} /></div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="col-dupla">
              <div className="card">
                <div className="card-cab"><b>Pedidos por dia de entrega</b><span className="sutil">últimos 6 e próximos 7 dias</span></div>
                <GraficoDias dados={dados.por_dia} />
              </div>
              <div className="card">
                <div className="card-cab"><b>Mais pedidos (30 dias)</b>{dados.kpis.valor_mes !== null && <span className="sutil">valor estimado no mês: {fmtBRL(dados.kpis.valor_mes)}</span>}</div>
                {dados.top.length === 0 ? <Vazio icone="bolo" titulo="Sem pedidos nos últimos 30 dias" /> : (
                  <ul className="ranking">
                    {dados.top.map((t, i) => {
                      const max = dados.top[0].quantidade || 1;
                      return (
                        <li key={t.name}>
                          <span className="rk-n">{i + 1}</span>
                          <span className="rk-nome">{t.name}</span>
                          <span className="rk-barra"><i style={{ width: `${(t.quantidade / max) * 100}%` }} /></span>
                          <span className="rk-q">{fmtQtd(t.quantidade, t.unit)}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          </div>

          {dados.estoque_baixo.length > 0 && (
            <div className="card notice alerta-suave">
              <b><Icone nome="alerta" tam={14} /> Estoque baixo</b>
              <p>{dados.estoque_baixo.map((p) => `${p.name} (${fmtQtd(p.stock, p.unit)})`).join(" · ")}</p>
              {pode("movimentacao") && <div><button className="btn mini" onClick={() => onView("movimentacao")}>Registrar entrada</button></div>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

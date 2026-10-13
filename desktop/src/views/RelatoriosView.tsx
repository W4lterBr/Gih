import { useEffect, useState } from "react";
import { abrirArquivo, api, escolherSalvar } from "../api";
import { useApp } from "../contexto";
import type { Etiqueta } from "../types";
import { isoLocal } from "../format";
import { Cabecalho, useCarregar, Vazio } from "../components/ui";
import { Icone } from "../components/Icone";

type Tipo = "entregas" | "producao" | "fechamento";
interface Rel { titulo: string; meta: string; colunas: string[]; linhas: (string | number)[][]; rodape: string; resumo?: { colunas: string[]; linhas: (string | number)[][] } }

const ABAS: [Tipo, string, string][] = [
  ["entregas", "Entregas do dia", "Pedidos do dia (menos os cancelados), com endereço e pagamento — para separar e entregar."],
  ["fechamento", "Fechamento", "Quantidades por cliente e produto no período (valor pelo preço de cadastro)."],
  ["producao", "Produção e estoque", "Todas as entradas e saídas de estoque no período."],
];

const inicioMes = () => isoLocal().slice(0, 8) + "01";

export function RelatoriosView() {
  const { toast } = useApp();
  const [tipo, setTipo] = useState<Tipo>("entregas");
  const [dia, setDia] = useState(isoLocal());
  const [de, setDe] = useState(inicioMes());
  const [ate, setAte] = useState(isoLocal());
  const [etiqueta, setEtiqueta] = useState("");
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([]);
  useEffect(() => { api.get<{ etiquetas: Etiqueta[] }>("/etiquetas").then((r) => setEtiquetas(r.etiquetas)).catch(() => {}); }, []);
  const params = tipo === "entregas" ? { tipo, dia } : { tipo, de, ate, etiqueta: tipo === "fechamento" ? etiqueta : "" };
  const { dados } = useCarregar(() => api.get<Rel>("/relatorios", params), [tipo, dia, de, ate, etiqueta]);

  const exportar = async (ext: "pdf" | "xlsx") => {
    const caminho = await escolherSalvar(`${tipo}_${tipo === "entregas" ? dia : `${de}_${ate}`}.${ext}`, [ext === "pdf" ? { name: "PDF", extensions: ["pdf"] } : { name: "Excel", extensions: ["xlsx"] }]);
    if (!caminho) return;
    try {
      const r = await api.post<{ caminho: string }>("/relatorios/exportar", { ...params, caminho });
      toast("Relatório exportado.");
      abrirArquivo(r.caminho).catch(() => {});
    } catch (e) { toast((e as Error).message, true); }
  };

  const aba = ABAS.find((a) => a[0] === tipo)!;
  return (
    <section className="view">
      <Cabecalho titulo="Relatórios" sub={aba[2]}>
        <button className="btn" onClick={() => exportar("xlsx")} disabled={!dados?.linhas.length}><Icone nome="download" tam={14} />Excel</button>
        <button className="btn primary" onClick={() => exportar("pdf")} disabled={!dados?.linhas.length}><Icone nome="download" tam={14} />PDF</button>
      </Cabecalho>
      <div className="config-abas sem-titulo">
        {ABAS.map(([t, r]) => <button key={t} aria-selected={tipo === t} onClick={() => setTipo(t)}>{r}</button>)}
      </div>
      <div className="filters pad-top">
        {tipo === "entregas" ? (
          <div className="periodo"><label>Dia <input type="date" value={dia} onChange={(e) => setDia(e.target.value || isoLocal())} /></label></div>
        ) : (
          <div className="periodo">
            <label>De <input type="date" value={de} max={ate} onChange={(e) => setDe(e.target.value)} /></label>
            <label>Até <input type="date" value={ate} min={de} onChange={(e) => setAte(e.target.value)} /></label>
          </div>
        )}
        {tipo === "fechamento" && (
          <select className="chip" value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)} aria-label="Etiqueta">
            <option value="">Todas as etiquetas</option>
            {etiquetas.map((e) => <option key={e.id}>{e.name}</option>)}
          </select>
        )}
        <span className="grow" />
        {dados && <span className="sutil">{dados.rodape}</span>}
      </div>
      <div className="pane">
        {!dados ? <div className="loading">Carregando…</div> : dados.linhas.length === 0 ? (
          <div className="card"><Vazio icone="relatorios" titulo="Nada no período" texto={dados.meta} /></div>
        ) : (
          <>
            <div className="card tabela-rel">
              <table>
                <thead><tr>{dados.colunas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{dados.linhas.map((l, i) => <tr key={i}>{l.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{v}</td>)}</tr>)}</tbody>
              </table>
            </div>
            {dados.resumo && (
              <div className="card tabela-rel">
                <div className="card-cab"><b>Resumo por cliente e etiqueta</b></div>
                <table>
                  <thead><tr>{dados.resumo.colunas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>{dados.resumo.linhas.map((l, i) => <tr key={i}>{l.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{v}</td>)}</tr>)}</tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

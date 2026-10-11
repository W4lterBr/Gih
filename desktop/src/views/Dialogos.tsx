import { useEffect, useState } from "react";
import { abrirArquivo, api, escolherSalvar } from "../api";
import { useApp } from "../contexto";
import type { Etiqueta, Log } from "../types";
import { fmtData, fmtDataHora, isoLocal } from "../format";
import { Campo, Etiqueta as Chip, Modal, useCarregar } from "../components/ui";
import { Icone } from "../components/Icone";

// ---------------------------------------------------------------- histórico (auditoria)

const ACAO: Record<string, string> = { create: "Criado", update: "Alterado", delete: "Excluído" };

export function LogsDialog({ entidade, id, titulo, onClose }: { entidade: string; id: number; titulo: string; onClose: () => void }) {
  const { dados } = useCarregar(() => api.get<{ logs: Log[] }>("/logs", { entidade, id }), [entidade, id]);
  return (
    <Modal titulo={`Histórico · ${titulo}`} onClose={onClose} largura={640}>
      {!dados ? <div className="loading">Carregando…</div> : dados.logs.length === 0 ? (
        <p className="hist-vazio">Nenhum registro encontrado.</p>
      ) : (
        <ul className="timeline">
          {dados.logs.map((l, i) => (
            <li key={i} className={l.action === "delete" ? "bad" : ""}>
              <i />
              <div>
                <b>{ACAO[l.action] ?? l.action}</b> por {l.user || "—"}
                {l.details && <span className="det">{l.action === "update" ? l.details.split("; ").join("\n") : l.details}</span>}
              </div>
              <span>{fmtDataHora(l.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- etiquetas

export function EtiquetasDialog({ onClose }: { onClose: () => void }) {
  const { toast, confirmar } = useApp();
  const { dados, recarregar } = useCarregar(() => api.get<{ etiquetas: Etiqueta[] }>("/etiquetas"), []);
  const [editando, setEditando] = useState<{ id?: number; name: string; color: string } | null>(null);
  const [erro, setErro] = useState("");

  const salvar = async () => {
    if (!editando) return;
    try {
      if (editando.id) await api.put(`/etiquetas/${editando.id}`, editando);
      else await api.post("/etiquetas", editando);
      setEditando(null);
      setErro("");
      recarregar(true);
    } catch (e) { setErro((e as Error).message); }
  };

  const excluir = async (e: Etiqueta) => {
    const { pedidos } = await api.get<{ pedidos: number }>(`/etiquetas/${e.id}/uso`);
    const ok = await confirmar({
      titulo: "Excluir etiqueta", perigo: true, ok: "Excluir",
      texto: <>Excluir a etiqueta <b>{e.name}</b>?{pedidos > 0 && <><br />{pedidos} pedido(s) usam esta etiqueta e passarão para "Comum".</>}</>,
    });
    if (!ok) return;
    try { await api.del(`/etiquetas/${e.id}`); toast("Etiqueta excluída."); recarregar(true); }
    catch (err) { toast((err as Error).message, true); }
  };

  return (
    <Modal titulo="Etiquetas" onClose={onClose} largura={520} aoEnviar={salvar}>
      <p className="nota-rodape">Etiquetas destacam pedidos na lista (ex.: Urgente, Encomenda especial).</p>
      <div className="lista-simples">
        {dados?.etiquetas.map((e) => (
          editando?.id === e.id ? null : (
            <div className="ls-linha" key={e.id}>
              <Chip nome={e.name} cor={e.color} />
              <span className="grow" />
              <button type="button" className="icone-btn" onClick={() => { setEditando({ ...e }); setErro(""); }} aria-label="Editar"><Icone nome="editar" tam={14} /></button>
              <button type="button" className="icone-btn perigo" onClick={() => excluir(e)} aria-label="Excluir"><Icone nome="lixo" tam={14} /></button>
            </div>
          )
        ))}
        {editando ? (
          <div className="ls-linha editando">
            <input type="color" value={editando.color} onChange={(e) => setEditando({ ...editando, color: e.target.value })} aria-label="Cor" />
            <input autoFocus value={editando.name} placeholder="Nome da etiqueta" onChange={(e) => setEditando({ ...editando, name: e.target.value })} />
            <button type="submit" className="btn primary mini">Salvar</button>
            <button type="button" className="btn mini" onClick={() => { setEditando(null); setErro(""); }}>Cancelar</button>
          </div>
        ) : (
          <button type="button" className="btn mini" onClick={() => setEditando({ name: "", color: "#6b7280" })}><Icone nome="mais" tam={12} />Nova etiqueta</button>
        )}
      </div>
      {erro && <p className="form-erro">{erro}</p>}
    </Modal>
  );
}

// ---------------------------------------------------------------- relatório de pedidos

export function RelatorioPedidosDialog({ de, ate, onClose }: { de: string; ate: string; onClose: () => void }) {
  const { toast } = useApp();
  const [opcoes, setOpcoes] = useState<{ clientes: string[]; etiquetas: string[] } | null>(null);
  const [inicio, setInicio] = useState(de || isoLocal());
  const [fim, setFim] = useState(ate || isoLocal());
  const [cliente, setCliente] = useState("");
  const [etiqueta, setEtiqueta] = useState("");
  const [formato, setFormato] = useState<"pdf" | "xlsx">("pdf");
  const [gerando, setGerando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => { api.get<{ clientes: string[]; etiquetas: string[] }>("/pedidos/relatorio/opcoes").then(setOpcoes).catch(() => {}); }, []);

  const gerar = async () => {
    const nome = `relatorio_${(cliente || "Todos").replace(/\s+/g, "_")}_${(etiqueta || "Todas_as_Etiquetas").replace(/\s+/g, "_")}_${inicio}_${fim}.${formato}`;
    const caminho = await escolherSalvar(nome, [formato === "pdf" ? { name: "PDF", extensions: ["pdf"] } : { name: "Excel", extensions: ["xlsx"] }]);
    if (!caminho) return;
    setGerando(true);
    setErro("");
    try {
      const r = await api.post<{ caminho: string; linhas: number }>("/pedidos/relatorio", { de: inicio, ate: fim, cliente, etiqueta, formato, caminho });
      toast(`Relatório gerado (${r.linhas} pedidos).`);
      abrirArquivo(r.caminho).catch(() => {});
      onClose();
    } catch (e) { setErro((e as Error).message); }
    finally { setGerando(false); }
  };

  return (
    <Modal titulo="Relatório de pedidos" onClose={onClose} largura={480} aoEnviar={gerar}
      rodape={<>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button type="submit" className="btn primary" disabled={gerando}><Icone nome="download" tam={14} />{gerando ? "Gerando…" : "Gerar"}</button>
      </>}>
      <div className="form-grid">
        <Campo rotulo="De"><input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} /></Campo>
        <Campo rotulo="Até"><input type="date" value={fim} min={inicio} onChange={(e) => setFim(e.target.value)} /></Campo>
        <Campo rotulo="Cliente" largura="1 / -1">
          <select value={cliente} onChange={(e) => setCliente(e.target.value)}>
            <option value="">Todos os clientes</option>
            {opcoes?.clientes.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Etiqueta">
          <select value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)}>
            <option value="">Todas as etiquetas</option>
            {opcoes?.etiquetas.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Formato">
          <div className="seg">
            <button type="button" aria-pressed={formato === "pdf"} onClick={() => setFormato("pdf")}>PDF</button>
            <button type="button" aria-pressed={formato === "xlsx"} onClick={() => setFormato("xlsx")}>Excel</button>
          </div>
        </Campo>
      </div>
      <p className="nota-rodape">Período pela data de entrega: {fmtData(inicio)} a {fmtData(fim)}.</p>
      {erro && <p className="form-erro">{erro}</p>}
    </Modal>
  );
}

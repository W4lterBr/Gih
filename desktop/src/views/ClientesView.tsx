import { useState } from "react";
import { api } from "../api";
import { useApp } from "../contexto";
import type { Cliente } from "../types";
import { BarraSelecao, Cabecalho, Campo, CampoBusca, Modal, Tabela, useCarregar, useDebounce, Vazio, type Coluna } from "../components/ui";
import { Icone } from "../components/Icone";
import { LogsDialog } from "./Dialogos";
import { PedidoDialog } from "./PedidoDialog";

function ClienteDialog({ cliente, onClose, onSalvo }: { cliente: Cliente | null; onClose: () => void; onSalvo: (msg: string) => void }) {
  const [f, setF] = useState({ name: cliente?.name ?? "", phone: cliente?.phone ?? "", address: cliente?.address ?? "", observation: cliente?.observation ?? "" });
  const [erro, setErro] = useState("");
  const salvar = async () => {
    if (!f.name.trim()) { setErro("Nome é obrigatório."); return; }
    try {
      if (cliente) await api.put(`/clientes/${cliente.id}`, f);
      else await api.post("/clientes", f);
      onSalvo(cliente ? "Cliente atualizado." : "Cliente criado.");
    } catch (e) { setErro((e as Error).message); }
  };
  return (
    <Modal titulo={cliente ? "Editar cliente" : "Novo cliente"} onClose={onClose} largura={520} aoEnviar={salvar}
      rodape={<><button type="button" className="btn" onClick={onClose}>Cancelar</button><button className="btn primary">Salvar</button></>}>
      <div className="form-grid">
        <Campo rotulo="Nome" largura="1 / -1"><input autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Campo>
        <Campo rotulo="Telefone"><input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="(00) 00000-0000" /></Campo>
        <Campo rotulo="Endereço"><input value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Campo>
        <Campo rotulo="Observações" largura="1 / -1">
          <textarea rows={3} value={f.observation} onChange={(e) => setF({ ...f, observation: e.target.value })} placeholder="Preferências, restrições, como prefere ser chamado…" />
        </Campo>
      </div>
      {erro && <p className="form-erro">{erro}</p>}
    </Modal>
  );
}

export function ClientesView() {
  const { toast, confirmar, admin, dadosMudaram, somenteLeitura, motivoBloqueio } = useApp();
  const [q, setQ] = useState("");
  const qd = useDebounce(q);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [dialogo, setDialogo] = useState<{ tipo: "editar"; c: Cliente | null } | { tipo: "pedido"; c: Cliente } | { tipo: "logs"; c: Cliente } | null>(null);
  const { dados, recarregar } = useCarregar(() => api.get<{ clientes: Cliente[] }>("/clientes", { q: qd }), [qd]);
  const linhas = dados?.clientes ?? [];
  const porId = new Map(linhas.map((c) => [c.id, c]));
  const marcados = [...sel].map((i) => porId.get(i)).filter(Boolean) as Cliente[];

  const excluir = async () => {
    const ok = await confirmar({
      titulo: marcados.length === 1 ? "Excluir cliente" : `Excluir ${marcados.length} clientes`, perigo: true, ok: "Excluir",
      texto: <>{marcados.length === 1 ? <><b>{marcados[0].name}</b> será excluído.</> : `${marcados.length} clientes serão excluídos.`} Clientes com pedidos não são excluídos.</>,
    });
    if (!ok) return;
    try {
      const r = await api.post<{ excluidos: number; bloqueados: string[] }>("/clientes/excluir", { ids: marcados.map((c) => c.id) });
      if (r.bloqueados.length) toast(`${r.excluidos} excluído(s). Com pedidos vinculados (mantidos): ${r.bloqueados.join(", ")}.`, true);
      else toast(r.excluidos === 1 ? "Cliente excluído." : `${r.excluidos} clientes excluídos.`);
      setSel(new Set()); recarregar(true);
    } catch (e) { toast((e as Error).message, true); }
  };

  const colunas: Coluna<Cliente>[] = [
    { id: "nome", titulo: "Nome", largura: "minmax(180px,1.4fr)", ordenar: (c) => c.name, render: (c) => <b className="peso-500">{c.name}</b> },
    { id: "fone", titulo: "Telefone", largura: "150px", ordenar: (c) => c.phone ?? "", render: (c) => c.phone ?? "" },
    { id: "end", titulo: "Endereço", largura: "minmax(160px,1.4fr)", render: (c) => c.address ?? "", titleAttr: (c) => c.address ?? "" },
    { id: "obs", titulo: "Observações", largura: "minmax(140px,1.2fr)", render: (c) => <span className="sutil">{c.observation ?? ""}</span>, titleAttr: (c) => c.observation ?? "" },
    { id: "acoes", titulo: "", largura: admin ? "124px" : "96px", render: (c) => (
      <span className="acoes-linha" onClick={(e) => e.stopPropagation()}>
        <button className="icone-btn" title="Novo pedido para este cliente" disabled={somenteLeitura} onClick={() => setDialogo({ tipo: "pedido", c })}><Icone nome="pedidos" tam={14} /></button>
        <button className="icone-btn" title="Editar" onClick={() => setDialogo({ tipo: "editar", c })}><Icone nome="editar" tam={14} /></button>
        {admin && <button className="icone-btn" title="Histórico" onClick={() => setDialogo({ tipo: "logs", c })}><Icone nome="historico" tam={14} /></button>}
      </span>
    ) },
  ];

  return (
    <section className="view">
      <Cabecalho titulo="Clientes" sub={`${linhas.length} cliente(s)`}>
        <button className="btn primary" onClick={() => setDialogo({ tipo: "editar", c: null })} disabled={somenteLeitura} title={somenteLeitura ? motivoBloqueio : undefined}><Icone nome="mais" tam={14} />Novo cliente</button>
      </Cabecalho>
      <div className="filters"><CampoBusca valor={q} onChange={setQ} placeholder="Nome, telefone, endereço ou observação" /></div>
      <BarraSelecao n={marcados.length} rotulo={["cliente marcado", "clientes marcados"]} onLimpar={() => setSel(new Set())}>
        <button className="btn perigo" onClick={excluir} disabled={somenteLeitura}><Icone nome="lixo" tam={14} />Excluir</button>
      </BarraSelecao>
      <Tabela linhas={linhas} colunas={colunas} chave={(c) => c.id} selecionadas={sel} onSelecionar={setSel}
        onAbrir={(c) => setDialogo({ tipo: "editar", c })} ordemPadrao={{ col: "nome", dir: 1 }}
        vazio={<Vazio icone="clientes" titulo={q ? "Nenhum cliente encontrado" : "Nenhum cliente cadastrado"} />} />
      {dialogo?.tipo === "editar" && <ClienteDialog cliente={dialogo.c} onClose={() => setDialogo(null)} onSalvo={(m) => { setDialogo(null); toast(m); recarregar(true); }} />}
      {dialogo?.tipo === "pedido" && <PedidoDialog clienteFixo={dialogo.c.id} onClose={() => setDialogo(null)} onSalvo={(m) => { setDialogo(null); toast(m); dadosMudaram(); }} />}
      {dialogo?.tipo === "logs" && <LogsDialog entidade="customer" id={dialogo.c.id} titulo={dialogo.c.name} onClose={() => setDialogo(null)} />}
    </section>
  );
}

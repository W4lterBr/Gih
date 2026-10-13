import type { Empresa, Usuario, View } from "../types";
import { Icone } from "./Icone";
import { sigla } from "../format";

interface Item { v: View; nome: string; icone: string; atalho?: string; count?: number }

interface Props {
  view: View;
  onView: (v: View) => void;
  empresa: Empresa;
  usuario: Usuario;
  escuro: boolean;
  onTema: () => void;
  onSair: () => void;
  contagens: { pedidosHoje?: number; producao?: number; esgotados?: number };
}

export const ITENS_OPERACAO: Item[] = [
  { v: "inicio", nome: "Início", icone: "inicio", atalho: "1" },
  { v: "pedidos", nome: "Pedidos", icone: "pedidos", atalho: "2" },
  { v: "producao", nome: "Produção", icone: "producao", atalho: "3" },
  { v: "pronta", nome: "Pronta entrega", icone: "pronta", atalho: "4" },
  { v: "custos", nome: "Custos", icone: "custos", atalho: "5" },
];
export const ITENS_CADASTRO: Item[] = [
  { v: "clientes", nome: "Clientes", icone: "clientes", atalho: "6" },
  { v: "produtos", nome: "Produtos", icone: "produtos", atalho: "7" },
  { v: "movimentacao", nome: "Movimentação", icone: "movimentacao", atalho: "8" },
  { v: "relatorios", nome: "Relatórios", icone: "relatorios", atalho: "9" },
];
/** Itens do menu que o perfil do usuário vê (api/permissoes.py decide; o motor também recusa). */
export const visiveis = (itens: Item[], ve: (tela: string) => boolean) => itens.filter((i) => ve(i.v));

export function Sidebar({ view, onView, empresa, usuario, escuro, onTema, onSair, contagens, ve }: Props & { ve: (tela: string) => boolean }) {
  const ehConfig = view.startsWith("cfg-");
  const count = (v: View) => (v === "pedidos" ? contagens.pedidosHoje : v === "producao" ? contagens.producao : v === "pronta" ? contagens.esgotados : undefined);
  const botao = (i: Item) => {
    const n = count(i.v);
    return (
      <button key={i.v} aria-current={view === i.v} onClick={() => onView(i.v)} title={i.atalho ? `${i.nome} (Ctrl+${i.atalho})` : i.nome}>
        <Icone nome={i.icone} />
        {i.nome}
        {n ? <span className={`count${i.v === "pronta" ? " count-alerta" : ""}`} title={i.v === "pronta" ? "Produtos esgotados" : i.v === "pedidos" ? "Pedidos para hoje" : "Itens na lista"}>{n}</span> : null}
      </button>
    );
  };
  return (
    <aside className="sidebar">
      <div className="marca-empresa">
        {empresa.logo
          ? <img src={empresa.logo} alt="" />
          : <span className="logo-sigla">{sigla(empresa.nome)}</span>}
        <div>
          <b title={empresa.nome}>{empresa.nome}</b>
          <span>Gestão de pedidos</span>
        </div>
      </div>
      <div className="side-grupos">
        <div>
          <div className="side-label">Operação</div>
          <nav className="nav">{visiveis(ITENS_OPERACAO, ve).map(botao)}</nav>
        </div>
        {visiveis(ITENS_CADASTRO, ve).length > 0 && (
          <div>
            <div className="side-label">Cadastros</div>
            <nav className="nav">{visiveis(ITENS_CADASTRO, ve).map(botao)}</nav>
          </div>
        )}
        <div>
          <nav className="nav">
            <button aria-current={ehConfig} onClick={() => onView(usuario.role === "admin" ? "cfg-empresa" : "cfg-aparencia")}>
              <Icone nome="config" />
              Configurações
            </button>
          </nav>
        </div>
      </div>
      <div className="conta">
        <div className="conta-id">
          <span className="conta-av">{sigla(usuario.username)}</span>
          <b>{usuario.username}</b>
          <span className="conta-sit"><i />{usuario.perfil ?? (usuario.role === "admin" ? "Administrador" : "Usuário")}</span>
        </div>
        <div className="conta-acoes">
          <button className="btn" onClick={onTema} title="Alternar tema claro/escuro">
            <Icone nome={escuro ? "sol" : "lua"} tam={14} />{escuro ? "Claro" : "Escuro"}
          </button>
          <button className="btn" onClick={onSair} title="Sair e trocar de usuário">
            <Icone nome="sair" tam={14} />Sair
          </button>
        </div>
      </div>
    </aside>
  );
}

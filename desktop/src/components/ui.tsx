import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Icone } from "./Icone";
import { corTexto } from "../format";
import { useApp } from "../contexto";

// ---------------------------------------------------------------- carregar dados

/**
 * Busca dados do motor e recarrega quando `deps` muda ou quando outra tela avisa que
 * os dados mudaram. `intervalo` (ms) recarrega sozinho enquanto a tela está aberta —
 * para estoque e produção, que o painel da cozinha também altera.
 */
export function useCarregar<T>(buscar: () => Promise<T>, deps: unknown[], intervalo?: number) {
  const { versaoDados, toast } = useApp();
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const ref = useRef(buscar);
  ref.current = buscar;
  const seq = useRef(0);

  const recarregar = useCallback((silencioso = false) => {
    const meu = ++seq.current;
    if (!silencioso) setCarregando(true);
    return ref.current()
      .then((d) => { if (meu === seq.current) { setDados(d); setErro(null); } })
      .catch((e) => {
        if (meu !== seq.current) return;
        setErro(String(e.message ?? e));
        if (silencioso) return;
        toast(String(e.message ?? e), true);
      })
      .finally(() => { if (meu === seq.current) setCarregando(false); });
  }, [toast]);

  useEffect(() => { recarregar(); }, [...deps, versaoDados]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!intervalo) return;
    const t = setInterval(() => { if (!document.hidden) recarregar(true); }, intervalo);
    return () => clearInterval(t);
  }, [intervalo, recarregar]);
  return { dados, erro, carregando, recarregar };
}

/** Valor com atraso (para busca enquanto digita). */
export function useDebounce<T>(valor: T, ms = 200) {
  const [v, setV] = useState(valor);
  useEffect(() => { const t = setTimeout(() => setV(valor), ms); return () => clearTimeout(t); }, [valor, ms]);
  return v;
}

// ---------------------------------------------------------------- peças visuais

export function CampoBusca({ valor, onChange, placeholder, autoFocus }: { valor: string; onChange: (v: string) => void; placeholder: string; autoFocus?: boolean }) {
  return (
    <label className="search">
      <Icone nome="busca" tam={14} style={{ color: "var(--text-3)" }} />
      <input type="search" value={valor} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} autoFocus={autoFocus} data-busca />
      {valor && <button className="limpar" onClick={() => onChange("")} aria-label="Limpar busca"><Icone nome="fechar" tam={12} /></button>}
    </label>
  );
}

export function Etiqueta({ nome, cor }: { nome: string; cor?: string | null }) {
  const c = cor || "#6B7280";
  return <span className="etq" style={{ background: c, color: corTexto(c) }}>{nome}</span>;
}

const STATUS_CLS: Record<string, string> = {
  "Pago": "st-pago",
  "Aguardando Pagamento": "st-aguardando",
  "Pagamento na Retirada": "st-retirada",
  "Entregue": "st-entregue",
  "Cancelado": "st-cancelado",
};
/** Pagamento. Bancos antigos guardavam "Entregue"/"Cancelado" aqui — isso agora é a
 *  situação (selo próprio), então não repete. */
export function Status({ valor }: { valor: string }) {
  if (["entregue", "cancelado", "completed", "cancelled", "concluído"].includes(valor.toLowerCase())) return null;
  return <span className={`pill ${STATUS_CLS[valor] ?? ""}`}>{valor}</span>;
}

/** Situação da entrega: só aparece quando não está "aberto". */
export function Situacao({ valor }: { valor: string }) {
  if (valor === "entregue") return <span className="pill st-entregue">Entregue</span>;
  if (valor === "cancelado") return <span className="pill st-cancelado">Cancelado</span>;
  return null;
}

export function Vazio({ icone = "info", titulo, texto, children }: { icone?: string; titulo: string; texto?: ReactNode; children?: ReactNode }) {
  return (
    <div className="vazio">
      <div className="vazio-ic"><Icone nome={icone} tam={22} /></div>
      <b>{titulo}</b>
      {texto && <p>{texto}</p>}
      {children}
    </div>
  );
}

export function Cabecalho({ titulo, sub, children }: { titulo: string; sub?: ReactNode; children?: ReactNode }) {
  return (
    <div className="head">
      <div>
        <h1>{titulo}</h1>
        {sub && <p>{sub}</p>}
      </div>
      <div className="grow" />
      {children}
    </div>
  );
}

export function Kpi({ rotulo, valor, sub, tom, onClick }: { rotulo: string; valor: ReactNode; sub?: ReactNode; tom?: "attn" | "alert" | "ok" | "brand"; onClick?: () => void }) {
  return (
    <div className={`kpi${tom ? ` ${tom}` : ""}${onClick ? " clicavel" : ""}`} onClick={onClick} role={onClick ? "button" : undefined}>
      <label>{rotulo}</label>
      <strong>{valor}</strong>
      {sub && <span className="sub">{sub}</span>}
    </div>
  );
}

// ---------------------------------------------------------------- diálogo modal

export function Modal({ titulo, onClose, children, rodape, largura = 520, aoEnviar }: {
  titulo: ReactNode; onClose: () => void; children: ReactNode; rodape?: ReactNode; largura?: number;
  /** Enter no formulário envia. */
  aoEnviar?: () => void;
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    window.addEventListener("keydown", k, true);
    return () => window.removeEventListener("keydown", k, true);
  }, [onClose]);
  return (
    <div className="scrim modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="dialogo modal" style={{ width: `min(${largura}px, calc(100% - 32px))` }} role="dialog"
        onSubmit={(e) => { e.preventDefault(); aoEnviar?.(); }}>
        <div className="modal-topo">
          <h2>{titulo}</h2>
          <button type="button" className="x" onClick={onClose} aria-label="Fechar"><Icone nome="fechar" tam={14} /></button>
        </div>
        <div className="modal-corpo">{children}</div>
        {rodape && <div className="dialogo-acoes">{rodape}</div>}
      </form>
    </div>
  );
}

export function Campo({ rotulo, children, dica, erro, largura }: { rotulo: string; children: ReactNode; dica?: ReactNode; erro?: string | null; largura?: string }) {
  return (
    <label className="campo" style={largura ? { gridColumn: largura } : undefined}>
      <span>{rotulo}</span>
      {children}
      {erro ? <small className="erro">{erro}</small> : dica ? <small>{dica}</small> : null}
    </label>
  );
}

// ---------------------------------------------------------------- tabela

export interface Coluna<T> {
  id: string;
  titulo: string;
  largura: string;          // trilha do grid: "1fr", "120px", "minmax(160px,2fr)"
  num?: boolean;
  render: (l: T) => ReactNode;
  ordenar?: (l: T) => string | number;
  titleAttr?: (l: T) => string;
}

/**
 * Tabela com cabeçalho fixo, ordenação por coluna, seleção múltipla (caixas e
 * Ctrl/Shift+clique) e duplo clique para abrir.
 */
export function Tabela<T>({ linhas, colunas, chave, selecionadas, onSelecionar, onAbrir, ativa, vazio, linhaClasse, alturaLinha = 44, ordemPadrao }: {
  linhas: T[];
  colunas: Coluna<T>[];
  chave: (l: T) => number;
  selecionadas?: Set<number>;
  onSelecionar?: (s: Set<number>) => void;
  onAbrir?: (l: T) => void;
  ativa?: number | null;
  vazio?: ReactNode;
  linhaClasse?: (l: T) => string | undefined;
  alturaLinha?: number;
  ordemPadrao?: { col: string; dir: 1 | -1 };
}) {
  const [ordem, setOrdem] = useState<{ col: string; dir: 1 | -1 } | null>(ordemPadrao ?? null);
  const ultimo = useRef<number | null>(null);
  const comCaixa = !!onSelecionar;
  const trilhas = (comCaixa ? "34px " : "") + colunas.map((c) => c.largura).join(" ");

  const ordenadas = (() => {
    if (!ordem) return linhas;
    const col = colunas.find((c) => c.id === ordem.col);
    if (!col?.ordenar) return linhas;
    const f = col.ordenar;
    return [...linhas].sort((a, b) => {
      const x = f(a), y = f(b);
      return (typeof x === "string" && typeof y === "string" ? x.localeCompare(y, "pt-BR") : x < y ? -1 : x > y ? 1 : 0) * ordem.dir;
    });
  })();

  const sel = selecionadas ?? new Set<number>();
  const todas = ordenadas.length > 0 && ordenadas.every((l) => sel.has(chave(l)));

  const clicar = (e: React.MouseEvent, l: T) => {
    if (!onSelecionar) return;
    const id = chave(l);
    const novo = new Set(e.ctrlKey || e.metaKey ? sel : []);
    if (e.shiftKey && ultimo.current !== null) {
      const ids = ordenadas.map(chave);
      const [a, b] = [ids.indexOf(ultimo.current), ids.indexOf(id)].sort((x, y) => x - y);
      if (a >= 0) ids.slice(a, b + 1).forEach((i) => novo.add(i));
    } else if ((e.ctrlKey || e.metaKey) && sel.has(id)) {
      novo.delete(id);
    } else {
      novo.add(id);
    }
    ultimo.current = id;
    onSelecionar(novo);
  };

  const marcar = (l: T, v: boolean) => {
    if (!onSelecionar) return;
    const novo = new Set(sel);
    if (v) novo.add(chave(l)); else novo.delete(chave(l));
    ultimo.current = chave(l);
    onSelecionar(novo);
  };

  return (
    <div className="gridwrap">
      <div className="grid-scroll">
        <div className="cols ghead" style={{ gridTemplateColumns: trilhas }}>
          {comCaixa && (
            <label className="marca" title={todas ? "Desmarcar todos" : "Marcar todos"}>
              <input type="checkbox" checked={todas} onChange={(e) => onSelecionar?.(new Set(e.target.checked ? ordenadas.map(chave) : []))} />
            </label>
          )}
          {colunas.map((c) => (
            <button key={c.id} type="button" className={c.num ? "num" : ""} data-active={ordem?.col === c.id}
              disabled={!c.ordenar} style={!c.ordenar ? { cursor: "default" } : undefined}
              onClick={() => c.ordenar && setOrdem((o) => (o?.col === c.id ? { col: c.id, dir: (o.dir * -1) as 1 | -1 } : { col: c.id, dir: 1 }))}>
              {c.titulo}
              {c.ordenar && <span className="arrow">{ordem?.col === c.id && ordem.dir === -1 ? "▼" : "▲"}</span>}
            </button>
          ))}
        </div>
        {ordenadas.length === 0 ? (vazio ?? <div className="empty">Nada para mostrar.</div>) : (
          <div className="glist">
            {ordenadas.map((l) => {
              const id = chave(l);
              return (
                <div key={id} className={`cols lrow ${linhaClasse?.(l) ?? ""}`} style={{ gridTemplateColumns: trilhas, minHeight: alturaLinha }}
                  aria-selected={ativa === id || sel.has(id)} data-marcada={sel.has(id)}
                  onClick={(e) => clicar(e, l)} onDoubleClick={() => onAbrir?.(l)}>
                  {comCaixa && (
                    <label className="marca" onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={sel.has(id)} onChange={(e) => marcar(l, e.target.checked)} />
                    </label>
                  )}
                  {colunas.map((c) => (
                    <div key={c.id} className={c.num ? "num" : ""} title={c.titleAttr?.(l)}>{c.render(l)}</div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/** Barra que aparece quando há itens marcados. */
export function BarraSelecao({ n, rotulo, children, onLimpar }: { n: number; rotulo: [string, string]; children: ReactNode; onLimpar: () => void }) {
  if (!n) return null;
  return (
    <div className="selbar" role="status">
      <span><b>{n}</b> {n === 1 ? rotulo[0] : rotulo[1]}</span>
      <span className="grow" />
      {children}
      <button type="button" className="btn" onClick={onLimpar}>Desmarcar</button>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { Icone } from "./Icone";

export interface OpcaoCombo { id: number; rotulo: string; detalhe?: string }

/** Campo de escolha com busca enquanto digita (clientes, produtos). */
export function Combo({ opcoes, valor, onChange, placeholder, autoFocus, desabilitado, id }: {
  opcoes: OpcaoCombo[];
  valor: number | null;
  onChange: (id: number | null) => void;
  placeholder?: string;
  autoFocus?: boolean;
  desabilitado?: boolean;
  id?: string;
}) {
  const atual = opcoes.find((o) => o.id === valor) ?? null;
  const [texto, setTexto] = useState(atual?.rotulo ?? "");
  const [aberto, setAberto] = useState(false);
  const [sel, setSel] = useState(0);
  const caixa = useRef<HTMLDivElement>(null);

  useEffect(() => { if (!aberto) setTexto(atual?.rotulo ?? ""); }, [atual, aberto]);

  const filtradas = useMemo(() => {
    const q = texto.trim().toLowerCase();
    if (!aberto || !q || q === atual?.rotulo.toLowerCase()) return opcoes.slice(0, 200);
    return opcoes.filter((o) => `${o.rotulo} ${o.detalhe ?? ""}`.toLowerCase().includes(q)).slice(0, 200);
  }, [texto, opcoes, aberto, atual]);

  useEffect(() => {
    const fora = (e: MouseEvent) => { if (!caixa.current?.contains(e.target as Node)) setAberto(false); };
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, []);

  const escolher = (o: OpcaoCombo) => { onChange(o.id); setTexto(o.rotulo); setAberto(false); };

  return (
    <div className="combo" ref={caixa}>
      <input id={id} value={texto} placeholder={placeholder} autoFocus={autoFocus} disabled={desabilitado}
        onFocus={(e) => { setAberto(true); e.target.select(); }}
        onChange={(e) => { setTexto(e.target.value); setAberto(true); setSel(0); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setAberto(true); setSel((s) => Math.min(s + 1, filtradas.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
          else if (e.key === "Enter" && aberto) { e.preventDefault(); if (filtradas[sel]) escolher(filtradas[sel]); }
          else if (e.key === "Escape" && aberto) { e.stopPropagation(); setAberto(false); }
          else if (e.key === "Tab" && aberto && filtradas[sel] && texto && texto !== atual?.rotulo) escolher(filtradas[sel]);
        }} />
      <Icone nome="seta" tam={12} className="combo-seta" />
      {aberto && !desabilitado && (
        <ul className="combo-lista" role="listbox">
          {filtradas.length === 0 && <li className="combo-vazio">Nada encontrado.</li>}
          {filtradas.map((o, i) => (
            <li key={o.id} role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)}
              onMouseDown={(e) => { e.preventDefault(); escolher(o); }}>
              <span>{o.rotulo}</span>
              {o.detalhe && <small>{o.detalhe}</small>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

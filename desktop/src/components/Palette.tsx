import { useEffect, useMemo, useRef, useState } from "react";

export interface Comando {
  titulo: string;
  dica?: string;
  run: () => void;
}

interface Props {
  aberta: boolean;
  onClose: () => void;
  comandos: Comando[];
  /** Comandos extras gerados a partir do texto (ex.: clientes com esse nome). */
  buscar: (texto: string) => Comando[];
}

/** Paleta de comandos (Ctrl+K). */
export function Palette({ aberta, onClose, comandos, buscar }: Props) {
  const [texto, setTexto] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (aberta) {
      setTexto("");
      setSel(0);
      setTimeout(() => input.current?.focus(), 0);
    }
  }, [aberta]);

  const itens = useMemo(() => {
    const q = texto.trim().toLowerCase();
    return [...buscar(q), ...comandos.filter((c) => c.titulo.toLowerCase().includes(q))];
  }, [texto, comandos, buscar]);

  if (!aberta) return null;

  const executar = (c?: Comando) => {
    if (!c) return;
    onClose();
    c.run();
  };

  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="palette" role="dialog" aria-label="Paleta de comandos">
        <input
          ref={input}
          value={texto}
          placeholder="Digite um comando, cliente ou produto…"
          onChange={(e) => { setTexto(e.target.value); setSel(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, itens.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
            if (e.key === "Enter") executar(itens[sel]);
            if (e.key === "Escape") onClose();
          }}
        />
        <ul role="listbox">
          {itens.length === 0 && <li>Nada encontrado.</li>}
          {itens.map((c, i) => (
            <li key={c.titulo + i} role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onClick={() => executar(c)}>
              {c.titulo}
              {c.dica && <small>{c.dica}</small>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

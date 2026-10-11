import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp } from "../contexto";
import type { Cliente, Etiqueta, PedidoDetalhe, Produto } from "../types";
import { ehSegunda, fmtTamanho, isoLocal, somarDias } from "../format";
import { Campo, Modal } from "../components/ui";
import { Combo } from "../components/Combo";
import { Icone } from "../components/Icone";

export const STATUS = ["Aguardando Pagamento", "Pagamento na Retirada", "Pago"];

interface ItemForm { chave: number; id?: number; product_id: number | null; quantity: number }

/** Próximo dia com expediente (pula segunda-feira). */
const proximoUtil = (iso: string) => (ehSegunda(iso) ? somarDias(iso, 1) : iso);

/**
 * Novo pedido (um ou vários produtos) ou edição de uma linha da lista.
 * `clienteFixo`: pedido rápido aberto a partir de um cliente.
 */
export function PedidoDialog({ editar, clienteFixo, onClose, onSalvo }: {
  editar?: PedidoDetalhe | null;
  clienteFixo?: number | null;
  onClose: () => void;
  onSalvo: (msg: string) => void;
}) {
  const { toast } = useApp();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([]);
  const [cliente, setCliente] = useState<number | null>(editar?.customer_id ?? clienteFixo ?? null);
  const [entrega, setEntrega] = useState(editar?.delivery_date ?? proximoUtil(isoLocal()));
  const [status, setStatus] = useState(editar?.status ?? STATUS[0]);
  const [etiqueta, setEtiqueta] = useState(editar?.label ?? "Comum");
  const [obs, setObs] = useState(editar?.obs ?? "");
  const [itens, setItens] = useState<ItemForm[]>(
    editar ? editar.itens.map((i, k) => ({ chave: k, id: i.id, product_id: i.product_id, quantity: i.quantity })) : [{ chave: 0, product_id: null, quantity: 1 }],
  );
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<{ clientes: Cliente[] }>("/clientes"),
      api.get<{ produtos: Produto[] }>("/produtos"),
      api.get<{ etiquetas: Etiqueta[] }>("/etiquetas"),
    ]).then(([c, p, e]) => { setClientes(c.clientes); setProdutos(p.produtos); setEtiquetas(e.etiquetas); })
      .catch((e) => toast(String(e.message), true));
  }, [toast]);

  const opClientes = useMemo(() => clientes.map((c) => ({ id: c.id, rotulo: c.name, detalhe: c.phone ?? undefined })), [clientes]);
  const opProdutos = useMemo(() => produtos.map((p) => ({ id: p.id, rotulo: p.name, detalhe: `${p.stock} em estoque${p.size ? ` · ${fmtTamanho(p.size)}` : ""}` })), [produtos]);
  const prodPorId = useMemo(() => new Map(produtos.map((p) => [p.id, p])), [produtos]);
  const statusOpcoes = STATUS.includes(status) ? STATUS : [...STATUS, status];
  const segunda = !!entrega && ehSegunda(entrega);
  const total = itens.reduce((s, i) => s + (i.product_id ? i.quantity : 0), 0);

  const mudarItem = (chave: number, campo: Partial<ItemForm>) => setItens((l) => l.map((i) => (i.chave === chave ? { ...i, ...campo } : i)));
  const adicionarItem = () => setItens((l) => [...l, { chave: Math.max(0, ...l.map((i) => i.chave)) + 1, product_id: null, quantity: 1 }]);

  const salvar = async () => {
    const validos = itens.filter((i) => i.product_id);
    if (!cliente) { setErro("Selecione um cliente."); return; }
    if (!validos.length) { setErro("Adicione pelo menos um produto ao pedido."); return; }
    if (validos.some((i) => !i.quantity || i.quantity < 1)) { setErro("A quantidade deve ser maior que zero."); return; }
    if (segunda) { setErro("Segunda não há expediente, pedido negado."); return; }
    setErro("");
    setSalvando(true);
    try {
      if (editar) {
        await api.post("/pedidos/editar", {
          customer_id: cliente, delivery_date: entrega, status, label: etiqueta, notes: obs,
          itens: validos.map((i) => ({ id: i.id, product_id: i.product_id, quantity: i.quantity })),
        });
        onSalvo("Pedido atualizado.");
      } else {
        const r = await api.post<{ ids: number[] }>("/pedidos", {
          customer_id: cliente, delivery_date: entrega, status, label: etiqueta, notes: obs,
          products: validos.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
        });
        onSalvo(r.ids.length > 1 ? `Pedido criado com ${r.ids.length} produtos.` : "Pedido criado.");
      }
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  };

  // Ctrl+Enter salva de qualquer campo.
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); salvar(); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });

  const rapidas: [string, string][] = [["Hoje", isoLocal()], ["Amanhã", somarDias(isoLocal(), 1)], ["Em 2 dias", somarDias(isoLocal(), 2)]];

  return (
    <Modal titulo={editar ? `Editar pedido #${editar.id}` : "Novo pedido"} onClose={onClose} largura={720} aoEnviar={salvar}
      rodape={<>
        <span className="rodape-info">{total} {total === 1 ? "item" : "itens"} · <span className="kbd">Ctrl Enter</span> salva</span>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button type="submit" className="btn primary" disabled={salvando}>{salvando ? "Salvando…" : editar ? "Salvar alterações" : "Criar pedido"}</button>
      </>}>
      <div className="form-grid">
        <Campo rotulo="Cliente" largura="1 / -1">
          <Combo opcoes={opClientes} valor={cliente} onChange={setCliente} placeholder="Digite para buscar o cliente…"
            autoFocus={!clienteFixo && !editar} desabilitado={!!clienteFixo} />
        </Campo>
        <Campo rotulo="Entrega" erro={segunda ? "Segunda não há expediente." : null}>
          <div className="linha-data">
            <input type="date" value={entrega} onChange={(e) => setEntrega(e.target.value)} required />
            {rapidas.map(([r, d]) => (
              <button type="button" key={r} className="chip mini" aria-pressed={entrega === d} disabled={ehSegunda(d)} onClick={() => setEntrega(d)}>{r}</button>
            ))}
          </div>
        </Campo>
        <Campo rotulo="Pagamento">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {statusOpcoes.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Etiqueta">
          <select value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)}>
            {!etiquetas.some((e) => e.name === etiqueta) && <option>{etiqueta}</option>}
            {etiquetas.map((e) => <option key={e.id}>{e.name}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Observações" largura="1 / -1">
          <textarea rows={2} value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Sabores, decoração, recado para a cozinha…" />
        </Campo>
      </div>

      <div className="itens-pedido">
        <div className="itens-cab">
          <span className="sect-t">Produtos</span>
          {!editar && <button type="button" className="btn mini" onClick={adicionarItem}><Icone nome="mais" tam={12} />Adicionar produto</button>}
        </div>
        {itens.map((i, n) => {
          const p = i.product_id ? prodPorId.get(i.product_id) : null;
          return (
            <div className="item-linha" key={i.chave}>
              <span className="item-n">{n + 1}</span>
              <Combo opcoes={opProdutos} valor={i.product_id} onChange={(id) => mudarItem(i.chave, { product_id: id })}
                placeholder="Produto…" autoFocus={!editar && n > 0 && !i.product_id} />
              <input className="qtd" type="number" min={1} max={1000000} value={i.quantity}
                onChange={(e) => mudarItem(i.chave, { quantity: Number(e.target.value) })} aria-label="Quantidade" />
              <span className={`item-estoque${p && p.stock - i.quantity < 0 ? " ruim" : ""}`}>
                {p ? `${p.stock} em estoque` : ""}
              </span>
              {!editar && itens.length > 1
                ? <button type="button" className="icone-btn" onClick={() => setItens((l) => l.filter((x) => x.chave !== i.chave))} aria-label="Remover produto"><Icone nome="lixo" tam={14} /></button>
                : <span />}
            </div>
          );
        })}
        {editar && editar.itens.length > 1 && <p className="nota-rodape">Pedido com vários produtos: entrega, pagamento, etiqueta e observações valem para todos.</p>}
      </div>
      {erro && <p className="form-erro" role="alert">{erro}</p>}
    </Modal>
  );
}

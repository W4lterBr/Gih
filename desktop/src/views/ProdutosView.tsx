import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../contexto";
import type { Produto } from "../types";
import { fmtBRL, fmtInt, fmtTamanho } from "../format";
import { BarraSelecao, Cabecalho, Campo, CampoBusca, Kpi, Modal, Tabela, useCarregar, useDebounce, Vazio, type Coluna } from "../components/ui";
import { Icone } from "../components/Icone";
import { LogsDialog } from "./Dialogos";

export function ProdutoDialog({ produto, onClose, onSalvo }: { produto: Produto | null; onClose: () => void; onSalvo: (msg: string) => void }) {
  const [f, setF] = useState({
    name: produto?.name ?? "", description: produto?.description ?? "",
    price: produto ? String(produto.price ?? 0).replace(".", ",") : "",
    stock: produto?.stock ?? 0, min_stock: produto?.min_stock ?? 0,
  });
  const [tamanhos, setTamanhos] = useState<string[]>(produto?.size ? produto.size.split(",").map((s) => s.trim()).filter(Boolean) : [""]);
  const [erro, setErro] = useState("");
  const varios = tamanhos.filter((t) => t.trim()).length > 1;

  const salvar = async () => {
    if (!f.name.trim()) { setErro("Nome é obrigatório."); return; }
    const preco = Number(String(f.price || "0").replace(/\./g, "").replace(",", "."));
    if (!Number.isFinite(preco) || preco < 0) { setErro("Preço inválido."); return; }
    const corpo = { ...f, price: preco, sizes: tamanhos.map((t) => t.trim()).filter(Boolean) };
    try {
      if (produto) {
        const r = await api.put<{ novos: number[] }>(`/produtos/${produto.id}`, corpo);
        onSalvo(r.novos.length ? `Produto atualizado e ${r.novos.length} novo(s) criado(s).` : "Produto atualizado.");
      } else {
        const r = await api.post<{ ids: number[] }>("/produtos", corpo);
        onSalvo(r.ids.length > 1 ? `${r.ids.length} produtos criados.` : "Produto criado.");
      }
    } catch (e) { setErro((e as Error).message); }
  };

  return (
    <Modal titulo={produto ? "Editar produto" : "Novo produto"} onClose={onClose} largura={560} aoEnviar={salvar}
      rodape={<><button type="button" className="btn" onClick={onClose}>Cancelar</button><button className="btn primary">Salvar</button></>}>
      <div className="form-grid">
        <Campo rotulo="Nome" largura="1 / -1"><input autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Ex.: Bolo de chocolate" /></Campo>
        <Campo rotulo="Descrição" largura="1 / -1"><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Campo>
        <Campo rotulo="Preço (R$)"><input inputMode="decimal" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} placeholder="0,00" /></Campo>
        <Campo rotulo="Estoque" dica={produto && f.stock !== produto.stock ? `Diferença de ${f.stock - produto.stock > 0 ? "+" : ""}${f.stock - produto.stock} vira uma movimentação de ajuste.` : undefined}>
          <input type="number" min={0} max={1000000} value={f.stock} onChange={(e) => setF({ ...f, stock: Number(e.target.value) })} />
        </Campo>
        <Campo rotulo="Estoque mínimo" dica="Avisa quando o estoque chegar neste número.">
          <input type="number" min={0} max={100000} value={f.min_stock} onChange={(e) => setF({ ...f, min_stock: Number(e.target.value) })} />
        </Campo>
        <Campo rotulo="Tamanhos (cm ou texto)" largura="1 / -1"
          dica={varios ? `Cada tamanho vira um produto separado (ex.: "${f.name || "Bolo"} ${tamanhos[0] || "15"}cm"), com o mesmo estoque inicial.` : "Opcional. Um número vira \"cm\" na exibição."}>
          <div className="tamanhos">
            {tamanhos.map((t, i) => (
              <span key={i} className="tam-campo">
                <input value={t} onChange={(e) => setTamanhos((l) => l.map((x, j) => (j === i ? e.target.value : x)))} placeholder={i === 0 ? "Ex.: 15" : "Ex.: 20"} />
                {i > 0 && <button type="button" className="icone-btn" onClick={() => setTamanhos((l) => l.filter((_, j) => j !== i))} aria-label="Remover tamanho"><Icone nome="fechar" tam={12} /></button>}
              </span>
            ))}
            <button type="button" className="btn mini" onClick={() => setTamanhos((l) => [...l, ""])}><Icone nome="mais" tam={12} />Tamanho</button>
          </div>
        </Campo>
      </div>
      {erro && <p className="form-erro">{erro}</p>}
    </Modal>
  );
}

export function ProdutosView({ modo }: { modo: "catalogo" | "pronta" }) {
  const { toast, confirmar, admin, somenteLeitura } = useApp();
  const pronta = modo === "pronta";
  const [q, setQ] = useState("");
  const qd = useDebounce(q);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [soEsgotados, setSoEsgotados] = useState(false);
  const [dialogo, setDialogo] = useState<{ tipo: "editar"; p: Produto | null } | { tipo: "logs"; p: Produto } | null>(null);
  const { dados, recarregar } = useCarregar(() => api.get<{ produtos: Produto[] }>("/produtos", { q: qd, ordem: pronta ? "pronta" : undefined }), [qd, pronta], 5000);
  useEffect(() => { setSel(new Set()); setSoEsgotados(false); }, [modo]);

  const todos = dados?.produtos ?? [];
  const linhas = soEsgotados ? todos.filter((p) => p.stock <= 0 || (p.min_stock > 0 && p.stock <= p.min_stock)) : todos;
  const porId = new Map(linhas.map((p) => [p.id, p]));
  const marcados = [...sel].map((i) => porId.get(i)).filter(Boolean) as Produto[];
  const esgotados = todos.filter((p) => p.stock <= 0).length;
  const baixos = todos.filter((p) => p.stock > 0 && p.min_stock > 0 && p.stock <= p.min_stock).length;
  const unidades = todos.reduce((s, p) => s + Math.max(0, p.stock), 0);
  const valor = todos.reduce((s, p) => s + Math.max(0, p.stock) * (p.price || 0), 0);

  const salvo = async (msg: string) => {
    setDialogo(null); toast(msg); recarregar(true);
    const r = await api.get<{ produtos: Produto[] }>("/produtos/estoque-baixo").catch(() => null);
    if (r?.produtos.length) toast(`Estoque baixo: ${r.produtos.map((p) => `${p.name} (${p.stock})`).join(", ")}`, true);
  };

  const excluir = async () => {
    const ok = await confirmar({
      titulo: marcados.length === 1 ? "Excluir produto" : `Excluir ${marcados.length} produtos`, perigo: true, ok: "Excluir",
      texto: <>{marcados.length === 1 ? <><b>{marcados[0].name}</b> será excluído</> : `${marcados.length} produtos serão excluídos`}, com o histórico de movimentações. Produtos com pedidos não são excluídos.</>,
    });
    if (!ok) return;
    try {
      const r = await api.post<{ excluidos: number; bloqueados: string[] }>("/produtos/excluir", { ids: marcados.map((p) => p.id) });
      if (r.bloqueados.length) toast(`${r.excluidos} excluído(s). Com pedidos vinculados (mantidos): ${r.bloqueados.join(", ")}.`, true);
      else toast(r.excluidos === 1 ? "Produto excluído." : `${r.excluidos} produtos excluídos.`);
      setSel(new Set()); recarregar(true);
    } catch (e) { toast((e as Error).message, true); }
  };

  const estoqueCel = (p: Produto) => p.stock <= 0
    ? <span className="estq esgotado">Esgotado{p.stock < 0 ? ` (${p.stock})` : ""}</span>
    : <span className={`estq${p.min_stock > 0 && p.stock <= p.min_stock ? " baixo" : ""}`}>{fmtInt(p.stock)}</span>;

  const colunas: Coluna<Produto>[] = [
    { id: "nome", titulo: "Produto", largura: "minmax(180px,1.6fr)", ordenar: (p) => p.name,
      render: (p) => <span className="who"><b>{p.name}</b>{p.description && <span className="sutil-sans">{p.description}</span>}</span> },
    { id: "tam", titulo: "Tamanho", largura: "130px", ordenar: (p) => p.size ?? "", render: (p) => fmtTamanho(p.size) },
    ...(!pronta ? [{ id: "preco", titulo: "Preço", largura: "110px", num: true, ordenar: (p: Produto) => p.price, render: (p: Produto) => fmtBRL(p.price) }] : []),
    { id: "estoque", titulo: "Estoque", largura: "120px", num: true, ordenar: (p) => p.stock, render: estoqueCel },
    { id: "min", titulo: "Mínimo", largura: "84px", num: true, ordenar: (p) => p.min_stock, render: (p) => (p.min_stock ? fmtInt(p.min_stock) : <span className="sutil">—</span>) },
    { id: "acoes", titulo: "", largura: admin && !pronta ? "96px" : "60px", render: (p) => (
      <span className="acoes-linha" onClick={(e) => e.stopPropagation()}>
        <button className="icone-btn" title="Editar" onClick={() => setDialogo({ tipo: "editar", p })}><Icone nome="editar" tam={14} /></button>
        {admin && !pronta && <button className="icone-btn" title="Histórico" onClick={() => setDialogo({ tipo: "logs", p })}><Icone nome="historico" tam={14} /></button>}
      </span>
    ) },
  ];

  return (
    <section className="view">
      <Cabecalho titulo={pronta ? "Pronta entrega" : "Produtos"} sub={pronta ? "Estoque disponível agora (atualiza sozinho)" : `${todos.length} produto(s) no catálogo`}>
        {!pronta && <button className="btn primary" onClick={() => setDialogo({ tipo: "editar", p: null })} disabled={somenteLeitura} title={somenteLeitura ? "Licença bloqueada: modo somente leitura" : undefined}><Icone nome="mais" tam={14} />Novo produto</button>}
      </Cabecalho>
      <div className="kpis kpis-4">
        <Kpi rotulo="Unidades em estoque" valor={fmtInt(unidades)} sub={`${todos.length} produtos`} />
        <Kpi rotulo="Esgotados" valor={fmtInt(esgotados)} tom={esgotados ? "alert" : "ok"} sub={esgotados ? "clique para filtrar" : "nenhum"} onClick={() => setSoEsgotados((v) => !v)} />
        <Kpi rotulo="Abaixo do mínimo" valor={fmtInt(baixos)} tom={baixos ? "attn" : undefined} sub="repor em breve" onClick={() => setSoEsgotados((v) => !v)} />
        <Kpi rotulo="Valor em estoque" valor={fmtBRL(valor)} sub="pelo preço de cadastro" />
      </div>
      <div className="filters">
        <CampoBusca valor={q} onChange={setQ} placeholder="Nome ou descrição" />
        <button className="chip" aria-pressed={soEsgotados} onClick={() => setSoEsgotados((v) => !v)}>Só esgotados e baixos <span className="n">{esgotados + baixos}</span></button>
      </div>
      {!pronta && (
        <BarraSelecao n={marcados.length} rotulo={["produto marcado", "produtos marcados"]} onLimpar={() => setSel(new Set())}>
          <button className="btn perigo" onClick={excluir} disabled={somenteLeitura}><Icone nome="lixo" tam={14} />Excluir</button>
        </BarraSelecao>
      )}
      <Tabela linhas={linhas} colunas={colunas} chave={(p) => p.id} selecionadas={pronta ? undefined : sel} onSelecionar={pronta ? undefined : setSel}
        onAbrir={(p) => setDialogo({ tipo: "editar", p })} linhaClasse={(p) => (p.stock <= 0 ? "linha-esgotada" : undefined)}
        vazio={<Vazio icone="produtos" titulo={q ? "Nenhum produto encontrado" : "Nenhum produto cadastrado"} />} />
      {dialogo?.tipo === "editar" && <ProdutoDialog produto={dialogo.p} onClose={() => setDialogo(null)} onSalvo={salvo} />}
      {dialogo?.tipo === "logs" && <LogsDialog entidade="product" id={dialogo.p.id} titulo={dialogo.p.name} onClose={() => setDialogo(null)} />}
    </section>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../contexto";
import type { Produto, Unidade } from "../types";
import { fmtBRL, fmtInt, fmtQtd, fmtTamanho, lerQtd } from "../format";
import { BarraSelecao, Cabecalho, Campo, CampoBusca, Kpi, Modal, Tabela, useCarregar, useDebounce, Vazio, type Coluna } from "../components/ui";
import { Icone } from "../components/Icone";
import { LogsDialog } from "./Dialogos";
import { NovoMovimento } from "./MovimentacaoView";

export function ProdutoDialog({ produto, onClose, onSalvo }: { produto: Produto | null; onClose: () => void; onSalvo: (msg: string) => void }) {
  const [f, setF] = useState({
    name: produto?.name ?? "", description: produto?.description ?? "",
    price: produto ? String(produto.price ?? 0).replace(".", ",") : "",
    stock: String(produto?.stock ?? 0).replace(".", ","), min_stock: String(produto?.min_stock ?? 0).replace(".", ","),
    unit: (produto?.unit ?? "un") as Unidade,
  });
  const kg = f.unit === "kg";
  const estoqueNum = lerQtd(f.stock);
  const [tamanhos, setTamanhos] = useState<string[]>(produto?.size ? produto.size.split(",").map((s) => s.trim()).filter(Boolean) : [""]);
  const [erro, setErro] = useState("");
  const varios = tamanhos.filter((t) => t.trim()).length > 1;

  const salvar = async () => {
    if (!f.name.trim()) { setErro("Nome é obrigatório."); return; }
    const preco = Number(String(f.price || "0").replace(/\./g, "").replace(",", "."));
    if (!Number.isFinite(preco) || preco < 0) { setErro("Preço inválido."); return; }
    // estoque_lido: se o campo não foi mexido, o motor mantém o estoque atual (o painel da cozinha pode ter mudado).
    if (!Number.isFinite(estoqueNum) || estoqueNum < 0 || !Number.isFinite(lerQtd(f.min_stock))) { setErro("Estoque inválido."); return; }
    if (!kg && (!Number.isInteger(estoqueNum) || !Number.isInteger(lerQtd(f.min_stock)))) { setErro("Produto vendido por unidade: estoque em número inteiro."); return; }
    const corpo = { ...f, stock: estoqueNum, min_stock: lerQtd(f.min_stock), price: preco, sizes: tamanhos.map((t) => t.trim()).filter(Boolean), ...(produto ? { estoque_lido: produto.stock } : {}) };
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
        <Campo rotulo="Vendido por" largura="1 / -1" dica={kg ? "Pedidos, estoque e produção em quilos (ex.: 1,5 kg). Preço por kg." : "Pedidos e estoque em unidades inteiras."}>
          <div className="seg">
            <button type="button" aria-pressed={!kg} onClick={() => setF({ ...f, unit: "un" })}>Unidade</button>
            <button type="button" aria-pressed={kg} onClick={() => setF({ ...f, unit: "kg" })}>Quilo (kg)</button>
          </div>
        </Campo>
        <Campo rotulo={kg ? "Preço por kg (R$)" : "Preço (R$)"}><input inputMode="decimal" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} placeholder="0,00" /></Campo>
        <Campo rotulo={`${!produto && varios ? "Estoque de cada tamanho" : "Estoque"}${kg ? " (kg)" : ""}`}
          dica={produto && Number.isFinite(estoqueNum) && estoqueNum !== produto.stock ? `Diferença de ${estoqueNum - produto.stock > 0 ? "+" : ""}${fmtQtd(Math.round((estoqueNum - produto.stock) * 1000) / 1000, f.unit)} vira uma movimentação de ajuste.` : undefined}>
          <input inputMode="decimal" value={f.stock} onChange={(e) => setF({ ...f, stock: e.target.value })} />
        </Campo>
        <Campo rotulo={`Estoque mínimo${kg ? " (kg)" : ""}`} dica="Avisa quando o estoque chegar neste número.">
          <input inputMode="decimal" value={f.min_stock} onChange={(e) => setF({ ...f, min_stock: e.target.value })} />
        </Campo>
        <Campo rotulo="Tamanhos (cm ou texto)" largura="1 / -1"
          dica={varios ? (produto
            ? "Cada tamanho a mais vira um produto separado, começando com estoque 0. Este produto fica com o 1º tamanho e o estoque acima."
            : `Cada tamanho vira um produto separado (ex.: "${f.name || "Bolo"} ${/^\d+([.,]\d+)?$/.test((tamanhos[0] || "15").trim()) ? `${(tamanhos[0] || "15").trim()}cm` : tamanhos[0]}"), cada um com o estoque acima.`)
            : "Opcional. Um número vira \"cm\" na exibição."}>
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
  const { toast, confirmar, admin, somenteLeitura, motivoBloqueio } = useApp();
  const pronta = modo === "pronta";
  const [q, setQ] = useState("");
  const qd = useDebounce(q);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [soEsgotados, setSoEsgotados] = useState(false);
  const [dialogo, setDialogo] = useState<{ tipo: "editar"; p: Produto | null } | { tipo: "logs"; p: Produto } | { tipo: "ajustar"; p: Produto; categorias: Record<"Entrada" | "Saída", string[]> } | null>(null);
  // Cadastro (nome, preço) é do administrador; quem cuida do estoque ajusta por movimentação.
  const { pode } = useApp();
  const editaCadastro = pode("produtos");
  const ajustaEstoque = !editaCadastro && pode("movimentacao");
  const abrir = async (p: Produto) => {
    if (editaCadastro) { setDialogo({ tipo: "editar", p }); return; }
    if (!ajustaEstoque || somenteLeitura) return;
    try {
      const r = await api.get<{ categorias: Record<"Entrada" | "Saída", string[]> }>("/movimentos", { produto: p.id });
      setDialogo({ tipo: "ajustar", p, categorias: r.categorias });
    } catch (e) { toast((e as Error).message, true); }
  };
  const { dados, recarregar } = useCarregar(() => api.get<{ produtos: Produto[] }>("/produtos", { q: qd, ordem: pronta ? "pronta" : undefined }), [qd, pronta], 5000);
  useEffect(() => { setSel(new Set()); setSoEsgotados(false); }, [modo]);

  const todos = dados?.produtos ?? [];
  const linhas = soEsgotados ? todos.filter((p) => p.stock <= 0 || (p.min_stock > 0 && p.stock <= p.min_stock)) : todos;
  const porId = new Map(linhas.map((p) => [p.id, p]));
  const marcados = [...sel].map((i) => porId.get(i)).filter(Boolean) as Produto[];
  const esgotados = todos.filter((p) => p.stock <= 0).length;
  const baixos = todos.filter((p) => p.stock > 0 && p.min_stock > 0 && p.stock <= p.min_stock).length;
  const unidades = todos.reduce((s, p) => s + (p.unit === "kg" ? 0 : Math.max(0, p.stock)), 0);
  const quilos = todos.reduce((s, p) => s + (p.unit === "kg" ? Math.max(0, p.stock) : 0), 0);
  const valor = todos.reduce((s, p) => s + Math.max(0, p.stock) * (p.price || 0), 0);

  const salvo = async (msg: string) => {
    setDialogo(null); toast(msg); recarregar(true);
    const r = await api.get<{ produtos: Produto[] }>("/produtos/estoque-baixo").catch(() => null);
    if (r?.produtos.length) toast(`Estoque baixo: ${r.produtos.map((p) => `${p.name} (${fmtQtd(p.stock, p.unit)})`).join(", ")}`, true);
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
    ? <span className="estq esgotado">Esgotado{p.stock < 0 ? ` (${fmtQtd(p.stock, p.unit)})` : ""}</span>
    : <span className={`estq${p.min_stock > 0 && p.stock <= p.min_stock ? " baixo" : ""}`}>{fmtQtd(p.stock, p.unit)}</span>;

  const colunas: Coluna<Produto>[] = [
    { id: "nome", titulo: "Produto", largura: "minmax(180px,1.6fr)", ordenar: (p) => p.name,
      render: (p) => <span className="who"><b>{p.name}</b>{p.description && <span className="sutil-sans">{p.description}</span>}</span> },
    { id: "tam", titulo: "Tamanho", largura: "130px", ordenar: (p) => p.size ?? "", render: (p) => fmtTamanho(p.size) },
    ...(!pronta ? [{ id: "preco", titulo: "Preço", largura: "120px", num: true, ordenar: (p: Produto) => p.price, render: (p: Produto) => <>{fmtBRL(p.price)}{p.unit === "kg" && <span className="sutil">/kg</span>}</> }] : []),
    { id: "estoque", titulo: "Estoque", largura: "120px", num: true, ordenar: (p) => p.stock, render: estoqueCel },
    { id: "min", titulo: "Mínimo", largura: "84px", num: true, ordenar: (p) => p.min_stock, render: (p) => (p.min_stock ? fmtQtd(p.min_stock, p.unit) : <span className="sutil">—</span>) },
    { id: "acoes", titulo: "", largura: admin && !pronta ? "96px" : "60px", render: (p) => (
      <span className="acoes-linha" onClick={(e) => e.stopPropagation()}>
        {editaCadastro && <button className="icone-btn" title="Editar" onClick={() => abrir(p)}><Icone nome="editar" tam={14} /></button>}
        {ajustaEstoque && <button className="icone-btn" title="Ajustar estoque (entrada ou saída)" disabled={somenteLeitura} onClick={() => abrir(p)}><Icone nome="movimentacao" tam={14} /></button>}
        {admin && !pronta && <button className="icone-btn" title="Histórico" onClick={() => setDialogo({ tipo: "logs", p })}><Icone nome="historico" tam={14} /></button>}
      </span>
    ) },
  ];

  return (
    <section className="view">
      <Cabecalho titulo={pronta ? "Pronta entrega" : "Produtos"} sub={pronta ? "Estoque disponível agora (atualiza sozinho)" : `${todos.length} produto(s) no catálogo`}>
        {!pronta && editaCadastro && <button className="btn primary" onClick={() => setDialogo({ tipo: "editar", p: null })} disabled={somenteLeitura} title={somenteLeitura ? motivoBloqueio : undefined}><Icone nome="mais" tam={14} />Novo produto</button>}
      </Cabecalho>
      <div className="kpis kpis-4">
        <Kpi rotulo="Em estoque" valor={fmtInt(unidades) + " un"} sub={quilos ? `+ ${fmtQtd(Math.round(quilos * 1000) / 1000, "kg")} · ${todos.length} produtos` : `${todos.length} produtos`} />
        <Kpi rotulo="Esgotados" valor={fmtInt(esgotados)} tom={esgotados ? "alert" : "ok"} sub={esgotados ? "clique para filtrar" : "nenhum"} onClick={() => setSoEsgotados((v) => !v)} />
        <Kpi rotulo="Abaixo do mínimo" valor={fmtInt(baixos)} tom={baixos ? "attn" : undefined} sub="repor em breve" onClick={() => setSoEsgotados((v) => !v)} />
        <Kpi rotulo="Valor em estoque" valor={fmtBRL(valor)} sub="pelo preço de cadastro" />
      </div>
      <div className="filters">
        <CampoBusca valor={q} onChange={setQ} placeholder="Nome ou descrição" />
        <button className="chip" aria-pressed={soEsgotados} onClick={() => setSoEsgotados((v) => !v)}>Só esgotados e baixos <span className="n">{esgotados + baixos}</span></button>
      </div>
      {!pronta && editaCadastro && (
        <BarraSelecao n={marcados.length} rotulo={["produto marcado", "produtos marcados"]} onLimpar={() => setSel(new Set())}>
          <button className="btn perigo" onClick={excluir} disabled={somenteLeitura}><Icone nome="lixo" tam={14} />Excluir</button>
        </BarraSelecao>
      )}
      <Tabela linhas={linhas} colunas={colunas} chave={(p) => p.id} selecionadas={pronta || !editaCadastro ? undefined : sel} onSelecionar={pronta || !editaCadastro ? undefined : setSel}
        onAbrir={abrir} linhaClasse={(p) => (p.stock <= 0 ? "linha-esgotada" : undefined)}
        vazio={<Vazio icone="produtos" titulo={q ? "Nenhum produto encontrado" : "Nenhum produto cadastrado"} />} />
      {dialogo?.tipo === "editar" && <ProdutoDialog produto={dialogo.p} onClose={() => setDialogo(null)} onSalvo={salvo} />}
      {dialogo?.tipo === "ajustar" && <NovoMovimento categorias={dialogo.categorias} produtoInicial={dialogo.p.id} onClose={() => setDialogo(null)}
        onSalvo={(msg) => { setDialogo(null); toast(msg); recarregar(true); }} />}
      {dialogo?.tipo === "logs" && <LogsDialog entidade="product" id={dialogo.p.id} titulo={dialogo.p.name} onClose={() => setDialogo(null)} />}
    </section>
  );
}

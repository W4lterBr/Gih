import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, definirAoPerderSessao, useMotor } from "./api";
import { ProvedorApp, useApp } from "./contexto";
import type { Empresa, Usuario, View } from "./types";
import { TitleBar } from "./components/TitleBar";
import { ITENS_CADASTRO, ITENS_OPERACAO, Sidebar } from "./components/Sidebar";
import { Login, TrocaObrigatoria } from "./components/Login";
import { BancoAusente } from "./components/BancoAusente";
import { Palette, type Comando } from "./components/Palette";
import { InicioView } from "./views/InicioView";
import { PedidosView } from "./views/PedidosView";
import { ClientesView } from "./views/ClientesView";
import { ProdutosView } from "./views/ProdutosView";
import { MovimentacaoView } from "./views/MovimentacaoView";
import { ProducaoView } from "./views/ProducaoView";
import { RelatoriosView } from "./views/RelatoriosView";
import { ConfigView } from "./views/ConfigView";
import { FaixaLicenca, useLicenca } from "./licenca";

const CHAVE_TEMA = "confeitaria.tema";
const EMPRESA_PADRAO: Empresa = { nome: "Confeitaria", logo: null, logo_path: null, dias_fechados: [0] };

function temaInicial() {
  try {
    const s = localStorage.getItem(CHAVE_TEMA);
    if (s === "escuro" || s === "claro") return s === "escuro";
  } catch { /* sem storage: segue o Windows */ }
  return matchMedia("(prefers-color-scheme: dark)").matches;
}

export default function App() {
  const { estado, saude, erro } = useMotor();
  const [empresa, setEmpresa] = useState<Empresa | null>(null);
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [lembrado, setLembrado] = useState<string | null>(null);
  const [tentouAuto, setTentouAuto] = useState(false);
  const [escuro, setEscuro] = useState(temaInicial);

  useEffect(() => { document.documentElement.setAttribute("data-theme", escuro ? "dark" : "light"); }, [escuro]);
  const escolherTema = useCallback((e: boolean) => {
    setEscuro(e);
    try { localStorage.setItem(CHAVE_TEMA, e ? "escuro" : "claro"); } catch { /* sem storage */ }
  }, []);

  const carregarEmpresa = useCallback(() => {
    api.get<Empresa>("/empresa").then(setEmpresa).catch(() => setEmpresa(EMPRESA_PADRAO));
  }, []);

  // Motor pronto: empresa + login automático (credenciais lembradas). Segurar Shift
  // ao abrir pula o login automático (para trocar de usuário), como no app antigo.
  useEffect(() => {
    if (estado !== "pronto") return;
    carregarEmpresa();
    if (saude?.usuario) { setUsuario(saude.usuario); setTentouAuto(true); return; }
    const shift = (window as unknown as { __shift?: boolean }).__shift;
    if (shift) { setTentouAuto(true); return; }
    api.post<{ usuario: Usuario | null; lembrado: string | null }>("/login/automatico")
      .then((r) => { setLembrado(r.lembrado); if (r.usuario) setUsuario(r.usuario); })
      .catch(() => {})
      .finally(() => setTentouAuto(true));
  }, [estado, saude, carregarEmpresa]);

  useEffect(() => { definirAoPerderSessao(() => setUsuario(null)); }, []);

  const sair = useCallback(async () => {
    await api.post("/logout", { esquecer: true }).catch(() => {});
    setLembrado(null);
    setUsuario(null);
  }, []);

  if (estado !== "pronto" || !tentouAuto || !empresa) {
    return (
      <div className="window">
        <TitleBar motor={estado} />
        <div className="inicializando">
          {estado === "erro" ? (
            <div className="card notice alerta" style={{ maxWidth: 520 }}>
              <b>O motor da Confeitaria não iniciou</b>
              <p>{erro}</p>
              <p>Feche e abra o sistema de novo. Se continuar, veja o arquivo de log em %LOCALAPPDATA%\Confeitaria\logs\servico_local.log.</p>
            </div>
          ) : (
            <><div className="spinner" /><span>Abrindo o sistema…</span></>
          )}
        </div>
      </div>
    );
  }

  if (saude?.banco_ausente) {
    return (
      <div className="window">
        <TitleBar motor={estado} />
        <BancoAusente caminho={saude.banco_ausente} />
      </div>
    );
  }

  if (!usuario) {
    return (
      <div className="window">
        <TitleBar motor={estado} />
        <Login empresa={empresa} cozinha={saude?.cozinha ?? null} lembrado={lembrado} onEntrar={setUsuario} />
      </div>
    );
  }

  if (usuario.trocar_senha) {
    return (
      <div className="window">
        <TitleBar motor={estado} />
        <TrocaObrigatoria empresa={empresa} usuario={usuario} onSair={sair}
          onTrocada={() => setUsuario({ ...usuario, trocar_senha: false })} />
      </div>
    );
  }

  return <Logado usuario={usuario} empresa={empresa} carregarEmpresa={carregarEmpresa} escuro={escuro} onTema={escolherTema} onSair={sair} cozinha={saude?.cozinha ?? null} />;
}

function Logado({ usuario, empresa, carregarEmpresa, escuro, onTema, onSair, cozinha }: {
  usuario: Usuario; empresa: Empresa; carregarEmpresa: () => void; escuro: boolean; onTema: (e: boolean) => void; onSair: () => void; cozinha: string | null;
}) {
  const { lic, carregar } = useLicenca(0);
  return (
    <ProvedorApp usuario={usuario} empresa={empresa} recarregarEmpresa={carregarEmpresa} licenca={lic} recarregarLicenca={carregar}>
      <Moldura escuro={escuro} onTema={onTema} onSair={onSair} cozinha={cozinha} />
    </ProvedorApp>
  );
}

function Moldura({ escuro, onTema, onSair, cozinha }: { escuro: boolean; onTema: (e: boolean) => void; onSair: () => void; cozinha: string | null }) {
  const { usuario, empresa, toast, versaoDados, dadosMudaram, admin, licenca, recarregarLicenca, somenteLeitura } = useApp();
  const [verificando, setVerificando] = useState(false);
  const verificarLicenca = useCallback(async () => {
    setVerificando(true);
    try {
      const s = await api.post<{ situacao: string; somente_leitura: boolean; erro: string | null }>("/licenca/verificar");
      recarregarLicenca();
      if (s.erro) toast(s.erro, true);
      else toast(s.somente_leitura ? "A DWM ainda não registrou o pagamento. Pagamentos por boleto podem levar até 3 dias úteis." : "Licença confirmada. Obrigado!", s.somente_leitura);
    } catch (e) { toast((e as Error).message, true); }
    finally { setVerificando(false); }
  }, [recarregarLicenca, toast]);
  const [view, setView] = useState<View>("inicio");
  const [palette, setPalette] = useState(false);
  const [novoPedido, setNovoPedido] = useState(false);
  const [contagens, setContagens] = useState<{ pedidosHoje?: number; producao?: number; esgotados?: number }>({});
  const avisoSeq = useRef(0);

  const irPara = useCallback((v: View) => setView(v), []);
  const abrirNovoPedido = useCallback(() => {
    setView("pedidos");
    if (somenteLeitura) { toast("Licença bloqueada: o sistema está em modo somente leitura.", true); return; }
    setNovoPedido(true);
  }, [somenteLeitura, toast]);

  // Contadores do menu e avisos das tarefas de fundo (reserva de estoque, backup).
  useEffect(() => {
    const atualizar = () => {
      if (document.hidden) return;
      api.get<typeof contagens>("/menu").then(setContagens).catch(() => {});
      api.get<{ avisos: { i: number; msg: string }[] }>("/avisos", { desde: avisoSeq.current }).then((r) => {
        for (const a of r.avisos) {
          if (avisoSeq.current) { toast(a.msg); if (a.msg.includes("Licença")) recarregarLicenca(); }
          avisoSeq.current = Math.max(avisoSeq.current, a.i);
        }
        if (!avisoSeq.current) avisoSeq.current = -1;
      }).catch(() => {});
    };
    atualizar();
    const t = setInterval(atualizar, 10000);
    return () => clearInterval(t);
  }, [toast, versaoDados, view, recarregarLicenca]);

  // Atalhos globais.
  useEffect(() => {
    const todas = [...ITENS_OPERACAO, ...ITENS_CADASTRO];
    const k = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;
      const tecla = e.key.toLowerCase();
      const emCampo = !!(e.target as HTMLElement)?.closest?.("input, textarea, select");
      if (ctrl && tecla === "k") { e.preventDefault(); setPalette(true); }
      else if (ctrl && tecla === "n") { e.preventDefault(); abrirNovoPedido(); }
      else if (ctrl && /^[1-8]$/.test(e.key)) { e.preventDefault(); const i = todas.find((x) => x.atalho === e.key); if (i) setView(i.v); }
      else if (e.key === "F5") { e.preventDefault(); dadosMudaram(); }
      else if (e.key === "/" && !emCampo) {
        const busca = document.querySelector<HTMLInputElement>("[data-busca]");
        if (busca) { e.preventDefault(); busca.focus(); }
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [abrirNovoPedido, dadosMudaram]);

  const comandos: Comando[] = useMemo(() => [
    { titulo: "Novo pedido", dica: "Ctrl+N", run: abrirNovoPedido },
    ...[...ITENS_OPERACAO, ...ITENS_CADASTRO].map((i) => ({ titulo: `Ir para ${i.nome}`, dica: i.atalho ? `Ctrl+${i.atalho}` : undefined, run: () => setView(i.v) })),
    ...(admin ? [
      { titulo: "Fazer backup agora", run: () => setView("cfg-banco") },
      { titulo: "Usuários", run: () => setView("cfg-usuarios") },
      { titulo: "Dados da empresa (nome e logo)", run: () => setView("cfg-empresa") },
    ] : []),
    { titulo: "Painel da cozinha (endereço e PIN)", run: () => setView("cfg-cozinha") },
    { titulo: "Licença DWM e faturas", run: () => setView("cfg-licenca") },
    { titulo: "Alternar tema claro/escuro", run: () => onTema(!escuro) },
    { titulo: "Trocar minha senha", run: () => setView("cfg-conta") },
    { titulo: "Recarregar dados", dica: "F5", run: dadosMudaram },
    { titulo: "Sair (trocar de usuário)", run: onSair },
  ], [abrirNovoPedido, admin, escuro, onTema, dadosMudaram, onSair]);

  const buscar = useCallback(() => [] as Comando[], []);
  const consumirNovo = useCallback(() => setNovoPedido(false), []);

  return (
    <div className="window">
      <TitleBar motor="pronto" onPalette={() => setPalette(true)} cozinha={cozinha} onCozinha={() => setView("cfg-cozinha")} />
      <div className="body">
        <Sidebar view={view} onView={irPara} empresa={empresa} usuario={usuario} escuro={escuro} onTema={() => onTema(!escuro)} onSair={onSair} contagens={contagens} />
        <main className="main">
          <FaixaLicenca lic={licenca} admin={admin} empresa={empresa.nome} onAbrir={() => setView("cfg-licenca")} onVerificar={verificarLicenca} verificando={verificando} />
          {view === "inicio" && <InicioView onView={irPara} onNovoPedido={abrirNovoPedido} />}
          {view === "pedidos" && <PedidosView novoPedido={novoPedido} onNovoConsumido={consumirNovo} />}
          {view === "producao" && <ProducaoView />}
          {view === "pronta" && <ProdutosView modo="pronta" />}
          {view === "clientes" && <ClientesView />}
          {view === "produtos" && <ProdutosView modo="catalogo" />}
          {view === "movimentacao" && <MovimentacaoView />}
          {view === "relatorios" && <RelatoriosView />}
          {view.startsWith("cfg-") && <ConfigView view={view} onView={irPara} escuro={escuro} onTema={onTema} />}
          <Palette aberta={palette} onClose={() => setPalette(false)} comandos={comandos} buscar={buscar} />
        </main>
      </div>
      <footer className="statusbar">
        <span>{empresa.nome}</span>
        <span className="sp" />
        {cozinha && <span>Painel da cozinha: <b>{cozinha}</b></span>}
        <span>© {new Date().getFullYear()} DWM Systems</span>
      </footer>
    </div>
  );
}

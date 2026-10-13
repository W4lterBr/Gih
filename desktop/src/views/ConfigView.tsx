import { useState } from "react";
import { abrirUrl, api, escolherAbrir, escolherSalvar, mostrarNoExplorer } from "../api";
import { useApp } from "../contexto";
import type { Usuario, View } from "../types";
import { fmtDataHora, fmtInt, isoLocal, NOMES_DIAS, sigla } from "../format";
import { Campo, Modal, useCarregar } from "../components/ui";
import { Icone } from "../components/Icone";
import { LicencaView } from "./LicencaView";

const ABAS_ADMIN: [View, string][] = [
  ["cfg-empresa", "Empresa"], ["cfg-usuarios", "Usuários"], ["cfg-banco", "Banco e backup"],
  ["cfg-cozinha", "Painel da cozinha"], ["cfg-licenca", "Licença DWM"], ["cfg-aparencia", "Aparência"], ["cfg-conta", "Minha conta"],
];
const ABAS_USUARIO: [View, string][] = [["cfg-cozinha", "Painel da cozinha"], ["cfg-licenca", "Licença DWM"], ["cfg-aparencia", "Aparência"], ["cfg-conta", "Minha conta"]];

export function ConfigView({ view, onView, escuro, onTema }: { view: View; onView: (v: View) => void; escuro: boolean; onTema: (escuro: boolean) => void }) {
  const { admin, pode } = useApp();
  // Endereço do painel web: só para quem entra nele (cozinha; recepção não usa).
  const abas = admin ? ABAS_ADMIN : ABAS_USUARIO.filter(([v]) => v !== "cfg-cozinha" || pode("producao"));
  const atual = abas.some((a) => a[0] === view) ? view : abas[0][0];
  return (
    <section className="view">
      <div className="config-abas">
        <span className="config-titulo">Configurações</span>
        {abas.map(([v, r]) => <button key={v} aria-selected={atual === v} onClick={() => onView(v)}>{r}</button>)}
      </div>
      <div className="pane pad-top">
        {atual === "cfg-empresa" && <Empresa />}
        {atual === "cfg-usuarios" && <Usuarios />}
        {atual === "cfg-banco" && <Banco />}
        {atual === "cfg-cozinha" && <Cozinha />}
        {atual === "cfg-licenca" && <LicencaView />}
        {atual === "cfg-aparencia" && <Aparencia escuro={escuro} onTema={onTema} />}
        {atual === "cfg-conta" && <Conta />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- empresa

function Empresa() {
  const { empresa, recarregarEmpresa, toast, confirmar } = useApp();
  const [nome, setNome] = useState(empresa.nome);
  const salvarNome = async () => {
    try { await api.put("/empresa/nome", { nome }); toast("Nome da empresa atualizado."); recarregarEmpresa(); }
    catch (e) { toast((e as Error).message, true); }
  };
  const trocarLogo = async () => {
    const caminho = await escolherAbrir("Logo da empresa", [{ name: "Imagens", extensions: ["png", "jpg", "jpeg", "bmp", "gif", "svg", "webp"] }]);
    if (!caminho) return;
    try { await api.put("/empresa/logo", { caminho }); toast("Logo atualizada."); recarregarEmpresa(); }
    catch (e) { toast((e as Error).message, true); }
  };
  const fechados = empresa.dias_fechados ?? [];
  const alternarDia = async (d: number) => {
    const dias = fechados.includes(d) ? fechados.filter((x) => x !== d) : [...fechados, d];
    try { await api.put("/empresa/dias-fechados", { dias }); recarregarEmpresa(); }
    catch (e) { toast((e as Error).message, true); }
  };
  const removerLogo = async () => {
    if (!(await confirmar({ titulo: "Remover logo", texto: "Remover a logo da empresa?", ok: "Remover", perigo: true }))) return;
    try { await api.del("/empresa/logo"); toast("Logo removida."); recarregarEmpresa(); }
    catch (e) { toast((e as Error).message, true); }
  };
  return (
    <div className="card">
      <div className="set">
        <div><b>Nome da confeitaria</b><p>Aparece no menu, no login e nos relatórios.</p></div>
        <form className="ctl linha-ctl" onSubmit={(e) => { e.preventDefault(); salvarNome(); }}>
          <input value={nome} onChange={(e) => setNome(e.target.value)} />
          <button className="btn primary" disabled={!nome.trim() || nome === empresa.nome}>Salvar</button>
        </form>
      </div>
      <div className="set">
        <div><b>Logo</b><p>PNG ou JPG, de preferência quadrada. Usada no login, no menu e nos relatórios.</p></div>
        <div className="ctl linha-ctl">
          <span className="logo-previa">{empresa.logo ? <img src={empresa.logo} alt="" /> : <span className="logo-sigla">{sigla(empresa.nome)}</span>}</span>
          <button className="btn" onClick={trocarLogo}><Icone nome="upload" tam={14} />{empresa.logo ? "Trocar" : "Escolher"}</button>
          {empresa.logo && <button className="btn perigo" onClick={removerLogo}>Remover</button>}
        </div>
      </div>
      <div className="set">
        <div><b>Dias sem expediente</b><p>Pedidos não podem ser marcados para entrega nestes dias.</p></div>
        <div className="ctl linha-ctl dias-semana" role="group" aria-label="Dias sem expediente">
          {NOMES_DIAS.map((n, d) => (
            <button key={d} type="button" className="chip" aria-pressed={fechados.includes(d)} onClick={() => alternarDia(d)} title={n}>{n.slice(0, 3)}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- usuários

/** Os mesmos perfis de api/permissoes.py (o motor confere em toda ação). */
const PERFIS: { role: string; nome: string; descricao: string }[] = [
  { role: "admin", nome: "Administrador", descricao: "Tudo: custos, relatórios, usuários, empresa, banco e licença." },
  { role: "recepcao", nome: "Recepção", descricao: "Pedidos e clientes. Vê produção, pronta entrega e produtos. Sem custos nem relatórios." },
  { role: "cozinha", nome: "Cozinha", descricao: "Produção, estoque e painel no celular. Vê os pedidos, sem alterar. Sem clientes nem custos." },
];

function UsuarioDialog({ u, onClose, onSalvo }: { u: Usuario | null; onClose: () => void; onSalvo: () => void }) {
  // Perfil antigo ("common"/"func") continua até o administrador escolher um dos 3.
  const antigo = !!u && !PERFIS.some((p) => p.role === u.role);
  const [f, setF] = useState({ username: u?.username ?? "", password: "", confirmar: "", role: u?.role ?? "" });
  const [erro, setErro] = useState("");
  const salvar = async () => {
    if (f.password !== f.confirmar) { setErro("As senhas não coincidem"); return; }
    if (!f.role) { setErro("Escolha o perfil do usuário."); return; }
    try {
      const corpo = { username: f.username, password: f.password, role: f.role };
      if (u) await api.put(`/usuarios/${u.id}`, corpo); else await api.post("/usuarios", corpo);
      onSalvo();
    } catch (e) { setErro((e as Error).message); }
  };
  return (
    <Modal titulo={u ? "Editar usuário" : "Novo usuário"} onClose={onClose} largura={460} aoEnviar={salvar}
      rodape={<><button type="button" className="btn" onClick={onClose}>Cancelar</button><button className="btn primary">Salvar</button></>}>
      <div className="form-grid">
        <Campo rotulo="Nome de usuário" largura="1 / -1"><input autoFocus value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></Campo>
        <Campo rotulo={u ? "Nova senha" : "Senha"} dica={u ? "Deixe em branco para manter a atual." : "Mínimo de 6 caracteres; evite 123456, admin ou o nome do usuário."}>
          <input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" />
        </Campo>
        <Campo rotulo="Confirmar senha"><input type="password" value={f.confirmar} onChange={(e) => setF({ ...f, confirmar: e.target.value })} autoComplete="new-password" /></Campo>
        <Campo rotulo="Perfil" largura="1 / -1" erro={antigo && f.role === u?.role ? "Perfil da versão antiga (acesso completo, menos administração). Escolha Recepção ou Cozinha." : undefined}>
          <div className="perfis">
            {PERFIS.map((p) => (
              <button type="button" key={p.role} className="perfil-opcao" aria-pressed={f.role === p.role} onClick={() => setF({ ...f, role: p.role })}>
                <b>{p.nome}</b><span>{p.descricao}</span>
              </button>
            ))}
          </div>
        </Campo>
      </div>
      {erro && <p className="form-erro">{erro}</p>}
    </Modal>
  );
}

function Usuarios() {
  const { toast, confirmar, usuario } = useApp();
  const { dados, recarregar } = useCarregar(() => api.get<{ usuarios: Usuario[] }>("/usuarios"), []);
  const [ed, setEd] = useState<{ u: Usuario | null } | null>(null);
  const excluir = async (u: Usuario) => {
    if (!(await confirmar({ titulo: "Excluir usuário", texto: <>Excluir o usuário <b>{u.username}</b>?</>, ok: "Excluir", perigo: true }))) return;
    try { await api.del(`/usuarios/${u.id}`); toast("Usuário excluído."); recarregar(true); }
    catch (e) { toast((e as Error).message, true); }
  };
  return (
    <>
      <div className="card">
        {dados?.usuarios.map((u) => (
          <div className="cert-linha" key={u.id}>
            <span className="av conta-av">{sigla(u.username)}</span>
            <div className="cert-info"><b>{u.username}{u.id === usuario.id && <span className="tag-leitura">você</span>}</b><span className="meta">{u.perfil ?? u.role}</span></div>
            <div className="cert-acoes">
              <button className="btn" onClick={() => setEd({ u })}>Editar</button>
              <button className="btn perigo" onClick={() => excluir(u)} disabled={u.id === usuario.id}>Excluir</button>
            </div>
          </div>
        ))}
      </div>
      <div><button className="btn primary" onClick={() => setEd({ u: null })}><Icone nome="mais" tam={14} />Novo usuário</button></div>
      {ed && <UsuarioDialog u={ed.u} onClose={() => setEd(null)} onSalvo={() => { setEd(null); toast("Usuário salvo."); recarregar(true); }} />}
    </>
  );
}

// ---------------------------------------------------------------- banco e backup

interface InfoBanco {
  caminho: string; tamanho: number; modificado: string | null; rede: boolean; journal: string;
  contagens: { clientes: number; produtos: number; pedidos: number };
  pasta_backups: string; backups: { nome: string; caminho: string; tamanho: number; data: string }[];
  auto_backup: { enabled: boolean; interval_hours: number }; ultimo_backup_auto: string | null;
}

const mb = (b: number) => `${(b / 1048576).toFixed(b < 1048576 ? 2 : 1)} MB`;

function Banco() {
  const { toast, confirmar, dadosMudaram } = useApp();
  const { dados, recarregar } = useCarregar(() => api.get<InfoBanco>("/banco"), []);
  const [ocupado, setOcupado] = useState("");

  const executar = async (rotulo: string, fn: () => Promise<void>) => {
    setOcupado(rotulo);
    try { await fn(); } catch (e) { toast((e as Error).message, true); } finally { setOcupado(""); recarregar(true); }
  };

  const backupAgora = () => executar("backup", async () => {
    const r = await api.post<{ caminho: string; tamanho: number }>("/banco/backup", {});
    toast(`Backup criado (${mb(r.tamanho)}).`);
  });
  const backupEmOutroLugar = async () => {
    const caminho = await escolherSalvar(`backup_confeitaria_${isoLocal()}.zip`, [{ name: "Backup", extensions: ["zip"] }]);
    if (caminho) executar("backup", async () => { await api.post("/banco/backup", { caminho }); toast("Backup salvo."); });
  };
  const restaurar = async (caminho?: string) => {
    const arq = caminho ?? (await escolherAbrir("Restaurar backup", [{ name: "Backup (.zip ou .db)", extensions: ["zip", "db"] }]));
    if (!arq) return;
    const ok = await confirmar({
      titulo: "Restaurar backup", perigo: true, ok: "Restaurar",
      texto: <>Os dados atuais serão substituídos pelos do backup.<br />Antes, um backup de segurança do estado atual é salvo automaticamente.</>,
    });
    if (!ok) return;
    executar("restaurar", async () => {
      const r = await api.post<{ seguranca: string }>("/banco/restaurar", { caminho: arq });
      toast("Backup restaurado. Backup de segurança salvo.");
      void r;
      dadosMudaram();
    });
  };
  const verificar = () => executar("verificar", async () => {
    const r = await api.post<{ ok: boolean; detalhes: string[] }>("/banco/verificar");
    toast(r.ok ? "Banco íntegro: nenhum problema encontrado." : `Problemas encontrados: ${r.detalhes.slice(0, 3).join("; ")}`, !r.ok);
  });
  const reparar = async () => {
    if (!(await confirmar({ titulo: "Reparar banco", texto: "Se o banco estiver corrompido, ele será reconstruído. Um backup é feito antes.", ok: "Verificar e reparar" }))) return;
    executar("reparar", async () => { const r = await api.post<{ mensagem: string }>("/banco/reparar"); toast(r.mensagem); dadosMudaram(); });
  };
  const usarOutro = async (criar: boolean) => {
    const caminho = criar
      ? await escolherSalvar("confeitaria_novo.db", [{ name: "Banco de dados", extensions: ["db"] }])
      : await escolherAbrir("Usar outro banco de dados", [{ name: "Banco de dados", extensions: ["db"] }]);
    if (!caminho) return;
    const ok = await confirmar({
      titulo: criar ? "Criar banco novo" : "Trocar de banco", ok: criar ? "Criar e usar" : "Usar este banco",
      texto: <>O sistema passa a usar <span className="caminho">{caminho}</span>{criar ? " (vazio)." : "."} O banco atual não é apagado.</>,
    });
    if (!ok) return;
    executar("trocar", async () => { await api.post("/banco/usar", { caminho, criar }); toast("Banco trocado."); dadosMudaram(); });
  };
  const salvarAuto = (enabled: boolean, interval_hours: number) =>
    api.put("/banco/backup-automatico", { enabled, interval_hours }).then(() => { toast("Backup automático atualizado."); recarregar(true); }).catch((e) => toast(e.message, true));

  if (!dados) return <div className="loading">Carregando…</div>;
  return (
    <>
      <div className="kpis kpis-4 sem-pad">
        <div className="kpi"><label>Pedidos</label><strong>{fmtInt(dados.contagens.pedidos)}</strong></div>
        <div className="kpi"><label>Clientes</label><strong>{fmtInt(dados.contagens.clientes)}</strong></div>
        <div className="kpi"><label>Produtos</label><strong>{fmtInt(dados.contagens.produtos)}</strong></div>
        <div className="kpi"><label>Tamanho</label><strong>{mb(dados.tamanho)}</strong><span className="sub">{dados.rede ? "na rede" : "neste computador"}</span></div>
      </div>
      <div className="card">
        <div className="set">
          <div><b>Arquivo em uso</b><p className="caminho">{dados.caminho}</p></div>
          <div className="ctl linha-ctl">
            <button className="btn" onClick={() => mostrarNoExplorer(dados.caminho).catch((e) => toast(e.message, true))}>Mostrar na pasta</button>
          </div>
        </div>
        <div className="set">
          <div><b>Backup agora</b><p>Cópia completa do banco e das configurações num arquivo .zip.</p></div>
          <div className="ctl linha-ctl">
            <button className="btn" onClick={backupEmOutroLugar} disabled={!!ocupado}>Salvar em…</button>
            <button className="btn primary" onClick={backupAgora} disabled={!!ocupado}><Icone nome="download" tam={14} />{ocupado === "backup" ? "Fazendo…" : "Fazer backup"}</button>
          </div>
        </div>
        <div className="set">
          <div><b>Backup automático</b><p>{dados.auto_backup.enabled ? `A cada ${dados.auto_backup.interval_hours} h enquanto o sistema está aberto${dados.ultimo_backup_auto ? ` · último: ${fmtDataHora(dados.ultimo_backup_auto)}` : ""}.` : "Desligado."}</p></div>
          <div className="ctl linha-ctl">
            <select value={dados.auto_backup.interval_hours} disabled={!dados.auto_backup.enabled} onChange={(e) => salvarAuto(true, Number(e.target.value))}>
              {[1, 2, 4, 6, 12, 24].map((h) => <option key={h} value={h}>a cada {h} h</option>)}
            </select>
            <button className="switch" role="switch" aria-checked={dados.auto_backup.enabled} aria-label="Backup automático"
              onClick={() => salvarAuto(!dados.auto_backup.enabled, dados.auto_backup.interval_hours)} />
          </div>
        </div>
        <div className="set">
          <div><b>Restaurar</b><p>Volta os dados para um backup (.zip ou .db). O estado atual é guardado antes.</p></div>
          <div className="ctl"><button className="btn" onClick={() => restaurar()} disabled={!!ocupado}><Icone nome="upload" tam={14} />Escolher backup…</button></div>
        </div>
      </div>

      <div className="card">
        <div className="card-cab"><b>Backups recentes</b><button className="link" onClick={() => mostrarNoExplorer(dados.backups[0]?.caminho ?? dados.pasta_backups).catch(() => {})}>Abrir pasta</button></div>
        {dados.backups.length === 0 ? <p className="hist-vazio pad">Nenhum backup ainda.</p> : (
          <div className="tabela-logs pad-h">
            {dados.backups.slice(0, 8).map((b) => (
              <div className="log-linha log-backup" key={b.caminho}>
                <span>{fmtDataHora(b.data)}</span>
                <span className="path" title={b.caminho}>{b.nome}</span>
                <span className="num">{mb(b.tamanho)}</span>
                <button className="btn mini" onClick={() => restaurar(b.caminho)} disabled={!!ocupado}>Restaurar</button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="set">
          <div><b>Verificar integridade</b><p>Confere se o arquivo do banco está saudável.</p></div>
          <div className="ctl linha-ctl">
            <button className="btn" onClick={verificar} disabled={!!ocupado}>Verificar</button>
            <button className="btn" onClick={reparar} disabled={!!ocupado}>Reparar</button>
          </div>
        </div>
        <div className="set">
          <div><b>Usar outro banco</b><p>Abrir um arquivo .db existente (inclusive numa pasta compartilhada da rede, \\PC\pasta\confeitaria.db) ou começar um banco vazio.</p></div>
          <div className="ctl linha-ctl">
            <button className="btn" onClick={() => usarOutro(false)} disabled={!!ocupado}>Abrir arquivo…</button>
            <button className="btn" onClick={() => usarOutro(true)} disabled={!!ocupado}>Criar novo…</button>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------- painel da cozinha

interface Aparelho { id: number; usuario: string; lembrar: boolean; entrou: string; ultimo_uso: string; ip: string | null; aparelho: string | null }

/** "Mozilla/5.0 (Linux; Android 14; SM-A546E) …" -> "Android"; só para reconhecer o aparelho. */
function nomeAparelho(ua: string | null) {
  const u = ua ?? "";
  if (/iPhone|iPad/i.test(u)) return /iPad/i.test(u) ? "iPad" : "iPhone";
  if (/Android/i.test(u)) return "Android";
  if (/Windows/i.test(u)) return "Windows";
  if (/Mac OS/i.test(u)) return "Mac";
  return "Navegador";
}

function Cozinha() {
  const { toast, admin, confirmar } = useApp();
  const { dados, recarregar } = useCarregar(() => api.get<{ url: string; local: string; aparelhos?: Aparelho[] }>("/painel-cozinha"), []);
  if (!dados) return <div className="loading">Carregando…</div>;
  const copiar = (t: string) => navigator.clipboard.writeText(t).then(() => toast("Copiado."), () => toast("Não foi possível copiar.", true));
  const desconectar = async (a: Aparelho | null) => {
    const ok = await confirmar({ titulo: a ? "Desconectar aparelho" : "Desconectar todos", ok: "Desconectar", perigo: true,
      texto: a ? <>O aparelho de <b>{a.usuario}</b> ({nomeAparelho(a.aparelho)}) vai pedir usuário e senha de novo.</> : "Todos os aparelhos vão pedir usuário e senha de novo." });
    if (!ok) return;
    try { await api.post("/painel-cozinha/desconectar", a ? { id: a.id } : { todos: true }); toast("Desconectado."); recarregar(true); }
    catch (e) { toast((e as Error).message, true); }
  };
  return (
    <div className="card">
      <div className="set">
        <div><b>Endereço para o celular ou tablet</b><p>Conecte o aparelho na mesma rede Wi-Fi deste computador e abra no navegador.</p></div>
        <div className="ctl linha-ctl">
          <code className="codigo">{dados.url}</code>
          <button className="btn" onClick={() => copiar(dados.url)}><Icone nome="copiar" tam={14} />Copiar</button>
        </div>
      </div>
      <div className="set">
        <div><b>Acesso com usuário e senha</b><p>Entram no painel os perfis <b>Cozinha</b> e <b>Administrador</b> (Recepção não). Marcando "Manter conectado", o aparelho fica conectado por 30 dias desde o último uso. Trocar a senha, o perfil ou o nome do usuário desconecta os aparelhos dele.</p></div>
      </div>
      <div className="set">
        <div><b>Abrir neste computador</b><p>Mesmo painel que a cozinha usa: lista de produção e pronta entrega.</p></div>
        <div className="ctl"><button className="btn" onClick={() => abrirUrl(dados.local)}><Icone nome="externo" tam={14} />Abrir painel</button></div>
      </div>
      {admin && dados.aparelhos && (
        <div className="set set-coluna">
          <div className="set-cab">
            <div><b>Aparelhos conectados</b><p>{dados.aparelhos.length ? `${dados.aparelhos.length} sessão(ões) ativa(s).` : "Nenhum aparelho conectado agora."}</p></div>
            {dados.aparelhos.length > 1 && <button className="btn perigo" onClick={() => desconectar(null)}>Desconectar todos</button>}
          </div>
          {dados.aparelhos.map((a) => (
            <div className="cert-linha" key={a.id}>
              <span className="av conta-av"><Icone nome="celular" tam={14} /></span>
              <div className="cert-info"><b>{a.usuario} · {nomeAparelho(a.aparelho)}</b>
                <span className="meta">{a.ip ?? "—"} · último uso {fmtDataHora(a.ultimo_uso)} · {a.lembrar ? "mantém conectado" : "até fechar o navegador"}</span></div>
              <div className="cert-acoes"><button className="btn" onClick={() => desconectar(a)}>Desconectar</button></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- aparência e conta

function Aparencia({ escuro, onTema }: { escuro: boolean; onTema: (e: boolean) => void }) {
  return (
    <div className="card">
      <div className="set">
        <div><b>Tema</b><p>Fica salvo neste computador.</p></div>
        <div className="ctl">
          <div className="seg">
            <button aria-pressed={!escuro} onClick={() => onTema(false)}><Icone nome="sol" tam={14} /> Claro</button>
            <button aria-pressed={escuro} onClick={() => onTema(true)}><Icone nome="lua" tam={14} /> Escuro</button>
          </div>
        </div>
      </div>
      <div className="set">
        <div><b>Atalhos</b><p><span className="kbd">Ctrl K</span> comandos · <span className="kbd">Ctrl N</span> novo pedido · <span className="kbd">Ctrl 1</span>–<span className="kbd">9</span> telas · <span className="kbd">/</span> buscar · <span className="kbd">F5</span> recarregar · <span className="kbd">Del</span> excluir marcados</p></div>
      </div>
    </div>
  );
}

function Conta() {
  const { usuario, toast } = useApp();
  const [f, setF] = useState({ atual: "", nova: "", confirmar: "" });
  const salvar = async () => {
    if (f.nova !== f.confirmar) { toast("As senhas não coincidem.", true); return; }
    try { await api.put("/minha-senha", { atual: f.atual, nova: f.nova }); toast("Senha alterada."); setF({ atual: "", nova: "", confirmar: "" }); }
    catch (e) { toast((e as Error).message, true); }
  };
  return (
    <div className="card">
      <div className="set">
        <div><b>{usuario.username}</b><p>{usuario.role === "admin" ? "Administrador" : "Usuário"}</p></div>
      </div>
      <form className="form" onSubmit={(e) => { e.preventDefault(); salvar(); }}>
        <b>Trocar minha senha</b>
        <div className="form-linha tres">
          <label>Senha atual<input type="password" value={f.atual} onChange={(e) => setF({ ...f, atual: e.target.value })} autoComplete="current-password" /></label>
          <label>Nova senha<input type="password" value={f.nova} onChange={(e) => setF({ ...f, nova: e.target.value })} autoComplete="new-password" /></label>
          <label>Confirmar<input type="password" value={f.confirmar} onChange={(e) => setF({ ...f, confirmar: e.target.value })} autoComplete="new-password" /></label>
        </div>
        <div><button className="btn primary" disabled={!f.atual || f.nova.length < 6}>Salvar senha</button></div>
      </form>
    </div>
  );
}

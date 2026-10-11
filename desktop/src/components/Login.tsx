import { useEffect, useRef, useState } from "react";
import { api, ErroMotor } from "../api";
import type { Empresa, Usuario } from "../types";
import { sigla } from "../format";

interface Props {
  empresa: Empresa | null;
  cozinha: string | null;
  lembrado: string | null;
  onEntrar: (u: Usuario) => void;
}

/** Tela de login (o motor confere a senha, com bloqueio após tentativas erradas).
 *  "Trocar senha" troca sem entrar no sistema (pede a senha atual). */
export function Login({ empresa, cozinha, lembrado, onEntrar }: Props) {
  const [modo, setModo] = useState<"entrar" | "trocar">("entrar");
  const [usuario, setUsuario] = useState(lembrado ?? "");
  const [senha, setSenha] = useState("");
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [lembrar, setLembrar] = useState(!!lembrado);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [enviando, setEnviando] = useState(false);
  const campoSenha = useRef<HTMLInputElement>(null);
  const campoUsuario = useRef<HTMLInputElement>(null);

  useEffect(() => { (usuario ? campoSenha : campoUsuario).current?.focus(); }, [modo]); // eslint-disable-line react-hooks/exhaustive-deps

  const trocarModo = (m: "entrar" | "trocar") => { setModo(m); setErro(""); setAviso(""); setSenha(""); setNova(""); setConfirmar(""); };

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usuario.trim() || !senha) { setErro(modo === "entrar" ? "Informe usuário e senha." : "Informe usuário e senha atual."); return; }
    if (modo === "trocar" && nova !== confirmar) { setErro("A confirmação não confere com a senha nova."); return; }
    setEnviando(true);
    setErro("");
    try {
      if (modo === "entrar") {
        const r = await api.post<{ usuario: Usuario }>("/login", { usuario: usuario.trim(), senha, lembrar });
        onEntrar(r.usuario);
      } else {
        await api.post("/login/trocar-senha", { usuario: usuario.trim(), atual: senha, nova });
        trocarModo("entrar");
        setAviso("Senha trocada. Entre com a senha nova.");
      }
    } catch (e) {
      setErro((e as ErroMotor).message);
      setSenha("");
      campoSenha.current?.focus();
    } finally {
      setEnviando(false);
    }
  };

  const nome = empresa?.nome ?? "Confeitaria";
  return (
    <div className="login">
      <form className="login-card" onSubmit={enviar}>
        <div className="login-logo">
          {empresa?.logo ? <img src={empresa.logo} alt="" /> : <span className="logo-sigla grande">{sigla(nome)}</span>}
        </div>
        <h1>{nome}</h1>
        <p className="login-sub">{modo === "entrar" ? "Entre com seu usuário para continuar" : "Trocar senha"}</p>
        <label className="campo">
          <span>Usuário</span>
          <input ref={campoUsuario} value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" placeholder="Digite seu usuário" />
        </label>
        <label className="campo">
          <span>{modo === "entrar" ? "Senha" : "Senha atual"}</span>
          <input ref={campoSenha} type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password"
            placeholder={modo === "entrar" ? "Digite sua senha" : "Senha que você usa hoje"} />
        </label>
        {modo === "trocar" && (
          <>
            <label className="campo">
              <span>Senha nova</span>
              <input type="password" value={nova} onChange={(e) => setNova(e.target.value)} autoComplete="new-password" placeholder="Mínimo de 6 caracteres" />
            </label>
            <label className="campo">
              <span>Confirmar senha nova</span>
              <input type="password" value={confirmar} onChange={(e) => setConfirmar(e.target.value)} autoComplete="new-password" />
            </label>
          </>
        )}
        {modo === "entrar" && (
          <label className="opcao lembrar">
            <input type="checkbox" checked={lembrar} onChange={(e) => setLembrar(e.target.checked)} />
            Lembrar neste computador
          </label>
        )}
        {aviso && <p className="form-ok" role="status">{aviso}</p>}
        {erro && <p className="form-erro" role="alert">{erro}</p>}
        <button className="btn primary grande" disabled={enviando}>
          {enviando ? (modo === "entrar" ? "Entrando…" : "Trocando…") : modo === "entrar" ? "Entrar" : "Trocar senha"}
        </button>
        <button type="button" className="link login-link" onClick={() => trocarModo(modo === "entrar" ? "trocar" : "entrar")}>
          {modo === "entrar" ? "Trocar senha" : "Voltar para o login"}
        </button>
        {cozinha && <p className="login-rodape">Painel da cozinha: <b>{cozinha}</b></p>}
      </form>
    </div>
  );
}

/** Depois de entrar com a senha padrão (ou fraca): só segue depois de definir outra. */
export function TrocaObrigatoria({ empresa, usuario, onTrocada, onSair }: {
  empresa: Empresa | null; usuario: Usuario; onTrocada: () => void; onSair: () => void;
}) {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (nova !== confirmar) { setErro("A confirmação não confere com a senha nova."); return; }
    setEnviando(true);
    setErro("");
    try {
      await api.put("/minha-senha", { atual, nova });
      onTrocada();
    } catch (e) {
      setErro((e as ErroMotor).message);
    } finally {
      setEnviando(false);
    }
  };

  const nome = empresa?.nome ?? "Confeitaria";
  return (
    <div className="login">
      <form className="login-card" onSubmit={enviar}>
        <div className="login-logo">
          {empresa?.logo ? <img src={empresa.logo} alt="" /> : <span className="logo-sigla grande">{sigla(nome)}</span>}
        </div>
        <h1>Defina uma nova senha</h1>
        <p className="login-sub">
          O usuário <b>{usuario.username}</b> está com a senha padrão ou fácil demais. Por segurança, escolha outra antes de continuar.
        </p>
        <label className="campo">
          <span>Senha atual</span>
          <input type="password" autoFocus value={atual} onChange={(e) => setAtual(e.target.value)} autoComplete="current-password" />
        </label>
        <label className="campo">
          <span>Senha nova</span>
          <input type="password" value={nova} onChange={(e) => setNova(e.target.value)} autoComplete="new-password" placeholder="Mínimo de 6 caracteres" />
        </label>
        <label className="campo">
          <span>Confirmar senha nova</span>
          <input type="password" value={confirmar} onChange={(e) => setConfirmar(e.target.value)} autoComplete="new-password" />
        </label>
        <p className="login-dica">Evite senhas como 123456, admin ou o próprio nome de usuário.</p>
        {erro && <p className="form-erro" role="alert">{erro}</p>}
        <button className="btn primary grande" disabled={enviando || !atual || !nova}>{enviando ? "Salvando…" : "Salvar e entrar"}</button>
        <button type="button" className="link login-link" onClick={onSair}>Sair</button>
      </form>
    </div>
  );
}

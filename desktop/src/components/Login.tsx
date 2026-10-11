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

/** Tela de login (o motor confere a senha, com bloqueio após tentativas erradas). */
export function Login({ empresa, cozinha, lembrado, onEntrar }: Props) {
  const [usuario, setUsuario] = useState(lembrado ?? "");
  const [senha, setSenha] = useState("");
  const [lembrar, setLembrar] = useState(!!lembrado);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const campoSenha = useRef<HTMLInputElement>(null);
  const campoUsuario = useRef<HTMLInputElement>(null);

  useEffect(() => { (lembrado ? campoSenha : campoUsuario).current?.focus(); }, [lembrado]);

  const entrar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usuario.trim() || !senha) { setErro("Informe usuário e senha."); return; }
    setEnviando(true);
    setErro("");
    try {
      const r = await api.post<{ usuario: Usuario }>("/login", { usuario: usuario.trim(), senha, lembrar });
      onEntrar(r.usuario);
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
      <form className="login-card" onSubmit={entrar}>
        <div className="login-logo">
          {empresa?.logo ? <img src={empresa.logo} alt="" /> : <span className="logo-sigla grande">{sigla(nome)}</span>}
        </div>
        <h1>{nome}</h1>
        <p className="login-sub">Entre com seu usuário para continuar</p>
        <label className="campo">
          <span>Usuário</span>
          <input ref={campoUsuario} value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" placeholder="Digite seu usuário" />
        </label>
        <label className="campo">
          <span>Senha</span>
          <input ref={campoSenha} type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" placeholder="Digite sua senha" />
        </label>
        <label className="opcao lembrar">
          <input type="checkbox" checked={lembrar} onChange={(e) => setLembrar(e.target.checked)} />
          Lembrar neste computador
        </label>
        {erro && <p className="form-erro" role="alert">{erro}</p>}
        <button className="btn primary grande" disabled={enviando}>{enviando ? "Entrando…" : "Entrar"}</button>
        {cozinha && <p className="login-rodape">Painel da cozinha: <b>{cozinha}</b></p>}
      </form>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, escolherAbrir } from "../api";
import { fmtDataHora } from "../format";

interface Info { caminho: string; backups: { nome: string; caminho: string; tamanho: number; data: string }[] }

/**
 * O banco configurado não existe mais (apagado, movido, pasta da rede fora do ar).
 * O motor não cria um banco vazio sozinho: aqui o usuário escolhe o que fazer.
 */
export function BancoAusente({ caminho }: { caminho: string }) {
  const [info, setInfo] = useState<Info | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [confirmarVazio, setConfirmarVazio] = useState(false);

  useEffect(() => { api.get<Info>("/banco/ausente").then(setInfo).catch(() => {}); }, []);

  const agir = async (acao: string, arquivo?: string) => {
    setOcupado(true);
    setErro("");
    try {
      await api.post("/banco/localizar", { acao, caminho: arquivo });
      window.location.reload();
    } catch (e) {
      setErro((e as Error).message);
      setOcupado(false);
    }
  };
  const procurar = async () => {
    const c = await escolherAbrir("Onde está o banco de dados?", [{ name: "Banco de dados", extensions: ["db"] }]);
    if (c) agir("abrir", c);
  };
  const restaurar = async (arquivo?: string) => {
    const c = arquivo ?? (await escolherAbrir("Restaurar backup", [{ name: "Backup (.zip ou .db)", extensions: ["zip", "db"] }]));
    if (c) agir("restaurar", c);
  };

  return (
    <div className="login">
      <div className="login-card banco-ausente">
        <h1>Banco de dados não encontrado</h1>
        <p className="login-sub">O sistema está configurado para usar este arquivo, mas ele não existe mais:</p>
        <p className="caminho">{caminho}</p>
        <p className="login-dica">Se ele fica numa pasta da rede, confira se o outro computador está ligado e tente de novo. Nada foi apagado nem criado.</p>
        <button className="btn primary grande" disabled={ocupado} onClick={() => agir("tentar")}>Tentar de novo</button>
        <button className="btn grande" disabled={ocupado} onClick={procurar}>Procurar o arquivo…</button>
        <button className="btn grande" disabled={ocupado} onClick={() => restaurar()}>Restaurar um backup…</button>
        {info && info.backups.length > 0 && (
          <div className="backups-ausente">
            <span className="login-dica">Backups neste computador:</span>
            {info.backups.map((b) => (
              <button key={b.caminho} className="link" disabled={ocupado} onClick={() => restaurar(b.caminho)} title={b.caminho}>
                {fmtDataHora(b.data)} · {b.nome}
              </button>
            ))}
          </div>
        )}
        {confirmarVazio ? (
          <p className="form-erro">
            Começar com um banco vazio (sem pedidos, clientes nem produtos)?{" "}
            <button className="link" disabled={ocupado} onClick={() => agir("criar")}>Sim, começar vazio</button>{" · "}
            <button className="link" onClick={() => setConfirmarVazio(false)}>Cancelar</button>
          </p>
        ) : (
          <button className="link login-link" disabled={ocupado} onClick={() => setConfirmarVazio(true)}>Começar um banco vazio neste local</button>
        )}
        {erro && <p className="form-erro" role="alert">{erro}</p>}
      </div>
    </div>
  );
}

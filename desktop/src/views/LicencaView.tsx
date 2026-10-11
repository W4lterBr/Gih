import { useState } from "react";
import { abrirUrl, api } from "../api";
import { useApp } from "../contexto";
import { abrirSuporte, type Licenca } from "../licenca";
import { fmtBRL, fmtData } from "../format";
import { Icone } from "../components/Icone";

const SITUACAO_TEXTO: Record<Licenca["situacao"], { rotulo: string; cls: string }> = {
  sem_token: { rotulo: "Não ativada", cls: "neutro" },
  liberado: { rotulo: "Em dia", cls: "ok" },
  tolerancia: { rotulo: "Fatura vencida (em tolerância)", cls: "warn" },
  bloqueado: { rotulo: "Bloqueada — somente leitura", cls: "bad" },
  sem_conexao: { rotulo: "Sem conexão (vale a última confirmação)", cls: "warn" },
};

/** "2026-10-11T15:02:11+00:00" -> "11/10/2026 12:02" (horário local). */
function quandoLocal(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/** Configurações → Licença DWM: situação das faturas na DWM e ativação do token. */
export function LicencaView() {
  const { licenca, recarregarLicenca, admin, toast, confirmar, empresa } = useApp();
  const [token, setToken] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [trocar, setTrocar] = useState(false);
  const l = licenca;

  const ativar = async () => {
    setOcupado(true);
    try {
      const s = await api.post<Licenca>("/licenca/ativar", { token });
      toast(s.situacao === "bloqueado" ? "Token aceito, mas a licença está bloqueada na DWM." : "Licença ativada.", s.situacao === "bloqueado");
      setToken("");
      setTrocar(false);
      recarregarLicenca();
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setOcupado(false);
    }
  };

  const verificar = async () => {
    setOcupado(true);
    try {
      const s = await api.post<Licenca>("/licenca/verificar");
      recarregarLicenca();
      toast(s.erro ?? "Situação atualizada.", !!s.erro);
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setOcupado(false);
    }
  };

  const remover = async () => {
    const ok = await confirmar({
      titulo: "Remover licença deste computador", perigo: true, ok: "Remover",
      texto: "O token de licença sai deste computador. Para voltar a usar a licença será preciso digitá-lo de novo.",
    });
    if (!ok) return;
    try {
      await api.post("/licenca/remover");
      toast("Licença removida deste computador.");
      recarregarLicenca();
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  if (!l) return <div className="loading">Carregando…</div>;
  const sit = SITUACAO_TEXTO[l.situacao];
  const d = l.dados;
  const pedeToken = l.situacao === "sem_token" || l.motivo === "token_ausente" || l.motivo === "token_invalido" || trocar;

  return (
    <>
      <div className="card">
        <div className="set">
          <div>
            <b>Situação</b>
            <p><span className={`conta-sit ${sit.cls}`}><i />{sit.rotulo}</span></p>
            {l.mensagem && <p>{l.mensagem}</p>}
          </div>
          <div className="ctl linha-ctl">
            {l.situacao !== "sem_token" && (
              <button className="btn" onClick={verificar} disabled={ocupado}><Icone nome="reload" tam={14} />Verificar agora</button>
            )}
            {(d?.fatura_vencida || d?.proxima_fatura) && (
              <button className="btn primary" onClick={() => abrirUrl(l.portal)}>Pagar / ver faturas</button>
            )}
          </div>
        </div>
        {d?.cliente?.nome && (
          <div className="set"><div><b>Cliente na DWM</b><p>{d.cliente.nome}{d.cliente.documento ? ` · ${d.cliente.documento}` : ""}</p></div></div>
        )}
        {d?.fatura_vencida && (
          <div className="set"><div><b>Fatura vencida</b>
            <p className="ruim-texto">{d.fatura_vencida.numero} · {fmtBRL(d.fatura_vencida.valor)} · venceu em {fmtData(d.fatura_vencida.vencimento)}{d.dias_atraso ? ` (${d.dias_atraso} dia(s) de atraso)` : ""}</p>
          </div></div>
        )}
        {d?.proxima_fatura && !d.fatura_vencida && (
          <div className="set"><div><b>Próxima fatura</b><p>{d.proxima_fatura.numero} · {fmtBRL(d.proxima_fatura.valor)} · vence em {fmtData(d.proxima_fatura.vencimento)}</p></div></div>
        )}
        {d && d.faturas_pagas.length > 0 && (
          <div className="set"><div><b>Últimos pagamentos</b>
            <p>{d.faturas_pagas.map((f) => `${f.numero} · ${fmtBRL(f.valor)}${f.pago_em ? ` · pago em ${fmtData(f.pago_em)}` : ""}`).join("  |  ")}</p>
          </div></div>
        )}
        {l.confirmado_em && (
          <div className="set"><div><b>Última confirmação com a DWM</b><p>{quandoLocal(l.confirmado_em)}{l.token_final ? ` · token final ${l.token_final}` : ""}</p></div></div>
        )}
      </div>

      {admin ? (
        <div className="card">
          {pedeToken ? (
            <div className="set">
              <div>
                <b>{l.situacao === "sem_token" ? "Ativar licença" : "Ativar token"}</b>
                <p>Digite o token de licença enviado pela DWM. Ele é conferido com a DWM antes de ser salvo e fica guardado com a criptografia do Windows neste computador.</p>
              </div>
              <form className="ctl linha-ctl" onSubmit={(e) => { e.preventDefault(); ativar(); }}>
                <input className="mono" value={token} onChange={(e) => setToken(e.target.value.toUpperCase())} placeholder="XXXX-XXXX-XXXX-XXXX"
                  autoComplete="off" spellCheck={false} maxLength={64} aria-label="Token de licença" />
                <button className="btn primary" disabled={ocupado || token.trim().length < 8}>{ocupado ? "Conferindo…" : "Ativar"}</button>
                {trocar && <button type="button" className="btn" onClick={() => setTrocar(false)}>Cancelar</button>}
              </form>
            </div>
          ) : (
            <div className="set">
              <div><b>Token de licença</b><p>Para trocar de token (ex.: mudança de cadastro na DWM) ou tirar a licença deste computador.</p></div>
              <div className="ctl linha-ctl">
                <button className="btn" onClick={() => setTrocar(true)}>Trocar token</button>
                <button className="btn perigo" onClick={remover} disabled={l.somente_leitura}
                  title={l.somente_leitura ? "Com a licença bloqueada não é possível remover o token" : undefined}>Remover</button>
              </div>
            </div>
          )}
        </div>
      ) : l.situacao === "sem_token" ? (
        <div className="card notice"><b>Licença não ativada</b><p>Peça a um administrador do sistema para ativar a licença DWM.</p></div>
      ) : null}

      <div className="card notice">
        <b>Como funciona</b>
        <p>O sistema confere com a DWM a situação das faturas desta confeitaria a cada 4 horas. Com uma fatura vencida há mais de 7 dias, o sistema entra em modo somente leitura (dá para ver, imprimir e fazer backup) até o pagamento ser confirmado. Sem internet, vale a última confirmação por até 7 dias.</p>
        <div><button className="btn mini" onClick={() => abrirSuporte(l, empresa.nome)}>Falar com o suporte DWM</button></div>
      </div>
    </>
  );
}

import { useCallback, useEffect, useState } from "react";
import { abrirUrl, api } from "./api";
import { fmtBRL, fmtData } from "./format";
import { Icone } from "./components/Icone";

/** Situação da licença DWM (motor: core/licenca.py). */
export interface FaturaLic { numero: string; valor: number; vencimento: string; status: string | null; pago_em: string | null }
export interface Licenca {
  situacao: "sem_token" | "liberado" | "tolerancia" | "bloqueado" | "sem_conexao";
  somente_leitura: boolean;
  motivo: "fatura" | "inativo" | "sem_confirmacao" | "token_invalido" | "token_ausente" | null;
  mensagem: string;
  portal: string;
  whatsapp: string;
  token_final: string | null;
  origem: string;
  erro: string | null;
  confirmado_em?: string | null;
  dados?: {
    status: string; dias_atraso: number | null; dias_restantes_tolerancia: number | null; mensagem: string;
    fatura_vencida: FaturaLic | null; proxima_fatura: FaturaLic | null; faturas_pagas: FaturaLic[];
    cliente: { nome: string; documento: string };
  } | null;
}

/** Lê a situação ao entrar e a cada 30 min (o motor só consulta a DWM a cada 4 h). */
export function useLicenca(versao: number) {
  const [lic, setLic] = useState<Licenca | null>(null);
  const carregar = useCallback(() => api.get<Licenca>("/licenca").then(setLic).catch(() => {}), []);
  useEffect(() => {
    carregar();
    const t = setInterval(carregar, 30 * 60 * 1000);
    return () => clearInterval(t);
  }, [carregar, versao]);
  return { lic, setLic, carregar };
}

export function abrirSuporte(lic: Licenca | null, empresa: string) {
  const texto = `Olá! Preciso de ajuda com a licença da Confeitaria. Empresa: ${empresa}.${lic?.token_final ? ` Token final ${lic.token_final}.` : ""}`;
  abrirUrl(`https://wa.me/${lic?.whatsapp ?? "5531981052030"}?text=${encodeURIComponent(texto)}`).catch(() => {});
}

/** Faixa no topo da área principal. Sem token: discreta. Tolerância: aviso. Bloqueado: vermelha. */
export function FaixaLicenca({ lic, admin, onAbrir, onVerificar, verificando, empresa }: {
  lic: Licenca | null; admin: boolean; onAbrir: () => void; onVerificar: () => void; verificando: boolean; empresa: string;
}) {
  if (!lic) return null;
  const fv = lic.dados?.fatura_vencida;
  if (lic.situacao === "sem_token") {
    if (!admin) return null;
    return (
      <div className="faixa-licenca neutra" role="status">
        <Icone nome="info" tam={14} />
        <span>Licença DWM não ativada neste computador.</span>
        <button className="btn mini" onClick={onAbrir}>Ativar</button>
      </div>
    );
  }
  if (lic.situacao === "tolerancia") {
    return (
      <div className="faixa-licenca warn" role="status">
        <Icone nome="alerta" tam={14} />
        <span>
          <b>Fatura DWM vencida</b>{fv ? ` (${fv.numero}, ${fmtBRL(fv.valor)}, venceu em ${fmtData(fv.vencimento)})` : ""}.{" "}
          {lic.dados?.dias_restantes_tolerancia != null ? `Regularize em até ${lic.dados.dias_restantes_tolerancia} dia(s) para evitar o bloqueio.` : lic.mensagem}
        </span>
        <button className="btn mini primary" onClick={() => abrirUrl(lic.portal)}>Pagar fatura</button>
        <button className="btn mini" onClick={onVerificar} disabled={verificando}>{verificando ? "Verificando…" : "Já paguei"}</button>
      </div>
    );
  }
  if (lic.situacao === "bloqueado") {
    const titulo = lic.motivo === "fatura" ? "Licença bloqueada por fatura em atraso"
      : lic.motivo === "inativo" ? "Licença inativa na DWM"
      : lic.motivo === "sem_confirmacao" ? "Licença não confirmada"
      : lic.motivo === "token_invalido" ? "Token de licença recusado"
      : "Licença não encontrada";
    return (
      <div className="faixa-licenca bad" role="alert">
        <Icone nome="alerta" tam={14} />
        <span><b>{titulo}.</b> {lic.mensagem} O sistema está em <b>modo somente leitura</b>: dá para ver e imprimir, mas não alterar.</span>
        {(lic.motivo === "fatura" || lic.motivo === "inativo") && <button className="btn mini primary" onClick={() => abrirUrl(lic.portal)}>Pagar fatura</button>}
        <button className="btn mini" onClick={onVerificar} disabled={verificando}>{verificando ? "Verificando…" : lic.motivo === "fatura" ? "Já paguei" : "Verificar agora"}</button>
        {(lic.motivo === "token_invalido" || lic.motivo === "token_ausente") && admin && <button className="btn mini" onClick={onAbrir}>Ativar token</button>}
        <button className="btn mini" onClick={() => abrirSuporte(lic, empresa)}>Suporte</button>
      </div>
    );
  }
  return null;
}

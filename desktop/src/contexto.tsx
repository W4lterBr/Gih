import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import type { Empresa, Usuario } from "./types";
import type { Licenca } from "./licenca";

/** Coisas que qualquer tela usa: avisos (toast), confirmação, usuário logado e empresa. */
interface Ctx {
  toast: (msg: string, erro?: boolean) => void;
  confirmar: (o: OpcoesConfirmacao) => Promise<boolean>;
  usuario: Usuario;
  admin: boolean;
  empresa: Empresa;
  recarregarEmpresa: () => void;
  /** Pede às telas abertas que releiam os dados (ex.: depois de restaurar um backup). */
  versaoDados: number;
  dadosMudaram: () => void;
  /** Licença DWM bloqueada, ou tela que o perfil só consulta: telas desabilitam criar/editar
   *  (o motor também recusa). `motivoBloqueio` explica qual dos dois. */
  somenteLeitura: boolean;
  motivoBloqueio: string | undefined;
  /** Perfil do usuário: a tela aparece? pode alterar nela? */
  ve: (tela: string) => boolean;
  pode: (tela: string) => boolean;
  licenca: Licenca | null;
  recarregarLicenca: () => void;
}

export interface OpcoesConfirmacao {
  titulo: string;
  texto: ReactNode;
  ok?: string;
  cancelar?: string;
  perigo?: boolean;
}

const AppCtx = createContext<Ctx | null>(null);

const MOTIVO_LICENCA = "Licença bloqueada: modo somente leitura";
const MOTIVO_PERFIL = "Seu perfil só consulta esta tela";

/**
 * Tela aberta com as regras do perfil: se o usuário só pode consultar, todos os botões
 * que já respeitam `somenteLeitura` ficam desabilitados, com a explicação certa.
 */
export function ModoTela({ tela, children }: { tela: string; children: ReactNode }) {
  const c = useApp();
  const soVer = !c.pode(tela);
  const valor = useMemo<Ctx>(() => (soVer && !c.somenteLeitura ? { ...c, somenteLeitura: true, motivoBloqueio: MOTIVO_PERFIL } : c), [c, soVer]);
  return <AppCtx.Provider value={valor}>{children}</AppCtx.Provider>;
}

export function useApp(): Ctx {
  const c = useContext(AppCtx);
  if (!c) throw new Error("useApp fora do provedor");
  return c;
}

interface Toast { id: number; msg: string; erro?: boolean }

export function ProvedorApp({ usuario, empresa, recarregarEmpresa, licenca, recarregarLicenca, children }: {
  usuario: Usuario; empresa: Empresa; recarregarEmpresa: () => void;
  licenca: Licenca | null; recarregarLicenca: () => void; children: ReactNode;
}) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [conf, setConf] = useState<(OpcoesConfirmacao & { resolver: (v: boolean) => void }) | null>(null);
  const [versaoDados, setVersaoDados] = useState(0);
  const botaoOk = useRef<HTMLButtonElement>(null);

  const toast = useCallback((msg: string, erro = false) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, erro }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), erro ? 6000 : 3500);
  }, []);

  const confirmar = useCallback((o: OpcoesConfirmacao) => new Promise<boolean>((resolver) => {
    setConf({ ...o, resolver });
    setTimeout(() => botaoOk.current?.focus(), 0);
  }), []);

  const responder = (v: boolean) => { conf?.resolver(v); setConf(null); };

  const valor = useMemo<Ctx>(() => {
    const telas = usuario.telas ?? {};
    return {
      toast, confirmar, usuario, admin: usuario.role === "admin", empresa, recarregarEmpresa,
      versaoDados, dadosMudaram: () => setVersaoDados((v) => v + 1),
      somenteLeitura: !!licenca?.somente_leitura, motivoBloqueio: licenca?.somente_leitura ? MOTIVO_LICENCA : undefined,
      licenca, recarregarLicenca,
      ve: (t: string) => !!telas[t], pode: (t: string) => telas[t] === "editar",
    };
  }, [toast, confirmar, usuario, empresa, recarregarEmpresa, versaoDados, licenca, recarregarLicenca]);

  return (
    <AppCtx.Provider value={valor}>
      {children}
      {conf && (
        <div className="scrim modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && responder(false)}
          onKeyDown={(e) => e.key === "Escape" && responder(false)}>
          <div className="dialogo" role="alertdialog" aria-label={conf.titulo}>
            <h2>{conf.titulo}</h2>
            <div className="nota-rodape conf-texto">{conf.texto}</div>
            <div className="dialogo-acoes">
              <button className="btn" onClick={() => responder(false)}>{conf.cancelar ?? "Cancelar"}</button>
              <button ref={botaoOk} className={`btn ${conf.perigo ? "perigo-cheio" : "primary"}`} onClick={() => responder(true)}>
                {conf.ok ?? "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast${t.erro ? " erro" : ""}`}>{t.msg}</div>)}
      </div>
    </AppCtx.Provider>
  );
}

import { invoke, isTauri } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";

/**
 * Cliente do motor da Confeitaria (servico_local.py). No app desktop, porta e token vêm
 * do Tauri (que inicia o motor). No navegador (`npm run dev`), de VITE_MOTOR_PORTA e
 * VITE_MOTOR_TOKEN — para desenvolver a interface com um motor iniciado à mão.
 */

interface Info { porta: number; token: string; erro: string | null }
let info: Promise<Info> | null = null;

function obterInfo(): Promise<Info> {
  if (!isTauri()) {
    const porta = Number(import.meta.env.VITE_MOTOR_PORTA || 0);
    const token = String(import.meta.env.VITE_MOTOR_TOKEN || "");
    return Promise.resolve({ porta, token, erro: porta ? null : "Motor só funciona no app desktop (ou defina VITE_MOTOR_PORTA)." });
  }
  info ??= invoke<Info>("motor_info");
  return info;
}

export class ErroMotor extends Error {
  constructor(msg: string, public status: number, public codigo?: string) { super(msg); }
}

/** Chamado quando o motor diz que a sessão acabou (ex.: motor reiniciado). */
let aoPerderSessao: (() => void) | null = null;
export const definirAoPerderSessao = (fn: () => void) => { aoPerderSessao = fn; };

async function chamar<T>(metodo: string, caminho: string, corpo?: unknown): Promise<T> {
  const { porta, token, erro } = await obterInfo();
  if (erro) throw new ErroMotor(erro, 0);
  let r: Response;
  try {
    r = await fetch(`http://127.0.0.1:${porta}${caminho}`, {
      method: metodo,
      headers: { "X-Token": token, "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new ErroMotor("O motor ainda não está respondendo.", 0);
  }
  const js = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && js.codigo === "sem_login") aoPerderSessao?.();
    throw new ErroMotor(js.erro ?? `Erro ${r.status}`, r.status, js.codigo);
  }
  return js as T;
}

export const api = {
  get: <T,>(caminho: string, params?: Record<string, string | number | undefined | null>) => {
    const q = params
      ? "?" + Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join("&")
      : "";
    return chamar<T>("GET", caminho + (q === "?" ? "" : q));
  },
  post: <T,>(caminho: string, corpo: unknown = {}) => chamar<T>("POST", caminho, corpo),
  put: <T,>(caminho: string, corpo: unknown = {}) => chamar<T>("PUT", caminho, corpo),
  del: <T,>(caminho: string) => chamar<T>("DELETE", caminho),
};

export type EstadoMotor = "iniciando" | "pronto" | "erro";

export interface Saude { ok: boolean; versao: string; banco: string | null; banco_ausente?: string | null; usuario: { id: number; username: string; role: string } | null; cozinha: string }

/** Espera o motor responder (ele sobe em paralelo com a janela). */
export function useMotor() {
  const [estado, setEstado] = useState<EstadoMotor>("iniciando");
  const [saude, setSaude] = useState<Saude | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    let vivo = true;
    let tentativas = 0;
    const tentar = () => {
      api.get<Saude>("/saude")
        .then((s) => { if (vivo) { setSaude(s); setEstado("pronto"); } })
        .catch((e: ErroMotor) => {
          if (!vivo) return;
          tentativas++;
          if (e.status === 0 && tentativas < 120) setTimeout(tentar, 250);
          else { setErro(e.message); setEstado("erro"); }
        });
    };
    tentar();
    return () => { vivo = false; };
  }, []);
  return { estado, saude, erro };
}

// ---------------------------------------------------------------- comandos do Tauri

export async function abrirArquivo(caminho: string) {
  if (!isTauri()) throw new Error("Disponível só no app desktop.");
  await invoke("abrir_arquivo", { caminho });
}

export async function mostrarNoExplorer(caminho: string) {
  if (!isTauri()) throw new Error("Disponível só no app desktop.");
  await invoke("mostrar_no_explorer", { caminho });
}

export async function abrirUrl(url: string) {
  if (!isTauri()) { window.open(url, "_blank"); return; }
  await invoke("abrir_url", { url });
}

/** Escolher onde salvar (PDF/Excel/ZIP). Retorna null se cancelado. */
export async function escolherSalvar(nomePadrao: string, filtros: { name: string; extensions: string[] }[]): Promise<string | null> {
  if (!isTauri()) {
    const c = window.prompt("Caminho completo do arquivo:", `C:\\Temp\\${nomePadrao}`);
    return c || null;
  }
  const { save } = await import("@tauri-apps/plugin-dialog");
  const { documentDir, join } = await import("@tauri-apps/api/path");
  const pasta = await documentDir().catch(() => "");
  return (await save({ defaultPath: pasta ? await join(pasta, nomePadrao) : nomePadrao, filters: filtros })) ?? null;
}

/** Escolher um arquivo existente. Retorna null se cancelado. */
export async function escolherAbrir(titulo: string, filtros: { name: string; extensions: string[] }[]): Promise<string | null> {
  if (!isTauri()) {
    const c = window.prompt(`${titulo} — caminho completo:`, "");
    return c || null;
  }
  const { open } = await import("@tauri-apps/plugin-dialog");
  const r = await open({ title: titulo, multiple: false, directory: false, filters: filtros });
  return typeof r === "string" ? r : null;
}

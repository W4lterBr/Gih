const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const inteiro = new Intl.NumberFormat("pt-BR");

export const fmtBRL = (v: number) => brl.format(v || 0);
export const fmtInt = (v: number) => inteiro.format(v || 0);

/** "2026-09-24" ou "2026-09-24 10:22[:00]" -> "24/09/2026" */
export function fmtData(iso: string | null | undefined) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso || "-";
}

/** "2026-09-24 10:22:05" -> "24/09/2026 10:22" */
export function fmtDataHora(iso: string | null | undefined) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : fmtData(iso);
}

const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

/** Entrega relativa: "Hoje", "Amanhã", "Ontem", "qua 15/10". */
export function fmtEntrega(iso: string) {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!a) return iso;
  const alvo = new Date(a, m - 1, d);
  const h = new Date();
  const hoje = new Date(h.getFullYear(), h.getMonth(), h.getDate());
  const dif = Math.round((alvo.getTime() - hoje.getTime()) / 86400000);
  if (dif === 0) return "Hoje";
  if (dif === 1) return "Amanhã";
  if (dif === -1) return "Ontem";
  return `${DIAS[alvo.getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}${a !== h.getFullYear() ? `/${a}` : ""}`;
}

/** Tamanhos do produto: "15, 20" -> "15 cm, 20 cm"; texto livre fica igual. */
export function fmtTamanho(s: string | null | undefined) {
  if (!s) return "";
  return s
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => (/^\d+([.,]\d+)?$/.test(t) ? `${t} cm` : t))
    .join(", ");
}

/** Data local AAAA-MM-DD. */
export function isoLocal(d: Date = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export const somarDias = (iso: string, dias: number) => {
  const [a, m, d] = iso.split("-").map(Number);
  return isoLocal(new Date(a, m - 1, d + dias));
};
export const ehSegunda = (iso: string) => {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d).getDay() === 1;
};

/** Texto preto ou branco conforme a luminância do fundo (etiquetas). */
export function corTexto(hex: string | null | undefined) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex ?? "");
  if (!m) return "#fff";
  const n = parseInt(m[1], 16);
  const lum = ((n >> 16) * 299 + ((n >> 8) & 255) * 587 + (n & 255) * 114) / 1000;
  return lum > 150 ? "#14141c" : "#fff";
}

export const sigla = (nome: string) =>
  nome
    .replace(/[^\p{L}\s]/gu, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("") || "?";

const CORES = ["#d6247e", "#1f9d6b", "#2f64c8", "#8b3bd6", "#c77a12", "#0f8a9a", "#b8403a", "#5a6b2f", "#6b4bd6"];
export const corDe = (texto: string) => {
  let h = 0;
  for (const c of texto) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return CORES[h % CORES.length];
};

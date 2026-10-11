import { useEffect, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import { getCurrentWindow } from "@tauri-apps/api/window";
import type { EstadoMotor } from "../api";

interface Props {
  onPalette?: () => void;
  motor: EstadoMotor;
  cozinha?: string | null;
  onCozinha?: () => void;
}

const TEXTO_MOTOR: Record<EstadoMotor, string> = {
  iniciando: "Iniciando…",
  pronto: "Painel da cozinha",
  erro: "Motor com erro",
};

/** Barra de título própria (a janela é criada com `decorations: false`). */
export function TitleBar({ onPalette, motor, cozinha, onCozinha }: Props) {
  const win = isTauri() ? getCurrentWindow() : null;
  const [versao, setVersao] = useState("");
  useEffect(() => { if (isTauri()) getVersion().then(setVersao).catch(() => {}); }, []);
  const dot = motor === "pronto" ? "dot on" : motor === "iniciando" ? "dot" : "dot off";
  return (
    <header className="titlebar" data-tauri-drag-region>
      <div className="wordmark">
        <div className="mark">C</div>CONFEITARIA <small>{versao ? `v${versao}` : "dev"}</small>
      </div>
      <div className="tb-spacer" data-tauri-drag-region />
      {onCozinha && (
        <button className="tb-chip tb-btn" onClick={onCozinha} title={cozinha ? `Painel da cozinha: ${cozinha}` : undefined}>
          <span className={dot} />
          {TEXTO_MOTOR[motor]}
        </button>
      )}
      {onPalette && (
        <button className="tb-chip tb-btn" onClick={onPalette}>
          Comandos <span className="kbd">Ctrl K</span>
        </button>
      )}
      <div className="winctl">
        <button aria-label="Minimizar" onClick={() => win?.minimize()}>
          <svg width="10" height="10" viewBox="0 0 10 10"><path d="M0 5h10" stroke="currentColor" /></svg>
        </button>
        <button aria-label="Maximizar" onClick={() => win?.toggleMaximize()}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><rect x=".5" y=".5" width="9" height="9" stroke="currentColor" /></svg>
        </button>
        <button className="close" aria-label="Fechar" onClick={() => win?.close()}>
          <svg width="10" height="10" viewBox="0 0 10 10"><path d="M0 0l10 10M10 0L0 10" stroke="currentColor" /></svg>
        </button>
      </div>
    </header>
  );
}

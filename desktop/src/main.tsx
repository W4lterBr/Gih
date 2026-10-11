import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./confeitaria.css";

// Segurar Shift ao abrir pula o login automático (para trocar de usuário).
const w = window as unknown as { __shift?: boolean };
w.__shift = false;
const marcarShift = (e: KeyboardEvent) => { if (e.key === "Shift") w.__shift = true; };
window.addEventListener("keydown", marcarShift);
setTimeout(() => window.removeEventListener("keydown", marcarShift), 4000);

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

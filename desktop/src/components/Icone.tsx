/** Ícones de linha (16px, traço 1.5) desenhados no mesmo estilo do Busca XML. */
const P: Record<string, string> = {
  inicio: "M2.5 7.2 8 2.5l5.5 4.7V13.5h-3.5v-4h-4v4H2.5z",
  pedidos: "M4 1.5h8v13l-2-1.3-2 1.3-2-1.3-2 1.3zM6 5h4M6 7.5h4M6 10h2.5",
  producao: "M3 6.5h10v3.5a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3zM5 6.5V4M8 6.5V3M11 6.5V4M1.5 8h1.5M13 8h1.5",
  pronta: "M2.5 5 8 2l5.5 3v6L8 14l-5.5-3zM2.5 5 8 8l5.5-3M8 8v6",
  clientes: "M6 7.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM1.5 13.5c.4-2.5 2.2-4 4.5-4s4.1 1.5 4.5 4M11 7.2a2 2 0 1 0-.4-3.9M12.2 9.6c1.3.5 2.1 1.7 2.3 3.4",
  produtos: "M2.5 9h11v4.5h-11zM4 9V7.2c0-.9.7-1.7 1.6-1.7h4.8c.9 0 1.6.8 1.6 1.7V9M8 5.5V3.5M8 3.5c-.8 0-1.2-.6-1.2-1.2S8 1 8 1s1.2.7 1.2 1.3-.4 1.2-1.2 1.2M2.5 11.2c1 .7 1.8.7 2.7 0s1.8-.7 2.8 0 1.8.7 2.8 0 1.7-.7 2.7 0",
  movimentacao: "M2.5 5h10M10 2.5 12.5 5 10 7.5M13.5 11h-10M6 8.5 3.5 11 6 13.5",
  relatorios: "M2.5 13.5h11M4.5 11V7.5M8 11V3.5M11.5 11V6",
  config: "M8 10.2a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4zM8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4",
  busca: "M7 11.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zM10.5 10.5 14 14",
  mais: "M8 3v10M3 8h10",
  editar: "M10.5 2.5l3 3-8 8H2.5v-3zM9 4l3 3",
  lixo: "M2.5 4h11M6 4V2.5h4V4M4 4l.7 9.5h6.6L12 4M6.5 6.5v4.5M9.5 6.5v4.5",
  fechar: "M3.5 3.5l9 9M12.5 3.5l-9 9",
  check: "M3 8.5 6.5 12 13 4.5",
  seta: "M3 4.5l3 3 3-3",
  direita: "M6 3.5 10.5 8 6 12.5",
  esquerda: "M10 3.5 5.5 8 10 12.5",
  calendario: "M2.5 3.5h11v10h-11zM2.5 6.5h11M5.5 2v3M10.5 2v3",
  etiqueta: "M2 2.5h5.5l6.5 6.5-5 5L2.5 7.5zM5 5.5h.01",
  arquivo: "M4 1.5h5.5L13 5v9.5H4zM9 1.5V5h4",
  download: "M8 2v8.5M4.5 7 8 10.5 11.5 7M2.5 13.5h11",
  upload: "M8 10.5V2M4.5 5.5 8 2l3.5 3.5M2.5 13.5h11",
  celular: "M4.5 1.5h7v13h-7zM7 12.5h2",
  sair: "M6 2.5H2.5v11H6M10 5l3 3-3 3M13 8H6",
  sol: "M8 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1",
  lua: "M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z",
  banco: "M8 2c3 0 5.5.9 5.5 2s-2.5 2-5.5 2-5.5-.9-5.5-2S5 2 8 2zM2.5 4v8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2V4M2.5 8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2",
  usuario: "M8 7.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2.5 14.5c.5-3 2.7-4.8 5.5-4.8s5 1.8 5.5 4.8",
  empresa: "M2.5 14V5.5L8 2l5.5 3.5V14M6 14v-3.5h4V14M5.5 7.5h1M9.5 7.5h1",
  copiar: "M5.5 5.5h8v8h-8zM3 10.5H2.5v-8h8V3",
  externo: "M9 2.5h4.5V7M13.5 2.5 7 9M11.5 9.5v4h-9v-9h4",
  alerta: "M8 2 14.5 13.5h-13zM8 6.5v3.5M8 12h.01",
  info: "M8 14.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM8 7.5V11M8 5h.01",
  historico: "M2.5 8a5.5 5.5 0 1 0 1.6-3.9M2.5 2.5v2.5H5M8 5v3l2 1.5",
  reload: "M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v2.5H11",
  bolo: "M2.5 13.5h11M3.5 13.5V9.5h9v4M5 9.5V7.5h6v2M8 7.5V5.5M8 5.5c-.7 0-1-.5-1-1S8 3 8 3s1 .9 1 1.5-.3 1-1 1",
  mover: "M6 3.5h.01M10 3.5h.01M6 8h.01M10 8h.01M6 12.5h.01M10 12.5h.01",
};

export function Icone({ nome, tam = 16, className, style }: { nome: keyof typeof P | string; tam?: number; className?: string; style?: React.CSSProperties }) {
  return (
    <svg width={tam} height={tam} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" className={className} style={style} aria-hidden="true">
      <path d={P[nome] ?? P.info} />
    </svg>
  );
}

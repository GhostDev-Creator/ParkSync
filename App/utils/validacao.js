// Validações iguais às do backend (schemas.py e utils/placa.py).

export const SENHA_MINIMA = 6;

const PLACA_MERCOSUL = /^[A-Z]{3}[0-9][A-Z][0-9]{2}$/;
const PLACA_ANTIGA = /^[A-Z]{3}[0-9]{4}$/;

// "bra-2e19" -> "BRA2E19". Retorna null se não for placa válida.
export function limparPlaca(texto) {
  const limpo = (texto || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  return PLACA_MERCOSUL.test(limpo) || PLACA_ANTIGA.test(limpo) ? limpo : null;
}

export function emailValido(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((email || '').trim());
}

export function somenteDigitos(texto) {
  return (texto || '').replace(/\D/g, '');
}

// Máscara DD/MM/AAAA enquanto digita
export function mascaraData(texto) {
  const d = somenteDigitos(texto).slice(0, 8);
  if (d.length > 4) return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`;
  if (d.length > 2) return `${d.slice(0, 2)}/${d.slice(2)}`;
  return d;
}

// Máscara HH:MM enquanto digita
export function mascaraHora(texto) {
  const d = somenteDigitos(texto).slice(0, 4);
  return d.length > 2 ? `${d.slice(0, 2)}:${d.slice(2)}` : d;
}

// "25/12/2026" + "14:30" -> Date, ou null se a data/hora não existir (ex.: 31/02, 25:00)
export function montarDataHora(data, hora) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(data || '');
  const h = /^(\d{2}):(\d{2})$/.exec(hora || '');
  if (!m || !h) return null;
  const [dia, mes, ano] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const [hh, mm] = [Number(h[1]), Number(h[2])];
  if (hh > 23 || mm > 59) return null;
  const dt = new Date(ano, mes - 1, dia, hh, mm);
  if (dt.getFullYear() !== ano || dt.getMonth() !== mes - 1 || dt.getDate() !== dia) return null;
  return dt;
}

// Formata ISO do backend ("2026-10-24T14:30:00") para "24/10/2026 às 14:30"
export function formatarDataHora(iso) {
  if (!iso) return '';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return '';
  const p = (n) => String(n).padStart(2, '0');
  return `${p(dt.getDate())}/${p(dt.getMonth() + 1)}/${dt.getFullYear()} às ${p(dt.getHours())}:${p(dt.getMinutes())}`;
}

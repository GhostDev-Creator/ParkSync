// Busca as notificações e controla quais o morador já viu (bolinha vermelha da Home).
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from './api';

const CHAVE_LIDAS = '@parksync:notificacoes-lidas';

export function buscarNotificacoes(moradorId, signal) {
  return api(`/api/notificacoes/morador/${moradorId}`, { signal }).then((lista) =>
    Array.isArray(lista) ? lista : [],
  );
}

// Só alertas de verdade acendem a bolinha. "Vaga livre/ocupada" e "Boas-vindas" são status, não aviso.
function chaveDoAviso(item) {
  const id = String(item?.id || '');
  if (id.startsWith('alerta_')) return id;
  if (id.startsWith('vaga_') && item.title === 'Alerta de Vaga!') return `${id}:conflito`;
  return null;
}

async function lerLidas() {
  try {
    const salvo = await AsyncStorage.getItem(CHAVE_LIDAS);
    const lista = salvo ? JSON.parse(salvo) : [];
    return new Set(Array.isArray(lista) ? lista : []);
  } catch {
    return new Set();
  }
}

export async function temNaoLidas(lista) {
  const lidas = await lerLidas();
  return lista.some((item) => {
    const chave = chaveDoAviso(item);
    return chave && !lidas.has(chave);
  });
}

export async function marcarComoLidas(lista) {
  const chaves = lista.map(chaveDoAviso).filter(Boolean);
  // Guarda só as atuais: o backend devolve no máximo 15 alertas, então a lista não cresce para sempre.
  await AsyncStorage.setItem(CHAVE_LIDAS, JSON.stringify(chaves)).catch(() => {});
}

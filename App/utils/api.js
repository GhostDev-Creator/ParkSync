// Cliente único da API ParkSync. Todas as telas usam este arquivo.
//
// Endereço da API, nesta ordem:
//   1. EXPO_PUBLIC_API_URL no arquivo .env do app (ex.: EXPO_PUBLIC_API_URL=http://192.168.0.10:8000)
//   2. "extra": { "apiUrl": "..." } no app.json
//   3. Automático: o mesmo IP do computador que roda o "npx expo start", porta 8000
//   4. http://127.0.0.1:8000 (só funciona no navegador do próprio computador)
import { Platform } from 'react-native';
import Constants from 'expo-constants';

const PORTA_API = 8000;
const TEMPO_LIMITE_MS = 10000;

function descobrirApiUrl() {
  const doEnv = process.env.EXPO_PUBLIC_API_URL;
  if (doEnv) return doEnv;

  const doAppJson = Constants.expoConfig?.extra?.apiUrl;
  if (doAppJson) return doAppJson;

  // No Expo Go, hostUri é "192.168.0.10:8081" (o PC que roda o Metro). A API roda no mesmo PC.
  const hostUri = Constants.expoConfig?.hostUri || Constants.expoGoConfig?.debuggerHost;
  const ip = hostUri ? hostUri.split(':')[0] : null;
  if (ip && ip !== 'localhost' && ip !== '127.0.0.1') return `http://${ip}:${PORTA_API}`;

  if (Platform.OS === 'web' && typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:${PORTA_API}`;
  }
  // Emulador Android enxerga o PC em 10.0.2.2
  if (Platform.OS === 'android') return `http://10.0.2.2:${PORTA_API}`;
  return `http://127.0.0.1:${PORTA_API}`;
}

export const API_URL = descobrirApiUrl().replace(/\/+$/, '');

// Token e "sessão expirou" são configurados pelo AuthContext.
let tokenAtual = null;
let aoExpirarSessao = null;

export function definirToken(token) {
  tokenAtual = token || null;
}

export function definirAoExpirarSessao(funcao) {
  aoExpirarSessao = funcao;
}

export class ApiError extends Error {
  constructor(mensagem, status = 0) {
    super(mensagem);
    this.name = 'ApiError';
    this.status = status;
  }
}

// FastAPI devolve detail como texto ou, em erro de validação (422), como lista.
function mensagemDoDetalhe(detail) {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    const msg = detail[0]?.msg || '';
    return msg.replace(/^Value error, /, '') || null;
  }
  return null;
}

/**
 * Faz a requisição com tempo limite, token e tratamento de erro.
 * Retorna o JSON da resposta. Lança ApiError com mensagem pronta para mostrar ao usuário.
 * opcoes.signal: AbortSignal para cancelar quando a tela fechar (erro com status -1).
 */
export async function api(caminho, { method = 'GET', body, signal, timeout = TEMPO_LIMITE_MS } = {}) {
  const controle = new AbortController();
  let estourouTempo = false;
  const timer = setTimeout(() => {
    estourouTempo = true;
    controle.abort();
  }, timeout);
  const cancelarExterno = () => controle.abort();
  if (signal) {
    if (signal.aborted) controle.abort();
    else signal.addEventListener('abort', cancelarExterno);
  }

  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (tokenAtual) headers.Authorization = `Bearer ${tokenAtual}`;

  let resposta;
  try {
    resposta = await fetch(`${API_URL}${caminho}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controle.signal,
    });
  } catch (err) {
    if (estourouTempo) throw new ApiError('O servidor demorou para responder. Tente novamente.', 0);
    if (signal?.aborted) throw new ApiError('Cancelado.', -1);
    throw new ApiError('Não foi possível conectar ao servidor. Verifique a rede e o endereço da API.', 0);
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener('abort', cancelarExterno);
  }

  let dados = null;
  try {
    dados = await resposta.json();
  } catch {
    dados = null; // resposta sem JSON (ex.: erro 500 em HTML)
  }

  if (!resposta.ok) {
    // Token vencido ou inválido: encerra a sessão. (401 sem token = login errado, não expira nada.)
    if (resposta.status === 401 && tokenAtual && aoExpirarSessao) aoExpirarSessao();
    const mensagem = mensagemDoDetalhe(dados?.detail) || `Erro ${resposta.status} no servidor.`;
    throw new ApiError(mensagem, resposta.status);
  }
  return dados;
}

export const foiCancelado = (err) => err instanceof ApiError && err.status === -1;

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { definirAoExpirarSessao, definirToken } from './utils/api';

const CHAVE_USUARIO = '@parksync:user';
const CHAVE_TOKEN = '@parksync:token';

export const AuthContext = createContext({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
  updateUserCar: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const userRef = useRef(null);

  // Carrega a sessão salva uma única vez. JSON corrompido não trava o app: limpa e vai para o login.
  useEffect(() => {
    let ativo = true;
    (async () => {
      try {
        const [[, salvo], [, tokenSalvo]] = await AsyncStorage.multiGet([CHAVE_USUARIO, CHAVE_TOKEN]);
        const dados = salvo ? JSON.parse(salvo) : null;
        if (ativo && dados?.id) {
          userRef.current = dados;
          setUser(dados);
          setToken(tokenSalvo || null);
          definirToken(tokenSalvo);
        }
      } catch {
        await AsyncStorage.multiRemove([CHAVE_USUARIO, CHAVE_TOKEN]).catch(() => {});
      } finally {
        if (ativo) setLoading(false);
      }
    })();
    return () => {
      ativo = false;
    };
  }, []);

  // Recebe a resposta do POST /api/login. O token fica separado dos dados do usuário.
  const login = useCallback(async (resposta) => {
    const { token: novoToken, token_type, ...dados } = resposta || {};
    userRef.current = dados;
    definirToken(novoToken);
    setUser(dados);
    setToken(novoToken || null);
    const pares = [[CHAVE_USUARIO, JSON.stringify(dados)]];
    if (novoToken) pares.push([CHAVE_TOKEN, novoToken]);
    await AsyncStorage.multiSet(pares);
    if (!novoToken) await AsyncStorage.removeItem(CHAVE_TOKEN);
  }, []);

  const logout = useCallback(async () => {
    userRef.current = null;
    definirToken(null);
    setUser(null);
    setToken(null);
    await AsyncStorage.multiRemove([CHAVE_USUARIO, CHAVE_TOKEN, '@parksync:notificacoes-lidas']).catch(() => {});
  }, []);

  const updateUserCar = useCallback(async (carro) => {
    if (!userRef.current) return;
    const atualizado = { ...userRef.current, carro };
    userRef.current = atualizado;
    setUser(atualizado);
    await AsyncStorage.setItem(CHAVE_USUARIO, JSON.stringify(atualizado));
  }, []);

  // Se a API responder 401 com token (sessão expirada), volta para o login.
  useEffect(() => {
    definirAoExpirarSessao(() => {
      logout();
    });
    return () => definirAoExpirarSessao(null);
  }, [logout]);

  const value = useMemo(
    () => ({ user, token, loading, login, logout, updateUserCar }),
    [user, token, loading, login, logout, updateUserCar],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

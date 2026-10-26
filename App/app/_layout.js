import React, { useEffect } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Stack, router, useSegments } from 'expo-router';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider, useAuth } from '../AuthContext';

// Telas que podem ser abertas sem login
const ROTAS_PUBLICAS = ['index', 'changePassword'];

function RootNavigator() {
  const { user, loading } = useAuth();
  const segments = useSegments();
  const rotaAtual = segments[0] ?? 'index';

  // Proteção de rotas: sem login vai para o login; logado não fica parado na tela de login.
  useEffect(() => {
    if (loading) return;
    const publica = ROTAS_PUBLICAS.includes(rotaAtual);
    if (!user && !publica) {
      router.replace('/');
    } else if (user && rotaAtual === 'index') {
      router.replace('/(tabs)/home');
    }
  }, [user, loading, rotaAtual]);

  return (
    <>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="profileData" options={{ presentation: 'transparentModal', animation: 'fade' }} />
        <Stack.Screen name="changePassword" options={{ presentation: 'transparentModal', animation: 'fade' }} />
        <Stack.Screen name="helpCenter" options={{ presentation: 'transparentModal', animation: 'fade' }} />
        <Stack.Screen name="termsOfUse" options={{ presentation: 'transparentModal', animation: 'fade' }} />
        <Stack.Screen name="registerVisitor" options={{ presentation: 'modal' }} />
      </Stack>
      {/* Cobre a tela enquanto lê a sessão salva, para não piscar o login antes de ir para a Home */}
      {loading && (
        <View style={styles.carregando}>
          <ActivityIndicator size="large" color="#0D6E4E" />
        </View>
      )}
    </>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <RootNavigator />
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  carregando: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
  },
});

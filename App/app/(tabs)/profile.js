import React, { useCallback, useState } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuth } from '../../AuthContext';
import { confirmar } from '../../utils/alerta';

export default function SettingsScreen() {
  const { logout } = useAuth();
  const [saindo, setSaindo] = useState(false);

  const handleLogout = useCallback(async () => {
    const ok = await confirmar('Sair da conta', 'Deseja realmente sair?', 'Sair');
    if (!ok) return;
    setSaindo(true);
    await logout(); // o app/_layout.js volta para o login quando o usuário sai
  }, [logout]);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>Configurações</Text>
          <Text style={styles.subtitle}>Conta e preferências</Text>
        </View>

        {/* Seção: Conta */}
        <Text style={styles.sectionHeader}>CONTA</Text>
        <View style={styles.card}>
          <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/profileData')}>
            <View style={[styles.iconBox, { backgroundColor: '#E0F2FE' }]}>
              <Feather name="user" size={18} color="#0284C7" />
            </View>
            <View style={styles.menuInfo}>
              <Text style={styles.menuTitle}>Meus dados</Text>
              <Text style={styles.menuSubtitle}>Informações do perfil</Text>
            </View>
            <Feather name="chevron-right" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <View style={styles.separator} />

          <TouchableOpacity style={styles.menuItem} onPress={() => router.push({ pathname: '/changePassword', params: { from: 'profile' } })}>
            <View style={[styles.iconBox, { backgroundColor: '#FEF3C7' }]}>
              <Feather name="lock" size={18} color="#D97706" />
            </View>
            <View style={styles.menuInfo}>
              <Text style={styles.menuTitle}>Alterar senha</Text>
              <Text style={styles.menuSubtitle}>Segurança da conta</Text>
            </View>
            <Feather name="chevron-right" size={18} color="#94A3B8" />
          </TouchableOpacity>
        </View>

        {/* Seção: Suporte */}
        <Text style={styles.sectionHeader}>SUPORTE E LEGAL</Text>
        <View style={styles.card}>
          <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/helpCenter')}>
            <View style={[styles.iconBox, { backgroundColor: '#FEE2E2' }]}>
              <Feather name="help-circle" size={18} color="#DC2626" />
            </View>
            <View style={styles.menuInfo}>
              <Text style={styles.menuTitle}>Central de Ajuda</Text>
              <Text style={styles.menuSubtitle}>Perguntas frequentes e suporte</Text>
            </View>
            <Feather name="chevron-right" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <View style={styles.separator} />

          <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/termsOfUse')}>
            <View style={[styles.iconBox, { backgroundColor: '#FEF3C7' }]}>
              <Feather name="file-text" size={18} color="#D97706" />
            </View>
            <View style={styles.menuInfo}>
              <Text style={styles.menuTitle}>Termos de Uso</Text>
              <Text style={styles.menuSubtitle}>Política de privacidade</Text>
            </View>
            <Feather name="chevron-right" size={18} color="#94A3B8" />
          </TouchableOpacity>
        </View>

        {/* Botão de Sair */}
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout} disabled={saindo}>
          {saindo ? <ActivityIndicator color="#DC2626" /> : <Text style={styles.logoutButtonText}>Sair da conta</Text>}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F4F7FB' },
  scrollContent: { padding: 20, paddingBottom: 40 },
  header: { marginBottom: 12 },
  title: { fontSize: 24, fontWeight: 'bold', color: '#0F172A', marginBottom: 2 },
  subtitle: { fontSize: 14, color: '#94A3B8' },
  sectionHeader: { fontSize: 12, fontWeight: 'bold', color: '#94A3B8', marginBottom: 8, marginTop: 16, letterSpacing: 0.5 },
  card: { backgroundColor: '#FFFFFF', borderRadius: 20, paddingVertical: 4, paddingHorizontal: 16, marginBottom: 10, elevation: 1 },
  menuItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12 },
  iconBox: { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center', marginRight: 14 },
  menuInfo: { flex: 1 },
  menuTitle: { fontSize: 15, fontWeight: '600', color: '#0F172A', marginBottom: 2 },
  menuSubtitle: { fontSize: 12, color: '#94A3B8' },
  separator: { height: 1, backgroundColor: '#F1F5F9', marginLeft: 50 },
  logoutButton: { backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FEE2E2', height: 52, borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginTop: 20 },
  logoutButtonText: { color: '#DC2626', fontSize: 15, fontWeight: 'bold' },
});

import React from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, Pressable } from 'react-native';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuth } from '../AuthContext';

const fechar = () => (router.canGoBack() ? router.back() : router.replace('/(tabs)/profile'));

export default function ProfileDataModal() {
  const { user } = useAuth();

  return (
    <View style={styles.modalOverlay}>
      <Pressable style={styles.backdropPressable} onPress={fechar} />
      <View style={styles.modalContent}>
        <View style={styles.dragIndicator} />

        <View style={styles.headerRow}>
          <View style={styles.headerTitleContainer}>
            <View style={styles.headerIconBox}>
              <Feather name="user" size={20} color="#0D6E4E" />
            </View>
            <View>
              <Text style={styles.title}>Meus Dados</Text>
              <Text style={styles.subtitle}>Informações do perfil</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.closeButton} onPress={fechar}>
            <Feather name="x" size={20} color="#64748B" />
          </TouchableOpacity>
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollBody}>
          <View style={styles.avatarSection}>
            <View style={styles.bigAvatar}>
              <MaterialCommunityIcons name="account" size={48} color="#0D6E4E" />
            </View>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>
                {user?.apartamento_bloco ? `Morador · ${user.apartamento_bloco}` : 'Morador'}
              </Text>
            </View>
          </View>

          <Text style={styles.sectionLabel}>DADOS PESSOAIS</Text>
          <View style={styles.formCard}>
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>NOME COMPLETO</Text>
              <Text style={styles.inputValue}>{user?.nome || 'Não informado'}</Text>
            </View>
            <View style={styles.separator} />
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>E-MAIL</Text>
              <Text style={styles.inputValue}>{user?.email || 'Não informado'}</Text>
            </View>
            <View style={styles.separator} />
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>APARTAMENTO E BLOCO</Text>
              <Text style={styles.inputValue}>{user?.apartamento_bloco || 'Não cadastrado'}</Text>
            </View>
            <View style={styles.separator} />
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>VEÍCULO</Text>
              <Text style={styles.inputValue}>
                {user?.carro ? `${user.carro.modelo} · ${user.carro.placa}` : 'Nenhum cadastrado'}
              </Text>
            </View>
          </View>

          <Text style={styles.hint}>Para corrigir seus dados, procure a administração do condomínio.</Text>
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15, 23, 42, 0.5)', justifyContent: 'flex-end' },
  backdropPressable: { flex: 1 },
  modalContent: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 20, paddingTop: 12, paddingBottom: 30, maxHeight: '85%' },
  dragIndicator: { width: 40, height: 4, backgroundColor: '#CBD5E1', borderRadius: 2, alignSelf: 'center', marginBottom: 16 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  headerTitleContainer: { flexDirection: 'row', alignItems: 'center' },
  headerIconBox: { width: 40, height: 40, backgroundColor: '#E6F4EA', borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  title: { fontSize: 18, fontWeight: 'bold', color: '#0F172A' },
  subtitle: { fontSize: 12, color: '#94A3B8' },
  closeButton: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F8FAFC', justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0' },
  scrollBody: { paddingBottom: 20 },
  avatarSection: { alignItems: 'center', marginBottom: 24 },
  bigAvatar: { width: 80, height: 80, backgroundColor: '#E6F4EA', borderRadius: 24, justifyContent: 'center', alignItems: 'center', marginBottom: 10 },
  badge: { backgroundColor: '#ECFDF5', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 16 },
  badgeText: { color: '#059669', fontSize: 13, fontWeight: '600' },
  sectionLabel: { fontSize: 12, fontWeight: 'bold', color: '#94A3B8', marginBottom: 8, letterSpacing: 0.5 },
  formCard: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 20, padding: 16 },
  inputGroup: { paddingVertical: 8 },
  inputLabel: { fontSize: 11, fontWeight: 'bold', color: '#94A3B8', marginBottom: 4, letterSpacing: 0.5 },
  inputValue: { fontSize: 15, fontWeight: '600', color: '#0F172A' },
  separator: { height: 1, backgroundColor: '#F1F5F9', marginVertical: 4 },
  hint: { fontSize: 12, color: '#94A3B8', textAlign: 'center', marginTop: 14 },
});

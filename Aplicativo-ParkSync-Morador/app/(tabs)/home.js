import React, { useContext } from 'react';
import { StyleSheet, Text, View, ScrollView, SafeAreaView, TouchableOpacity, Platform } from 'react-native';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { AuthContext } from '../../AuthContext';

export default function DashboardScreen() {
  const { user } = useContext(AuthContext);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <View style={styles.avatarContainer}>
              <MaterialCommunityIcons name="account" size={28} color="#475569" />
            </View>
            <View>
              <Text style={styles.greetingText}>Bem-vindo,</Text>
              <Text style={styles.userName}>{user?.nome || 'Morador'}</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.notificationBtn} onPress={() => router.push('/(tabs)/notifications')}>
            <Feather name="bell" size={20} color="#F59E0B" />
            <View style={styles.notificationDot} />
          </TouchableOpacity>
        </View>

        {/* Card Unidade */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.label}>Unidade</Text>
            <View style={styles.badge}><Text style={styles.badgeText}>Morador</Text></View>
          </View>
          <Text style={styles.unitTitle}>{user?.apartamento_bloco || 'Não informado'}</Text>
          <View style={styles.divider} />
          <View style={styles.grid}>
            <View style={styles.gridItem}>
              <Text style={styles.label}>Veículo</Text>
              <Text style={styles.value}>{user?.carro?.modelo || 'Sem veículo'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.label}>Placa</Text>
              <Text style={styles.value}>{user?.carro?.placa || 'N/A'}</Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F4F7FB' },
  scrollContent: { padding: 20, paddingBottom: 40 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, marginTop: Platform.OS === 'android' ? 20 : 0 },
  headerLeft: { flexDirection: 'row', alignItems: 'center' },
  avatarContainer: { width: 48, height: 48, backgroundColor: '#E2E8F0', borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  greetingText: { fontSize: 14, color: '#64748B' },
  userName: { fontSize: 18, fontWeight: 'bold', color: '#0F172A' },
  notificationBtn: { width: 48, height: 48, backgroundColor: '#FFFFFF', borderRadius: 12, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0' },
  notificationDot: { position: 'absolute', top: 12, right: 14, width: 8, height: 8, backgroundColor: '#EF4444', borderRadius: 4 },
  card: { backgroundColor: '#FFFFFF', borderRadius: 20, padding: 20, marginBottom: 24, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 8, elevation: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  label: { fontSize: 14, color: '#94A3B8', fontWeight: '500' },
  badge: { backgroundColor: '#ECFDF5', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 16 },
  badgeText: { color: '#059669', fontSize: 13, fontWeight: '600' },
  unitTitle: { fontSize: 22, fontWeight: 'bold', color: '#0F172A' },
  divider: { height: 1, backgroundColor: '#F1F5F9', marginVertical: 16 },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  gridItem: { width: '50%', marginBottom: 16 },
  value: { fontSize: 15, fontWeight: '600', color: '#0F172A', marginTop: 4 }
});
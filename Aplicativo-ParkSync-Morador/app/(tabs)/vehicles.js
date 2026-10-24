import React, { useState, useEffect, useContext, useCallback } from 'react';
import { StyleSheet, Text, View, ScrollView, SafeAreaView, TouchableOpacity, Platform, ActivityIndicator, Alert } from 'react-native';
import { MaterialCommunityIcons, Feather } from '@expo/vector-icons';
import { router, useFocusEffect } from 'expo-router';
import { AuthContext } from '../../AuthContext';

const API_URL = 'http://127.0.0.1:8000';

export default function VehiclesScreen() {
  const { user } = useContext(AuthContext);
  const [visitors, setVisitors] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchVisitors = async () => {
    if (!user?.id) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/visitantes/morador/${user.id}`);
      if (res.ok) {
        const data = await res.json();
        setVisitors(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchVisitors();
    }, [user?.id])
  );

  const handleCancelVisita = async (agendamentoId) => {
    Alert.alert('Cancelar Visita', 'Deseja realmente remover este agendamento?', [
      { text: 'Não', style: 'cancel' },
      {
        text: 'Sim',
        style: 'destructive',
        onPress: async () => {
          try {
            const res = await fetch(`${API_URL}/api/visitantes/agendamento/${agendamentoId}`, {
              method: 'DELETE',
            });
            if (res.ok) {
              setVisitors(prev => prev.filter(v => v.id_agendamento !== agendamentoId));
            }
          } catch (err) {
            Alert.alert('Erro', 'Não foi possível cancelar o agendamento.');
          }
        },
      },
    ]);
  };

  const formatDate = (isoString) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    return `${date.toLocaleDateString('pt-BR')} às ${date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={styles.title}>Meus Veículos</Text>
          <Text style={styles.subtitle}>Frota pessoal e controle de visitantes</Text>
        </View>

        {/* SEÇÃO: VEÍCULO DO MORADOR */}
        <Text style={styles.sectionHeader}>FROTA PESSOAL</Text>
        <View style={styles.vehicleCard}>
          <View style={styles.vehicleCardTop}>
            <View style={styles.carIconBox}>
              <MaterialCommunityIcons name="car" size={24} color="#059669" />
            </View>
            <View style={styles.carInfo}>
              <Text style={styles.carModel}>{user?.carro?.modelo || 'Nenhum cadastrado'}</Text>
              <Text style={styles.carColor}>Veículo Principal</Text>
            </View>
            <View style={styles.tagBadge}>
              <Feather name="check-circle" size={12} color="#059669" style={{ marginRight: 4 }} />
              <Text style={styles.tagBadgeText}>Ativo</Text>
            </View>
          </View>
          <View style={styles.separator} />
          <View style={styles.plateRow}>
            <Text style={styles.plateLabel}>PLACA DO VEÍCULO</Text>
            <View style={styles.plateBox}>
              <Text style={styles.plateText}>{user?.carro?.placa || 'N/A'}</Text>
            </View>
          </View>
        </View>

        {/* SEÇÃO: VISITANTES */}
        <View style={styles.visitorsHeaderRow}>
          <Text style={styles.sectionHeaderMarginless}>VISITANTES</Text>
          <TouchableOpacity 
            style={styles.addButton} 
            onPress={() => router.push('/registerVisitor')}
          >
            <Feather name="plus" size={16} color="#059669" style={{ marginRight: 4 }} />
            <Text style={styles.addButtonText}>Adicionar</Text>
          </TouchableOpacity>
        </View>

        {loading ? (
          <ActivityIndicator color="#059669" style={{ marginTop: 20 }} />
        ) : visitors.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nenhum visitante cadastrado no momento.</Text>
          </View>
        ) : (
          visitors.map((item) => (
            <View key={item.id_agendamento} style={styles.visitorCard}>
              <View style={styles.visitorTop}>
                <View style={styles.visitorIconBox}>
                  <Feather name="user" size={18} color="#D97706" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.visitorName}>{item.nome}</Text>
                  <Text style={styles.visitorDetails}>Placa: <Text style={{ fontWeight: 'bold' }}>{item.placa_veiculo || 'Sem veículo'}</Text></Text>
                </View>
                <TouchableOpacity onPress={() => handleCancelVisita(item.id_agendamento)}>
                  <Feather name="trash-2" size={18} color="#EF4444" />
                </TouchableOpacity>
              </View>
              <View style={styles.visitorFooter}>
                <Feather name="clock" size={13} color="#94A3B8" style={{ marginRight: 4 }} />
                <Text style={styles.visitorDate}>Entrada: {formatDate(item.data_entrada)}</Text>
              </View>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F4F7FB' },
  scrollContent: { padding: 20, paddingBottom: 40 },
  header: { marginBottom: 16, marginTop: Platform.OS === 'android' ? 10 : 0 },
  title: { fontSize: 24, fontWeight: 'bold', color: '#0F172A', marginBottom: 2 },
  subtitle: { fontSize: 14, color: '#94A3B8' },
  sectionHeader: { fontSize: 12, fontWeight: 'bold', color: '#94A3B8', marginBottom: 8, marginTop: 10, letterSpacing: 0.5 },
  sectionHeaderMarginless: { fontSize: 12, fontWeight: 'bold', color: '#94A3B8', letterSpacing: 0.5 },
  vehicleCard: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 20, padding: 16, marginBottom: 20 },
  vehicleCardTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  carIconBox: { width: 44, height: 44, backgroundColor: '#ECFDF5', borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  carInfo: { flex: 1 },
  carModel: { fontSize: 16, fontWeight: 'bold', color: '#0F172A', marginBottom: 2 },
  carColor: { fontSize: 12, color: '#94A3B8' },
  tagBadge: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#ECFDF5', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12 },
  tagBadgeText: { fontSize: 11, fontWeight: 'bold', color: '#059669' },
  separator: { height: 1, backgroundColor: '#F1F5F9', marginBottom: 12 },
  plateRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  plateLabel: { fontSize: 11, fontWeight: 'bold', color: '#94A3B8', letterSpacing: 0.5 },
  plateBox: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  plateText: { fontSize: 14, fontWeight: 'bold', color: '#0F172A', letterSpacing: 1 },
  visitorsHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, marginBottom: 10 },
  addButton: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14 },
  addButtonText: { fontSize: 13, fontWeight: 'bold', color: '#059669' },
  emptyContainer: { padding: 20, alignItems: 'center' },
  emptyText: { fontSize: 13, color: '#94A3B8' },
  visitorCard: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 16, padding: 14, marginBottom: 10 },
  visitorTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  visitorIconBox: { width: 36, height: 36, backgroundColor: '#FEF3C7', borderRadius: 10, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  visitorName: { fontSize: 14, fontWeight: 'bold', color: '#0F172A' },
  visitorDetails: { fontSize: 12, color: '#64748B', marginTop: 2 },
  visitorFooter: { flexDirection: 'row', alignItems: 'center', paddingTop: 8, borderTopWidth: 1, borderTopColor: '#F8FAFC' },
  visitorDate: { fontSize: 11, color: '#94A3B8' }
});
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View, FlatList, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons, Feather } from '@expo/vector-icons';
import { router, useFocusEffect } from 'expo-router';
import { useAuth } from '../../AuthContext';
import { api, foiCancelado } from '../../utils/api';
import { confirmar, mostrarAlerta } from '../../utils/alerta';
import { formatarDataHora } from '../../utils/validacao';

const VisitorCard = React.memo(function VisitorCard({ item, removendo, onCancel }) {
  return (
    <View style={styles.visitorCard}>
      <View style={styles.visitorTop}>
        <View style={styles.visitorIconBox}>
          <Feather name="user" size={18} color="#D97706" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.visitorName}>{item.nome}</Text>
          <Text style={styles.visitorDetails}>
            Placa: <Text style={{ fontWeight: 'bold' }}>{item.placa_veiculo || 'Sem veículo'}</Text>
          </Text>
        </View>
        {removendo ? (
          <ActivityIndicator size="small" color="#EF4444" />
        ) : (
          <TouchableOpacity onPress={() => onCancel(item.id_agendamento)} hitSlop={12} accessibilityLabel="Cancelar visita">
            <Feather name="trash-2" size={18} color="#EF4444" />
          </TouchableOpacity>
        )}
      </View>
      <View style={styles.visitorFooter}>
        <Feather name="clock" size={13} color="#94A3B8" style={{ marginRight: 4 }} />
        <Text style={styles.visitorDate}>
          {formatarDataHora(item.data_entrada)}
          {item.data_saida ? `  até  ${formatarDataHora(item.data_saida)}` : ''}
        </Text>
      </View>
    </View>
  );
});

export default function VehiclesScreen() {
  const { user } = useAuth();
  const [visitors, setVisitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [erro, setErro] = useState('');
  const [removendoId, setRemovendoId] = useState(null);
  const controleRef = useRef(null);

  const fetchVisitors = useCallback(
    async (puxou = false) => {
      if (!user?.id) return;
      controleRef.current?.abort();
      const controle = new AbortController();
      controleRef.current = controle;
      if (puxou) setRefreshing(true);
      try {
        const data = await api(`/api/visitantes/morador/${user.id}`, { signal: controle.signal });
        setVisitors(Array.isArray(data) ? data : []);
        setErro('');
      } catch (err) {
        if (foiCancelado(err)) return;
        setErro(err.message);
      } finally {
        if (controleRef.current === controle) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [user?.id],
  );

  // Recarrega quando a aba aparece e quando volta do cadastro de visitante
  useFocusEffect(
    useCallback(() => {
      fetchVisitors();
    }, [fetchVisitors]),
  );

  useEffect(() => () => controleRef.current?.abort(), []);

  const handleCancelVisita = useCallback(async (agendamentoId) => {
    const ok = await confirmar('Cancelar visita', 'Deseja realmente remover este agendamento?', 'Remover');
    if (!ok) return;
    setRemovendoId(agendamentoId);
    try {
      await api(`/api/visitantes/agendamento/${agendamentoId}`, { method: 'DELETE' });
      setVisitors((prev) => prev.filter((v) => v.id_agendamento !== agendamentoId));
    } catch (err) {
      // 404 = já tinha sido cancelado: some da lista do mesmo jeito
      if (err.status === 404) setVisitors((prev) => prev.filter((v) => v.id_agendamento !== agendamentoId));
      else mostrarAlerta('Erro', err.message || 'Não foi possível cancelar o agendamento.');
    } finally {
      setRemovendoId(null);
    }
  }, []);

  const renderItem = useCallback(
    ({ item }) => (
      <VisitorCard item={item} removendo={removendoId === item.id_agendamento} onCancel={handleCancelVisita} />
    ),
    [removendoId, handleCancelVisita],
  );

  const carro = user?.carro;

  const cabecalho = (
    <>
      <View style={styles.header}>
        <Text style={styles.title}>Meus Veículos</Text>
        <Text style={styles.subtitle}>Frota pessoal e controle de visitantes</Text>
      </View>

      <Text style={styles.sectionHeader}>FROTA PESSOAL</Text>
      <View style={styles.vehicleCard}>
        <View style={styles.vehicleCardTop}>
          <View style={styles.carIconBox}>
            <MaterialCommunityIcons name="car" size={24} color="#059669" />
          </View>
          <View style={styles.carInfo}>
            <Text style={styles.carModel}>{carro?.modelo || 'Nenhum cadastrado'}</Text>
            <Text style={styles.carColor}>{carro ? 'Veículo Principal' : 'Procure a administração para cadastrar'}</Text>
          </View>
          {carro ? (
            <View style={styles.tagBadge}>
              <Feather name="check-circle" size={12} color="#059669" style={{ marginRight: 4 }} />
              <Text style={styles.tagBadgeText}>Ativo</Text>
            </View>
          ) : null}
        </View>
        <View style={styles.separator} />
        <View style={styles.plateRow}>
          <Text style={styles.plateLabel}>PLACA DO VEÍCULO</Text>
          <View style={styles.plateBox}>
            <Text style={styles.plateText}>{carro?.placa || 'N/A'}</Text>
          </View>
        </View>
      </View>

      <View style={styles.visitorsHeaderRow}>
        <Text style={styles.sectionHeaderMarginless}>VISITANTES</Text>
        <TouchableOpacity style={styles.addButton} onPress={() => router.push('/registerVisitor')}>
          <Feather name="plus" size={16} color="#059669" style={{ marginRight: 4 }} />
          <Text style={styles.addButtonText}>Adicionar</Text>
        </TouchableOpacity>
      </View>

      {erro && visitors.length ? <Text style={styles.erroBanner}>{erro}</Text> : null}
    </>
  );

  const vazio = loading ? (
    <ActivityIndicator color="#059669" style={{ marginTop: 20 }} />
  ) : erro ? (
    <View style={styles.emptyContainer}>
      <Text style={styles.erroText}>{erro}</Text>
      <TouchableOpacity style={styles.addButton} onPress={() => fetchVisitors()}>
        <Text style={styles.addButtonText}>Tentar novamente</Text>
      </TouchableOpacity>
    </View>
  ) : (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyText}>Nenhum visitante agendado no momento.</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <FlatList
        data={visitors}
        keyExtractor={(item) => String(item.id_agendamento)}
        renderItem={renderItem}
        extraData={removendoId}
        ListHeaderComponent={cabecalho}
        ListEmptyComponent={vazio}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => fetchVisitors(true)} colors={['#059669']} tintColor="#059669" />
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F4F7FB' },
  scrollContent: { padding: 20, paddingBottom: 40 },
  header: { marginBottom: 16 },
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
  erroText: { fontSize: 13, color: '#EF4444', textAlign: 'center', marginBottom: 12 },
  erroBanner: { color: '#B91C1C', backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA', borderRadius: 12, padding: 10, fontSize: 12, marginBottom: 10 },
  visitorCard: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 16, padding: 14, marginBottom: 10 },
  visitorTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  visitorIconBox: { width: 36, height: 36, backgroundColor: '#FEF3C7', borderRadius: 10, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  visitorName: { fontSize: 14, fontWeight: 'bold', color: '#0F172A' },
  visitorDetails: { fontSize: 12, color: '#64748B', marginTop: 2 },
  visitorFooter: { flexDirection: 'row', alignItems: 'center', paddingTop: 8, borderTopWidth: 1, borderTopColor: '#F8FAFC' },
  visitorDate: { fontSize: 11, color: '#94A3B8', flex: 1 },
});

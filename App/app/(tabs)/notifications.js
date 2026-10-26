import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View, FlatList, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons } from '@expo/vector-icons';
import { router, useFocusEffect } from 'expo-router';
import { useAuth } from '../../AuthContext';
import { foiCancelado } from '../../utils/api';
import { buscarNotificacoes, marcarComoLidas } from '../../utils/notificacoes';

const voltar = () => (router.canGoBack() ? router.back() : router.replace('/(tabs)/home'));

// Cor do backend vem como "#RRGGBB"; o fundo do ícone usa a mesma cor com transparência.
const fundoDoIcone = (cor) => (/^#[0-9a-fA-F]{6}$/.test(cor || '') ? `${cor}22` : '#F1F5F9');

const NotificationCard = React.memo(function NotificationCard({ item }) {
  const cor = item.color || '#64748B';
  return (
    <View style={styles.card}>
      <View style={[styles.iconBox, { backgroundColor: fundoDoIcone(cor) }]}>
        <Ionicons name={item.icon || 'notifications'} size={22} color={cor} />
      </View>
      <View style={styles.cardBody}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {item.title}
          </Text>
          {item.time ? <Text style={styles.cardTime}>{item.time}</Text> : null}
        </View>
        <Text style={styles.cardDesc}>{item.desc}</Text>
      </View>
    </View>
  );
});

export default function NotificationsScreen() {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [erro, setErro] = useState('');
  const controleRef = useRef(null);

  const carregar = useCallback(
    async (puxou = false) => {
      if (!user?.id) return;
      controleRef.current?.abort(); // cancela a busca anterior, se ainda estiver rodando
      const controle = new AbortController();
      controleRef.current = controle;
      if (puxou) setRefreshing(true);
      try {
        const lista = await buscarNotificacoes(user.id, controle.signal);
        setNotifications(lista);
        setErro('');
        marcarComoLidas(lista); // apaga a bolinha da Home
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

  // Recarrega sempre que a aba aparece
  useFocusEffect(
    useCallback(() => {
      carregar();
    }, [carregar]),
  );

  // Cancela a requisição se a tela for desmontada (ex.: logout)
  useEffect(() => () => controleRef.current?.abort(), []);

  const onRefresh = useCallback(() => carregar(true), [carregar]);

  const cabecalho = (
    <>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={voltar}>
          <Feather name="arrow-left" size={20} color="#0F172A" />
        </TouchableOpacity>
        <View>
          <Text style={styles.title}>Notificações</Text>
          <Text style={styles.subtitle}>Alertas recentes · puxe para atualizar</Text>
        </View>
      </View>
      {/* Falhou ao atualizar, mas ainda há a lista anterior na tela */}
      {erro && notifications.length ? <Text style={styles.erroBanner}>{erro}</Text> : null}
    </>
  );

  const vazio = loading ? (
    <ActivityIndicator color="#065F46" style={{ marginTop: 20 }} />
  ) : erro ? (
    <View style={styles.erroBox}>
      <Text style={styles.erroText}>{erro}</Text>
      <TouchableOpacity style={styles.retryButton} onPress={() => carregar()}>
        <Text style={styles.retryText}>Tentar novamente</Text>
      </TouchableOpacity>
    </View>
  ) : (
    <Text style={styles.emptyText}>Nenhuma notificação encontrada.</Text>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <FlatList
        data={notifications}
        keyExtractor={(item, index) => String(item.id ?? index)}
        renderItem={({ item }) => <NotificationCard item={item} />}
        ListHeaderComponent={cabecalho}
        ListEmptyComponent={vazio}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#065F46']} tintColor="#065F46" />}
        showsVerticalScrollIndicator={false}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F4F7FB' },
  scrollContent: { padding: 20, paddingBottom: 40 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 24 },
  backButton: { width: 40, height: 40, backgroundColor: '#FFFFFF', borderRadius: 12, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0', marginRight: 12 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#0F172A' },
  subtitle: { fontSize: 12, color: '#94A3B8' },
  card: { backgroundColor: '#FFFFFF', borderRadius: 16, padding: 14, marginBottom: 12, flexDirection: 'row', borderWidth: 1, borderColor: '#E2E8F0' },
  iconBox: { width: 42, height: 42, borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  cardBody: { flex: 1 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  cardTitle: { flex: 1, fontSize: 15, fontWeight: 'bold', color: '#0F172A', marginRight: 8 },
  cardTime: { fontSize: 11, color: '#94A3B8' },
  cardDesc: { fontSize: 13, color: '#64748B', lineHeight: 18 },
  emptyText: { textAlign: 'center', color: '#94A3B8', marginTop: 20 },
  erroBanner: { color: '#B91C1C', backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA', borderRadius: 12, padding: 10, fontSize: 12, marginBottom: 12 },
  erroBox: { alignItems: 'center', marginTop: 20, paddingHorizontal: 10 },
  erroText: { textAlign: 'center', color: '#EF4444', fontSize: 13, marginBottom: 12 },
  retryButton: { backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12 },
  retryText: { color: '#059669', fontWeight: 'bold', fontSize: 13 },
});

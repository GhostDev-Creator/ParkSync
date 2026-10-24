import React, { useState, useEffect, useContext } from 'react';
import { StyleSheet, Text, View, ScrollView, SafeAreaView, TouchableOpacity, Platform, ActivityIndicator } from 'react-native';
import { Feather, Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { AuthContext } from '../../AuthContext';

const API_URL = 'http://127.0.0.1:8000';

export default function NotificationsScreen() {
  const { user } = useContext(AuthContext);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.id) return;
    
    fetch(`${API_URL}/api/notificacoes/morador/${user.id}`)
      .then(res => res.json())
      .then(data => setNotifications(data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, [user?.id]);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
              <Feather name="arrow-left" size={20} color="#0F172A" />
            </TouchableOpacity>
            <View>
              <Text style={styles.title}>Notificações</Text>
              <Text style={styles.subtitle}>Alertas recentes</Text>
            </View>
          </View>
        </View>

        {loading ? (
          <ActivityIndicator color="#065F46" style={{ marginTop: 20 }} />
        ) : notifications.length === 0 ? (
          <Text style={styles.emptyText}>Nenhuma notificação encontrada.</Text>
        ) : (
          notifications.map(item => (
            <View key={item.id} style={styles.card}>
              <View style={[styles.iconBox, { backgroundColor: `${item.color}15` }]}>
                <Ionicons name={item.icon} size={22} color={item.color} />
              </View>
              <View style={styles.cardBody}>
                <View style={styles.cardHeader}>
                  <Text style={styles.cardTitle}>{item.title}</Text>
                  <Text style={styles.cardTime}>{item.time}</Text>
                </View>
                <Text style={styles.cardDesc}>{item.desc}</Text>
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
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, marginTop: Platform.OS === 'android' ? 10 : 0 },
  headerLeft: { flexDirection: 'row', alignItems: 'center' },
  backButton: { width: 40, height: 40, backgroundColor: '#FFFFFF', borderRadius: 12, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0', marginRight: 12 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#0F172A' },
  subtitle: { fontSize: 12, color: '#94A3B8' },
  card: { backgroundColor: '#FFFFFF', borderRadius: 16, padding: 14, marginBottom: 12, flexDirection: 'row', borderWidth: 1, borderColor: '#E2E8F0' },
  iconBox: { width: 42, height: 42, borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  cardBody: { flex: 1 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  cardTitle: { fontSize: 15, fontWeight: 'bold', color: '#0F172A' },
  cardTime: { fontSize: 11, color: '#94A3B8' },
  cardDesc: { fontSize: 13, color: '#64748B', lineHeight: 18 },
  emptyText: { textAlign: 'center', color: '#94A3B8', marginTop: 20 }
});
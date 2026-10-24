import React, { useState, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TextInput,
  TouchableOpacity,
  SafeAreaView,
  Platform,
  Alert,
  ActivityIndicator,
} from 'react-native';

import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { AuthContext } from '../AuthContext';

const API_URL = 'http://127.0.0.1:8000';

export default function RegisterVisitorScreen() {
  const { user } = useContext(AuthContext);

  const [visitorName, setVisitorName] = useState('');
  const [visitorCpf, setVisitorCpf] = useState('');
  const [visitorCnh, setVisitorCnh] = useState('');
  const [carPlate, setCarPlate] = useState('');
  const [accessType, setAccessType] = useState('single');

  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [loading, setLoading] = useState(false);

  // Função auxiliar de alerta
  const showAlert = (title, msg) => {
    if (Platform.OS === 'web') alert(`${title}: ${msg}`);
    else Alert.alert(title, msg);
  };

  // Aplica máscara de Data (DD/MM/AAAA)
  const formatData = (text) => {
    let t = text.replace(/\D/g, '');
    if (t.length > 2) t = t.substring(0, 2) + '/' + t.substring(2);
    if (t.length > 5) t = t.substring(0, 5) + '/' + t.substring(5, 9);
    return t;
  };

  // Aplica máscara de Hora (HH:MM)
  const formatHora = (text) => {
    let t = text.replace(/\D/g, '');
    if (t.length > 2) t = t.substring(0, 2) + ':' + t.substring(2, 4);
    return t;
  };

  const handleRegister = async () => {
    if (!visitorName.trim() || !carPlate.trim()) {
      return showAlert('Atenção', 'Preencha o nome do visitante e a placa do veículo.');
    }

    if (accessType === 'period') {
      if (startDate.length < 10 || endDate.length < 10 || startTime.length < 5 || endTime.length < 5) {
        return showAlert('Atenção', 'Para visitas por período, preencha as datas (DD/MM/AAAA) e horários (HH:MM) completos.');
      }
    }

    setLoading(true);

    const payload = {
      nome: visitorName.trim(),
      cpf: visitorCpf.trim() || "00000000000", // Backend atualizou a modelagem, não permite Null em CPF
      cnh: visitorCnh.trim() || null,
      placa_veiculo: carPlate.trim().toUpperCase(),
      tipo_visita: accessType,
      fk_id_morador: user?.id,
      horario_inicio: accessType === 'period' ? `${startDate} ${startTime}` : null,
      horario_fim: accessType === 'period' ? `${endDate} ${endTime}` : null,
    };

    try {
      const response = await fetch(`${API_URL}/api/visitantes/cadastro`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.ok) {
        showAlert('Sucesso', 'Pré-cadastro realizado! A guarita receberá a atualização.');
        router.back();
      } else {
        showAlert('Erro', data.detail || 'Não foi possível realizar o cadastro.');
      }
    } catch (error) {
      showAlert('Erro', 'Falha ao conectar com o servidor.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.headerBar}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Feather name="arrow-left" size={20} color="#0F172A" />
        </TouchableOpacity>

        <View style={styles.headerTextContainer}>
          <Text style={styles.title}>Cadastrar Visitante</Text>
          <Text style={styles.subtitle}>Pré-acesso inteligente na portaria</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Text style={styles.sectionLabel}>DADOS DO VISITANTE</Text>
        <View style={styles.card}>
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Nome completo</Text>
            <TextInput style={styles.textInput} placeholder="Ex.: João da Silva" placeholderTextColor="#94A3B8" value={visitorName} onChangeText={setVisitorName} />
          </View>
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>CPF (Opcional)</Text>
            <TextInput style={styles.textInput} placeholder="Apenas números" placeholderTextColor="#94A3B8" keyboardType="numeric" maxLength={11} value={visitorCpf} onChangeText={setVisitorCpf} />
          </View>
          <View style={[styles.inputGroup, styles.lastInputGroup]}>
            <Text style={styles.inputLabel}>CNH (Opcional)</Text>
            <TextInput style={styles.textInput} placeholder="Apenas números" placeholderTextColor="#94A3B8" keyboardType="numeric" value={visitorCnh} onChangeText={setVisitorCnh} />
          </View>
        </View>

        <Text style={styles.sectionLabel}>VEÍCULO DO VISITANTE</Text>
        <View style={styles.card}>
          <View style={[styles.inputGroup, styles.lastInputGroup]}>
            <Text style={styles.inputLabel}>Placa (Padrão Mercosul)</Text>
            <TextInput style={styles.textInput} placeholder="ABC1D23" placeholderTextColor="#94A3B8" autoCapitalize="characters" maxLength={7} value={carPlate} onChangeText={setCarPlate} />
          </View>
        </View>

        <Text style={styles.sectionLabel}>PERÍODO DE ACESSO</Text>
        <View style={styles.card}>
          <View style={styles.segmentedControl}>
            <TouchableOpacity style={[styles.segmentButton, accessType === 'single' && styles.segmentButtonActive]} onPress={() => setAccessType('single')}>
              <Text style={[styles.segmentText, accessType === 'single' && styles.segmentTextActive]}>Entrada Única (12h)</Text>
            </TouchableOpacity>

            <TouchableOpacity style={[styles.segmentButton, accessType === 'period' && styles.segmentButtonActive]} onPress={() => setAccessType('period')}>
              <Text style={[styles.segmentText, accessType === 'period' && styles.segmentTextActive]}>Agendamento Fixo</Text>
            </TouchableOpacity>
          </View>

          {accessType === 'period' && (
            <>
              <View style={styles.rowInputs}>
                <View style={styles.halfInput}>
                  <Text style={styles.inputLabel}>Dia Chegada</Text>
                  <View style={styles.inputFieldBox}>
                    <TextInput style={styles.inputSubField} placeholder="DD/MM/AAAA" placeholderTextColor="#94A3B8" value={startDate} onChangeText={(t) => setStartDate(formatData(t))} keyboardType="numeric" maxLength={10} />
                  </View>
                </View>

                <View style={styles.halfInput}>
                  <Text style={styles.inputLabel}>Dia Saída</Text>
                  <View style={styles.inputFieldBox}>
                    <TextInput style={styles.inputSubField} placeholder="DD/MM/AAAA" placeholderTextColor="#94A3B8" value={endDate} onChangeText={(t) => setEndDate(formatData(t))} keyboardType="numeric" maxLength={10} />
                  </View>
                </View>
              </View>

              <View style={styles.rowInputs}>
                <View style={[styles.halfInput, styles.noBottomBorder]}>
                  <Text style={styles.inputLabel}>Hora Entrada</Text>
                  <View style={styles.inputFieldBox}>
                    <TextInput style={styles.inputSubField} placeholder="HH:MM" placeholderTextColor="#94A3B8" value={startTime} onChangeText={(t) => setStartTime(formatHora(t))} keyboardType="numeric" maxLength={5} />
                  </View>
                </View>

                <View style={[styles.halfInput, styles.noBottomBorder]}>
                  <Text style={styles.inputLabel}>Hora Limite</Text>
                  <View style={styles.inputFieldBox}>
                    <TextInput style={styles.inputSubField} placeholder="HH:MM" placeholderTextColor="#94A3B8" value={endTime} onChangeText={(t) => setEndTime(formatHora(t))} keyboardType="numeric" maxLength={5} />
                  </View>
                </View>
              </View>
            </>
          )}
        </View>

        <View style={styles.infoBox}>
          <Feather name="shield" size={16} color="#0284C7" style={styles.infoIcon} />
          <Text style={styles.infoBoxText}>A câmera validará a placa automaticamente na cancela. Se der erro, o porteiro fará a conferência visual.</Text>
        </View>

        <TouchableOpacity style={styles.submitButton} onPress={handleRegister} disabled={loading} activeOpacity={0.8}>
          {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitButtonText}>Liberar Acesso</Text>}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F4F7FB' },
  headerBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14, backgroundColor: '#FFFFFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0', marginTop: Platform.OS === 'android' ? 24 : 0 },
  backButton: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', justifyContent: 'center', alignItems: 'center' },
  headerTextContainer: { flex: 1, marginLeft: 12 },
  title: { fontSize: 18, fontWeight: 'bold', color: '#0F172A' },
  subtitle: { fontSize: 12, color: '#94A3B8', marginTop: 2 },
  scrollContent: { padding: 20, paddingBottom: 40 },
  sectionLabel: { fontSize: 12, fontWeight: 'bold', color: '#94A3B8', marginBottom: 8, marginTop: 16, letterSpacing: 0.5 },
  card: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 20, padding: 16 },
  inputGroup: { paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#F1F5F9', marginBottom: 6 },
  lastInputGroup: { borderBottomWidth: 0, marginBottom: 0 },
  inputLabel: { fontSize: 13, color: '#64748B', marginBottom: 6 },
  textInput: { fontSize: 15, color: '#0F172A', paddingVertical: 4, minHeight: 30 },
  segmentedControl: { flexDirection: 'row', backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 12, padding: 4, marginBottom: 14 },
  segmentButton: { flex: 1, paddingVertical: 10, alignItems: 'center', justifyContent: 'center', borderRadius: 10 },
  segmentButtonActive: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', elevation: 1 },
  segmentText: { fontSize: 13, fontWeight: '600', color: '#64748B' },
  segmentTextActive: { color: '#059669', fontWeight: 'bold' },
  rowInputs: { flexDirection: 'row', gap: 12, marginBottom: 4 },
  halfInput: { flex: 1, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  noBottomBorder: { borderBottomWidth: 0 },
  inputFieldBox: { flexDirection: 'row', alignItems: 'center', minHeight: 32 },
  inputSubField: { flex: 1, fontSize: 14, color: '#0F172A' },
  infoBox: { flexDirection: 'row', backgroundColor: '#EFF6FF', borderWidth: 1, borderColor: '#BFDBFE', borderRadius: 16, padding: 14, marginTop: 16 },
  infoIcon: { marginRight: 10, marginTop: 2 },
  infoBoxText: { flex: 1, fontSize: 12, color: '#1E40AF', lineHeight: 18 },
  submitButton: { backgroundColor: '#065F46', height: 52, borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginTop: 24 },
  submitButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: 'bold' },
});
import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuth } from '../AuthContext';
import { api } from '../utils/api';
import { mostrarAlerta } from '../utils/alerta';
import { limparPlaca, mascaraData, mascaraHora, montarDataHora, somenteDigitos } from '../utils/validacao';

const fechar = () => (router.canGoBack() ? router.back() : router.replace('/(tabs)/vehicles'));

export default function RegisterVisitorScreen() {
  const { user } = useAuth();

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

  // Retorna a mensagem do primeiro erro, ou null se o formulário estiver ok.
  const validar = () => {
    if (visitorName.trim().length < 2) return 'Informe o nome do visitante.';
    if (!limparPlaca(carPlate)) return 'Placa inválida. Use o formato ABC1D23 (Mercosul) ou ABC1234.';
    const cpf = somenteDigitos(visitorCpf);
    if (cpf && cpf.length !== 11) return 'O CPF precisa ter 11 dígitos (ou deixe em branco).';

    if (accessType === 'period') {
      const inicio = montarDataHora(startDate, startTime);
      const fim = montarDataHora(endDate, endTime);
      if (!inicio || !fim) return 'Preencha datas (DD/MM/AAAA) e horários (HH:MM) válidos.';
      if (fim <= inicio) return 'A saída precisa ser depois da chegada.';
      if (fim <= new Date()) return 'O período informado já terminou.';
    }
    return null;
  };

  const handleRegister = async () => {
    if (loading) return;
    const erro = validar();
    if (erro) return mostrarAlerta('Atenção', erro);
    if (!user?.id) return mostrarAlerta('Erro', 'Sessão inválida. Entre novamente.');

    const ehPeriodo = accessType === 'period';
    const payload = {
      nome: visitorName.trim(),
      cpf: somenteDigitos(visitorCpf) || null, // sem CPF vai null (o backend aceita)
      cnh: somenteDigitos(visitorCnh) || null,
      placa_veiculo: limparPlaca(carPlate),
      tipo_visita: accessType, // 'single' (12 h a partir de agora) ou 'period'
      fk_id_morador: user.id,
      horario_inicio: ehPeriodo ? `${startDate} ${startTime}` : null, // "dd/mm/aaaa hh:mm"
      horario_fim: ehPeriodo ? `${endDate} ${endTime}` : null,
    };

    setLoading(true);
    try {
      await api('/api/visitantes/cadastro', { method: 'POST', body: payload });
      setLoading(false);
      // A aba Veículos recarrega a lista sozinha quando volta a aparecer
      mostrarAlerta('Sucesso', 'Pré-cadastro realizado! A guarita já recebeu a atualização.', fechar);
    } catch (err) {
      setLoading(false);
      mostrarAlerta('Erro', err.message);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <View style={styles.headerBar}>
        <TouchableOpacity style={styles.backButton} onPress={fechar}>
          <Feather name="arrow-left" size={20} color="#0F172A" />
        </TouchableOpacity>

        <View style={styles.headerTextContainer}>
          <Text style={styles.title}>Cadastrar Visitante</Text>
          <Text style={styles.subtitle}>Pré-acesso inteligente na portaria</Text>
        </View>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.sectionLabel}>DADOS DO VISITANTE</Text>
          <View style={styles.card}>
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Nome completo</Text>
              <TextInput
                style={styles.textInput}
                placeholder="Ex.: João da Silva"
                placeholderTextColor="#94A3B8"
                value={visitorName}
                onChangeText={setVisitorName}
                autoCapitalize="words"
                maxLength={100}
              />
            </View>
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>CPF (Opcional)</Text>
              <TextInput
                style={styles.textInput}
                placeholder="Apenas números"
                placeholderTextColor="#94A3B8"
                keyboardType="number-pad"
                maxLength={11}
                value={visitorCpf}
                onChangeText={(t) => setVisitorCpf(somenteDigitos(t))}
              />
            </View>
            <View style={[styles.inputGroup, styles.lastInputGroup]}>
              <Text style={styles.inputLabel}>CNH (Opcional)</Text>
              <TextInput
                style={styles.textInput}
                placeholder="Apenas números"
                placeholderTextColor="#94A3B8"
                keyboardType="number-pad"
                maxLength={11}
                value={visitorCnh}
                onChangeText={(t) => setVisitorCnh(somenteDigitos(t))}
              />
            </View>
          </View>

          <Text style={styles.sectionLabel}>VEÍCULO DO VISITANTE</Text>
          <View style={styles.card}>
            <View style={[styles.inputGroup, styles.lastInputGroup]}>
              <Text style={styles.inputLabel}>Placa (Mercosul ou antiga)</Text>
              <TextInput
                style={styles.textInput}
                placeholder="ABC1D23"
                placeholderTextColor="#94A3B8"
                autoCapitalize="characters"
                autoCorrect={false}
                maxLength={8}
                value={carPlate}
                onChangeText={(t) => setCarPlate(t.toUpperCase().replace(/[^A-Z0-9-]/g, ''))}
              />
            </View>
          </View>

          <Text style={styles.sectionLabel}>PERÍODO DE ACESSO</Text>
          <View style={styles.card}>
            <View style={styles.segmentedControl}>
              <TouchableOpacity
                style={[styles.segmentButton, accessType === 'single' && styles.segmentButtonActive]}
                onPress={() => setAccessType('single')}
              >
                <Text style={[styles.segmentText, accessType === 'single' && styles.segmentTextActive]}>
                  Entrada Única (12h)
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.segmentButton, accessType === 'period' && styles.segmentButtonActive]}
                onPress={() => setAccessType('period')}
              >
                <Text style={[styles.segmentText, accessType === 'period' && styles.segmentTextActive]}>
                  Agendamento Fixo
                </Text>
              </TouchableOpacity>
            </View>

            {accessType === 'single' ? (
              <Text style={styles.helperText}>O acesso vale pelas próximas 12 horas a partir de agora.</Text>
            ) : (
              <>
                <View style={styles.rowInputs}>
                  <View style={styles.halfInput}>
                    <Text style={styles.inputLabel}>Dia Chegada</Text>
                    <TextInput
                      style={styles.inputSubField}
                      placeholder="DD/MM/AAAA"
                      placeholderTextColor="#94A3B8"
                      value={startDate}
                      onChangeText={(t) => setStartDate(mascaraData(t))}
                      keyboardType="number-pad"
                      maxLength={10}
                    />
                  </View>
                  <View style={styles.halfInput}>
                    <Text style={styles.inputLabel}>Dia Saída</Text>
                    <TextInput
                      style={styles.inputSubField}
                      placeholder="DD/MM/AAAA"
                      placeholderTextColor="#94A3B8"
                      value={endDate}
                      onChangeText={(t) => setEndDate(mascaraData(t))}
                      keyboardType="number-pad"
                      maxLength={10}
                    />
                  </View>
                </View>

                <View style={styles.rowInputs}>
                  <View style={[styles.halfInput, styles.noBottomBorder]}>
                    <Text style={styles.inputLabel}>Hora Entrada</Text>
                    <TextInput
                      style={styles.inputSubField}
                      placeholder="HH:MM"
                      placeholderTextColor="#94A3B8"
                      value={startTime}
                      onChangeText={(t) => setStartTime(mascaraHora(t))}
                      keyboardType="number-pad"
                      maxLength={5}
                    />
                  </View>
                  <View style={[styles.halfInput, styles.noBottomBorder]}>
                    <Text style={styles.inputLabel}>Hora Limite</Text>
                    <TextInput
                      style={styles.inputSubField}
                      placeholder="HH:MM"
                      placeholderTextColor="#94A3B8"
                      value={endTime}
                      onChangeText={(t) => setEndTime(mascaraHora(t))}
                      keyboardType="number-pad"
                      maxLength={5}
                    />
                  </View>
                </View>
              </>
            )}
          </View>

          <View style={styles.infoBox}>
            <Feather name="shield" size={16} color="#0284C7" style={styles.infoIcon} />
            <Text style={styles.infoBoxText}>
              A câmera validará a placa automaticamente na cancela. Se der erro, o porteiro fará a conferência visual.
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.submitButton, loading && styles.submitButtonDisabled]}
            onPress={handleRegister}
            disabled={loading}
            activeOpacity={0.8}
          >
            {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitButtonText}>Liberar Acesso</Text>}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F4F7FB' },
  headerBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14, backgroundColor: '#FFFFFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
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
  helperText: { fontSize: 12, color: '#64748B' },
  segmentedControl: { flexDirection: 'row', backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 12, padding: 4, marginBottom: 14 },
  segmentButton: { flex: 1, paddingVertical: 10, alignItems: 'center', justifyContent: 'center', borderRadius: 10 },
  segmentButtonActive: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', elevation: 1 },
  segmentText: { fontSize: 13, fontWeight: '600', color: '#64748B' },
  segmentTextActive: { color: '#059669', fontWeight: 'bold' },
  rowInputs: { flexDirection: 'row', gap: 12, marginBottom: 4 },
  halfInput: { flex: 1, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  noBottomBorder: { borderBottomWidth: 0 },
  inputSubField: { fontSize: 14, color: '#0F172A', minHeight: 32 },
  infoBox: { flexDirection: 'row', backgroundColor: '#EFF6FF', borderWidth: 1, borderColor: '#BFDBFE', borderRadius: 16, padding: 14, marginTop: 16 },
  infoIcon: { marginRight: 10, marginTop: 2 },
  infoBoxText: { flex: 1, fontSize: 12, color: '#1E40AF', lineHeight: 18 },
  submitButton: { backgroundColor: '#065F46', height: 52, borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginTop: 24 },
  submitButtonDisabled: { opacity: 0.7 },
  submitButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: 'bold' },
});

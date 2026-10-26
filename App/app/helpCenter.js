import React, { useMemo, useState } from 'react';
import { StyleSheet, Text, View, ScrollView, TextInput, TouchableOpacity, Pressable, Linking } from 'react-native';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { mostrarAlerta } from '../utils/alerta';

const EMAIL_SUPORTE = 'suporte@parksync.com.br';

// Fica fora do componente: não é recriada a cada renderização
const FAQ_LIST = [
  {
    title: 'Como funciona o reconhecimento de placa?',
    content:
      'Câmeras na entrada e na saída leem a placa do veículo e uma webcam confere o rosto do morador. Se placa e rosto batem com o cadastro (ou com uma visita agendada), a cancela abre sozinha; se não, o porteiro é avisado.',
  },
  {
    title: 'Como cadastrar um visitante?',
    content:
      'Acesse a aba Veículos, toque em "+ Adicionar" e preencha o nome e a placa do visitante. Escolha "Entrada única" (vale 12 horas) ou "Agendamento fixo" com data e hora de chegada e saída. A guarita recebe o pré-cadastro na hora.',
  },
  {
    title: 'O que fazer se minha placa não for reconhecida?',
    content:
      'Aguarde alguns segundos parado em frente à câmera. Se não liberar, acione o interfone da portaria: o porteiro pode conferir e abrir a cancela manualmente. Confira em "Meus Veículos" se a placa cadastrada está correta.',
  },
  {
    title: 'Como alterar minha senha?',
    content:
      'Em Configurações, toque em "Alterar senha". Informe a senha atual e a nova senha (mínimo 6 caracteres). Se esqueceu a senha, use "Esqueci minha senha" na tela de login.',
  },
  {
    title: 'Posso ter mais de um veículo cadastrado?',
    content:
      'O veículo é cadastrado pela administração do condomínio. Se você chegar com outro carro, o sistema reconhece seu rosto e libera o carro como temporário (um por vez). Cada unidade tem uma vaga.',
  },
];

// Busca sem diferenciar maiúsculas nem acentos ("veiculo" acha "Veículo")
const normalizar = (texto) =>
  texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
const FAQ_BUSCA = FAQ_LIST.map((item) => normalizar(`${item.title} ${item.content}`));

const fechar = () => (router.canGoBack() ? router.back() : router.replace('/(tabs)/profile'));

export default function HelpCenterModal() {
  const [expandedTitle, setExpandedTitle] = useState(FAQ_LIST[0].title);
  const [busca, setBusca] = useState('');

  const resultados = useMemo(() => {
    const termo = normalizar(busca.trim());
    if (!termo) return FAQ_LIST;
    return FAQ_LIST.filter((_, i) => FAQ_BUSCA[i].includes(termo));
  }, [busca]);

  const abrirEmail = async () => {
    const url = `mailto:${EMAIL_SUPORTE}?subject=${encodeURIComponent('Suporte ParkSync')}`;
    try {
      await Linking.openURL(url);
    } catch {
      mostrarAlerta('E-mail', `Escreva para ${EMAIL_SUPORTE}`);
    }
  };

  const abrirChat = () => {
    mostrarAlerta('Chat ao vivo', 'Atendimento de segunda a sexta, das 08h às 18h. Fora desse horário, use o interfone da portaria.');
  };

  return (
    <View style={styles.modalOverlay}>
      <Pressable style={styles.backdropPressable} onPress={fechar} />
      <View style={styles.modalContent}>
        <View style={styles.dragIndicator} />

        <View style={styles.headerRow}>
          <View style={styles.headerTitleContainer}>
            <View style={[styles.headerIconBox, { backgroundColor: '#FEE2E2' }]}>
              <Feather name="help-circle" size={20} color="#DC2626" />
            </View>
            <View>
              <Text style={styles.title}>Central de Ajuda</Text>
              <Text style={styles.subtitle}>Perguntas frequentes e suporte</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.closeButton} onPress={fechar}>
            <Feather name="x" size={20} color="#64748B" />
          </TouchableOpacity>
        </View>

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.scrollBody}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.searchContainer}>
            <Feather name="search" size={18} color="#94A3B8" style={styles.searchIcon} />
            <TextInput
              style={styles.searchInput}
              placeholder="Buscar por dúvidas e tutoriais..."
              placeholderTextColor="#94A3B8"
              value={busca}
              onChangeText={setBusca}
              autoCorrect={false}
              returnKeyType="search"
            />
            {busca ? (
              <TouchableOpacity onPress={() => setBusca('')} hitSlop={10}>
                <Feather name="x-circle" size={16} color="#94A3B8" />
              </TouchableOpacity>
            ) : null}
          </View>

          <Text style={styles.sectionLabel}>PERGUNTAS FREQUENTES</Text>

          {resultados.length === 0 ? (
            <Text style={styles.emptyText}>Nenhuma pergunta encontrada para "{busca.trim()}".</Text>
          ) : (
            <View style={styles.faqWrapper}>
              {resultados.map((item, index) => {
                // Durante a busca, todas as respostas encontradas ficam abertas
                const isOpen = busca.trim() ? true : expandedTitle === item.title;
                return (
                  <TouchableOpacity
                    key={item.title}
                    activeOpacity={0.8}
                    onPress={() => setExpandedTitle(isOpen ? null : item.title)}
                    style={[isOpen ? styles.faqCardActive : styles.faqCard, index > 0 && !isOpen && styles.faqCardBorder]}
                  >
                    <View style={styles.faqHeader}>
                      <Text style={isOpen ? styles.faqTitleActive : styles.faqTitle}>{item.title}</Text>
                      <Feather
                        name={isOpen ? 'chevron-up' : 'chevron-right'}
                        size={18}
                        color={isOpen ? '#059669' : '#94A3B8'}
                      />
                    </View>
                    {isOpen && <Text style={styles.faqBody}>{item.content}</Text>}
                  </TouchableOpacity>
                );
              })}
            </View>
          )}

          <Text style={[styles.sectionLabel, { marginTop: 20 }]}>FALAR COM SUPORTE</Text>

          <TouchableOpacity style={styles.supportCard} onPress={abrirChat}>
            <View style={[styles.supportIcon, { backgroundColor: '#ECFDF5' }]}>
              <MaterialCommunityIcons name="chat-processing-outline" size={20} color="#059669" />
            </View>
            <View style={styles.supportInfo}>
              <Text style={styles.supportTitle}>Chat ao vivo</Text>
              <Text style={styles.supportSub}>Seg-Sex, 08h–18h</Text>
            </View>
            <Feather name="chevron-right" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.supportCard} onPress={abrirEmail}>
            <View style={[styles.supportIcon, { backgroundColor: '#E0F2FE' }]}>
              <Feather name="mail" size={18} color="#0284C7" />
            </View>
            <View style={styles.supportInfo}>
              <Text style={styles.supportTitle}>E-mail</Text>
              <Text style={styles.supportSub}>{EMAIL_SUPORTE}</Text>
            </View>
            <Feather name="chevron-right" size={18} color="#94A3B8" />
          </TouchableOpacity>
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
  headerIconBox: { width: 40, height: 40, borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  title: { fontSize: 18, fontWeight: 'bold', color: '#0F172A' },
  subtitle: { fontSize: 12, color: '#94A3B8' },
  closeButton: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F8FAFC', justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0' },
  scrollBody: { paddingBottom: 20 },
  searchContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 12, paddingHorizontal: 14, height: 48, marginBottom: 20 },
  searchIcon: { marginRight: 10 },
  searchInput: { flex: 1, fontSize: 14, color: '#0F172A' },
  sectionLabel: { fontSize: 12, fontWeight: 'bold', color: '#94A3B8', marginBottom: 8, letterSpacing: 0.5 },
  emptyText: { fontSize: 13, color: '#94A3B8', textAlign: 'center', paddingVertical: 16 },
  faqWrapper: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 20, overflow: 'hidden', marginBottom: 10 },
  faqCard: { backgroundColor: '#FFFFFF', padding: 16, flexDirection: 'column' },
  faqCardBorder: { borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  faqCardActive: { backgroundColor: '#ECFDF5', padding: 16, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#A7F3D0', marginVertical: -1, zIndex: 2 },
  faqHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  faqTitle: { fontSize: 14, fontWeight: '600', color: '#0F172A', flex: 1, marginRight: 8 },
  faqTitleActive: { fontSize: 14, fontWeight: 'bold', color: '#065F46', flex: 1, marginRight: 8 },
  faqBody: { fontSize: 13, color: '#047857', lineHeight: 18, marginTop: 10 },
  supportCard: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 16, padding: 14, marginBottom: 10, flexDirection: 'row', alignItems: 'center' },
  supportIcon: { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  supportInfo: { flex: 1 },
  supportTitle: { fontSize: 14, fontWeight: 'bold', color: '#0F172A' },
  supportSub: { fontSize: 12, color: '#94A3B8' },
});

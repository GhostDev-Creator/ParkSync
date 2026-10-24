import React, { useState } from 'react';
import { StyleSheet, Text, View, ScrollView, TextInput, TouchableOpacity, Pressable } from 'react-native';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';

export default function HelpCenterModal() {
  const [expandedIndex, setExpandedIndex] = useState(0); // 0 começa com a primeira aberta, defina null se quiser todas fechadas

  const faqList = [
    {
      title: "Como funciona o reconhecimento de placa?",
      content: "Câmeras com visão computacional capturam a placa do veículo na entrada. O sistema compara em tempo real com o banco de dados e libera ou nega o acesso automaticamente."
    },
    {
      title: "Como cadastrar um visitante?",
      content: "Acesse a aba Veículos, toque em \"+ Adicionar\" e preencha os dados do visitante e do veículo. O pré-cadastro é enviado à guarita imediatamente."
    },
    {
      title: "O que fazer se minha placa não for reconhecida?",
      content: "Acione o interfone da portaria ou contate o síndico. Certifique-se de que o veículo está cadastrado em \"Meus Veículos\" com a placa correta."
    },
    {
      title: "Como alterar minha senha?",
      content: "Em Configurações, toque em \"Alterar senha\". Informe a senha atual e a nova senha. A alteração é aplicada imediatamente."
    },
    {
      title: "Posso ter mais de um veículo cadastrado?",
      content: "Sim. Entre em contato com a administração do condomínio para cadastrar veículos adicionais. Cada unidade pode ter até 2 vagas fixas."
    }
  ];

  return (
    <View style={styles.modalOverlay}>
      <Pressable style={styles.backdropPressable} onPress={() => router.back()} />
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
          <TouchableOpacity style={styles.closeButton} onPress={() => router.back()}>
            <Feather name="x" size={20} color="#64748B" />
          </TouchableOpacity>
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollBody}>
          <View style={styles.searchContainer}>
            <Feather name="search" size={18} color="#94A3B8" style={styles.searchIcon} />
            <TextInput 
              style={styles.searchInput} 
              placeholder="Buscar por dúvidas e tutoriais..." 
              placeholderTextColor="#94A3B8" 
            />
          </View>

          <Text style={styles.sectionLabel}>PERGUNTAS FREQUENTES</Text>
          
          <View style={styles.faqWrapper}>
            {faqList.map((item, index) => {
              const isOpen = expandedIndex === index;
              return (
                <TouchableOpacity 
                  key={index} 
                  activeOpacity={0.8}
                  onPress={() => setExpandedIndex(isOpen ? null : index)}
                  style={[isOpen ? styles.faqCardActive : styles.faqCard, index > 0 && !isOpen && styles.faqCardBorder]}
                >
                  <View style={styles.faqHeader}>
                    <Text style={isOpen ? styles.faqTitleActive : styles.faqTitle}>
                      {item.title}
                    </Text>
                    <Feather 
                      name={isOpen ? "chevron-up" : "chevron-right"} 
                      size={18} 
                      color={isOpen ? "#059669" : "#94A3B8"} 
                    />
                  </View>
                  {isOpen && (
                    <Text style={styles.faqBody}>
                      {item.content}
                    </Text>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={[styles.sectionLabel, { marginTop: 20 }]}>FALAR COM SUPORTE</Text>
          
          <TouchableOpacity style={styles.supportCard}>
            <View style={[styles.supportIcon, { backgroundColor: '#ECFDF5' }]}>
              <MaterialCommunityIcons name="chat-processing-outline" size={20} color="#059669" />
            </View>
            <View style={styles.supportInfo}>
              <Text style={styles.supportTitle}>Chat ao vivo</Text>
              <Text style={styles.supportSub}>Seg-Sex, 08h–18h</Text>
            </View>
            <Feather name="chevron-right" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.supportCard}>
            <View style={[styles.supportIcon, { backgroundColor: '#E0F2FE' }]}>
              <Feather name="mail" size={18} color="#0284C7" />
            </View>
            <View style={styles.supportInfo}>
              <Text style={styles.supportTitle}>E-mail</Text>
              <Text style={styles.supportSub}>suporte@parksync.com.br</Text>
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
  supportSub: { fontSize: 12, color: '#94A3B8' }
});
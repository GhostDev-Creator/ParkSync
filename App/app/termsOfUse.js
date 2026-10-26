import React from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, Pressable } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';

const fechar = () => (router.canGoBack() ? router.back() : router.replace('/'));

export default function TermsOfUseModal() {
  return (
    <View style={styles.modalOverlay}>
      <Pressable style={styles.backdropPressable} onPress={fechar} />
      <View style={styles.modalContent}>
        <View style={styles.dragIndicator} />
        
        <View style={styles.headerRow}>
          <View style={styles.headerTitleContainer}>
            <View style={[styles.headerIconBox, { backgroundColor: '#FEF3C7' }]}>
              <Feather name="file-text" size={20} color="#D97706" />
            </View>
            <View>
              <Text style={styles.title}>Termos de Uso</Text>
              <Text style={styles.subtitle}>Última atualização: 01/07/2024</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.closeButton} onPress={fechar}>
            <Feather name="x" size={20} color="#64748B" />
          </TouchableOpacity>
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollBody}>
          <View style={styles.alertBox}>
            <Feather name="shield" size={18} color="#0284C7" style={styles.alertIcon} />
            <Text style={styles.alertText}>
              Este aplicativo está em conformidade com a LGPD (Lei n.º 13.709/2018) e adota as melhores práticas de segurança da informação.
            </Text>
          </View>

          <View style={styles.termsCard}>
            <Text style={styles.termTitle}>1. Aceitação dos Termos</Text>
            <Text style={styles.termText}>
              Ao utilizar o aplicativo ParkSync, você concorda com estes Termos de Uso e nossa Política de Privacidade. O uso do aplicativo é restrito a moradores e usuários autorizados pelo condomínio.
            </Text>

            <View style={styles.separator} />

            <Text style={styles.termTitle}>2. Coleta de Dados Pessoais</Text>
            <Text style={styles.termText}>
              Coletamos nome, CPF, e-mail, placa do veículo e dados de acesso. Essas informações são utilizadas exclusivamente para controle de acesso condominial e segurança patrimonial.
            </Text>

            <View style={styles.separator} />

            <Text style={styles.termTitle}>3. Uso de Câmeras e IA</Text>
            <Text style={styles.termText}>
              O sistema utiliza câmeras para leitura automática de placas (LPR) e reconhecimento facial do morador na entrada e na saída. A foto do rosto é convertida em uma assinatura numérica (dado biométrico) usada exclusivamente para liberar o acesso nas guaritas.
            </Text>
          </View>

          <Text style={styles.footerCompany}>
            ParkSync Tecnologia Ltda · CNPJ 00.000.000/0001-00{'\n'}contato@parksync.com.br
          </Text>
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
  alertBox: { flexDirection: 'row', backgroundColor: '#E0F2FE', borderWidth: 1, borderColor: '#BAE6FD', borderRadius: 16, padding: 14, marginBottom: 16, alignItems: 'center' },
  alertIcon: { marginRight: 10 },
  alertText: { flex: 1, fontSize: 12, color: '#0369A1', lineHeight: 18 },
  termsCard: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 20, padding: 16, marginBottom: 20 },
  termTitle: { fontSize: 14, fontWeight: 'bold', color: '#0F172A', marginBottom: 6 },
  termText: { fontSize: 13, color: '#475569', lineHeight: 18, marginBottom: 12 },
  separator: { height: 1, backgroundColor: '#F1F5F9', marginVertical: 12 },
  footerCompany: { textAlign: 'center', fontSize: 12, color: '#94A3B8', lineHeight: 16 },
});

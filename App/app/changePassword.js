import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  Pressable,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useAuth } from '../AuthContext';
import { api } from '../utils/api';
import { mostrarAlerta } from '../utils/alerta';
import { SENHA_MINIMA, emailValido, somenteDigitos } from '../utils/validacao';

const fechar = () => (router.canGoBack() ? router.back() : router.replace('/'));

// Retorna a mensagem de erro da nova senha, ou null se estiver ok.
function erroNovaSenha(nova, confirmacao, atual) {
  if (!nova || !confirmacao) return 'Preencha a nova senha e a confirmação.';
  if (nova.length < SENHA_MINIMA) return `A nova senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`;
  if (nova !== confirmacao) return 'A nova senha e a confirmação não coincidem.';
  if (atual !== undefined && nova === atual) return 'A nova senha precisa ser diferente da atual.';
  return null;
}

export default function ChangePasswordModal() {
  const { email: paramEmail, from } = useLocalSearchParams();
  const { user } = useAuth();

  // Logado = sempre fluxo de "alterar senha" (pede a atual). Deslogado = "esqueci minha senha".
  const isProfileFlow = from === 'profile' || (from !== 'forgot' && !!user);
  const [step, setStep] = useState(1);

  const [emailInput, setEmailInput] = useState(typeof paramEmail === 'string' ? paramEmail : '');
  const [code, setCode] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const emailLimpo = emailInput.trim().toLowerCase();

  const handleProfileSubmit = async () => {
    if (!currentPassword) return mostrarAlerta('Atenção', 'Informe a sua senha atual.');
    const erro = erroNovaSenha(newPassword, confirmPassword, currentPassword);
    if (erro) return mostrarAlerta('Atenção', erro);
    if (!user?.email) return mostrarAlerta('Erro', 'Sessão inválida. Entre novamente.');

    setLoading(true);
    try {
      await api('/api/morador/senha', {
        method: 'PUT',
        body: { email: user.email, senha_atual: currentPassword, nova_senha: newPassword },
      });
      setLoading(false);
      mostrarAlerta('Sucesso', 'Senha alterada com sucesso!', fechar);
    } catch (err) {
      setLoading(false);
      mostrarAlerta('Erro', err.message);
    }
  };

  const handleSendCode = async () => {
    if (!emailValido(emailLimpo)) return mostrarAlerta('Atenção', 'Informe um e-mail válido.');

    setLoading(true);
    try {
      await api('/api/recuperar-senha/solicitar', { method: 'POST', body: { email: emailLimpo } });
      setCode('');
      setStep(2);
      mostrarAlerta('Código enviado', 'Verifique a caixa de entrada do seu e-mail.');
    } catch (err) {
      // Antes o app avançava mesmo sem internet; agora só avança se o servidor confirmar.
      mostrarAlerta('Erro', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (code.length !== 6) return mostrarAlerta('Atenção', 'Digite o código de 6 dígitos.');

    setLoading(true);
    try {
      await api('/api/recuperar-senha/validar', { method: 'POST', body: { email: emailLimpo, codigo: code } });
      setStep(3);
    } catch (err) {
      mostrarAlerta('Erro', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async () => {
    const erro = erroNovaSenha(newPassword, confirmPassword);
    if (erro) return mostrarAlerta('Atenção', erro);

    setLoading(true);
    try {
      await api('/api/recuperar-senha/redefinir', {
        method: 'POST',
        body: { email: emailLimpo, codigo: code, nova_senha: newPassword },
      });
      setLoading(false);
      mostrarAlerta('Sucesso', 'Senha redefinida! Faça login com a nova senha.', fechar); // volta para o login
    } catch (err) {
      setLoading(false);
      // Código expirado ou com tentativas demais: volta para pedir outro
      if (/expirado|tentativas|Nenhuma solicitação/i.test(err.message)) setStep(1);
      mostrarAlerta('Erro', err.message);
    }
  };

  const titulo = isProfileFlow
    ? 'Alterar senha'
    : ['Esqueci minha senha', 'Código de verificação', 'Criar nova senha'][step - 1];
  const subtitulo = isProfileFlow
    ? 'Informe sua senha atual para confirmar'
    : [
        'Digite seu e-mail para receber o código',
        `Insira o código enviado para ${emailLimpo}`,
        'Digite a sua nova senha abaixo',
      ][step - 1];

  const botao = (texto, onPress) => (
    <TouchableOpacity
      style={[styles.submitButton, loading && styles.submitButtonDisabled]}
      onPress={onPress}
      disabled={loading}
      activeOpacity={0.8}
    >
      {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitButtonText}>{texto}</Text>}
    </TouchableOpacity>
  );

  const camposNovaSenha = (
    <>
      <View style={styles.inputGroup}>
        <Text style={styles.label}>Nova senha</Text>
        <TextInput
          style={styles.input}
          secureTextEntry
          value={newPassword}
          onChangeText={setNewPassword}
          placeholder={`Mínimo ${SENHA_MINIMA} caracteres`}
          placeholderTextColor="#94A3B8"
          autoComplete="new-password"
          textContentType="newPassword"
        />
      </View>
      <View style={styles.inputGroup}>
        <Text style={styles.label}>Confirmar nova senha</Text>
        <TextInput
          style={styles.input}
          secureTextEntry
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          placeholder="Repita a nova senha"
          placeholderTextColor="#94A3B8"
          autoComplete="new-password"
          textContentType="newPassword"
        />
      </View>
    </>
  );

  return (
    <KeyboardAvoidingView style={styles.modalOverlay} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <Pressable style={styles.backdropPressable} onPress={fechar} />
      <View style={styles.modalContent}>
        <View style={styles.dragIndicator} />

        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>{titulo}</Text>
            <Text style={styles.subtitle}>{subtitulo}</Text>
          </View>
          <TouchableOpacity style={styles.closeButton} onPress={fechar}>
            <Feather name="x" size={20} color="#64748B" />
          </TouchableOpacity>
        </View>

        {isProfileFlow ? (
          <>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Senha atual</Text>
              <TextInput
                style={styles.input}
                secureTextEntry
                value={currentPassword}
                onChangeText={setCurrentPassword}
                placeholder="••••••••"
                placeholderTextColor="#94A3B8"
                autoComplete="current-password"
                textContentType="password"
              />
            </View>
            {camposNovaSenha}
            {botao('Salvar nova senha', handleProfileSubmit)}
          </>
        ) : (
          <>
            {step === 1 && (
              <>
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>E-mail cadastrado</Text>
                  <TextInput
                    style={styles.input}
                    value={emailInput}
                    onChangeText={setEmailInput}
                    placeholder="seu@email.com"
                    placeholderTextColor="#94A3B8"
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoCorrect={false}
                    returnKeyType="send"
                    onSubmitEditing={handleSendCode}
                  />
                </View>
                {botao('Enviar código', handleSendCode)}
              </>
            )}

            {step === 2 && (
              <>
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>Código de 6 dígitos</Text>
                  <TextInput
                    style={[styles.input, styles.codeInput]}
                    value={code}
                    onChangeText={(t) => setCode(somenteDigitos(t).slice(0, 6))}
                    placeholder="000000"
                    placeholderTextColor="#94A3B8"
                    keyboardType="number-pad"
                    maxLength={6}
                    autoComplete="one-time-code"
                    textContentType="oneTimeCode"
                  />
                </View>
                {botao('Validar código', handleVerifyCode)}
                <TouchableOpacity style={styles.backStepButton} onPress={() => setStep(1)} disabled={loading}>
                  <Text style={styles.backStepText}>Alterar e-mail ou reenviar código</Text>
                </TouchableOpacity>
              </>
            )}

            {step === 3 && (
              <>
                {camposNovaSenha}
                {botao('Redefinir senha', handleResetPassword)}
              </>
            )}
          </>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15, 23, 42, 0.5)', justifyContent: 'flex-end' },
  backdropPressable: { flex: 1 },
  modalContent: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 24, paddingTop: 12, paddingBottom: 40 },
  dragIndicator: { width: 40, height: 4, backgroundColor: '#CBD5E1', borderRadius: 2, alignSelf: 'center', marginBottom: 16 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#0F172A' },
  subtitle: { fontSize: 13, color: '#94A3B8', marginTop: 2 },
  closeButton: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F8FAFC', justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0', marginLeft: 10 },
  inputGroup: { marginBottom: 16 },
  label: { fontSize: 13, fontWeight: '500', color: '#475569', marginBottom: 6 },
  input: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 12, paddingHorizontal: 16, height: 50, fontSize: 15, color: '#0F172A' },
  codeInput: { letterSpacing: 6, fontSize: 18, textAlign: 'center' },
  submitButton: { backgroundColor: '#0D6E4E', height: 54, borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginTop: 8 },
  submitButtonDisabled: { opacity: 0.7 },
  submitButtonText: { color: '#FFFFFF', fontSize: 16, fontWeight: 'bold' },
  backStepButton: { alignItems: 'center', marginTop: 14, paddingVertical: 4 },
  backStepText: { color: '#64748B', fontSize: 13, fontWeight: '500' },
});

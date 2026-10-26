import React, { useRef, useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuth } from '../AuthContext';
import { api } from '../utils/api';
import { emailValido } from '../utils/validacao';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const { login } = useAuth();
  const senhaRef = useRef(null);

  const handleLogin = async () => {
    if (loading) return;
    const emailLimpo = email.trim().toLowerCase();
    if (!emailLimpo || !senha) {
      setErrorMsg('Preencha todos os campos.');
      return;
    }
    if (!emailValido(emailLimpo)) {
      setErrorMsg('Digite um e-mail válido.');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    try {
      const data = await api('/api/login', { method: 'POST', body: { email: emailLimpo, senha } });
      await login(data); // o app/_layout.js leva para a Home assim que o usuário é salvo
    } catch (err) {
      setErrorMsg(err.status === 401 ? 'E-mail ou senha incorretos.' : err.message);
      setLoading(false);
    }
  };

  const handleForgotPassword = () => {
    router.push({ pathname: '/changePassword', params: { from: 'forgot', email: email.trim() } });
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <View style={styles.logoBox}>
              <MaterialCommunityIcons name="parking" size={32} color="#0D6E4E" />
            </View>
            <Text style={styles.title}>ParkSync</Text>
            <Text style={styles.subtitle}>Bem-vindo de volta</Text>
          </View>

          <View style={styles.form}>
            {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

            <View style={styles.inputGroup}>
              <Text style={styles.label}>E-mail</Text>
              <View style={styles.inputContainer}>
                <Feather name="mail" size={18} color="#94A3B8" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="seu@email.com"
                  placeholderTextColor="#94A3B8"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete="email"
                  textContentType="emailAddress"
                  returnKeyType="next"
                  onSubmitEditing={() => senhaRef.current?.focus()}
                />
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Senha</Text>
              <View style={styles.inputContainer}>
                <Feather name="lock" size={18} color="#94A3B8" style={styles.inputIcon} />
                <TextInput
                  ref={senhaRef}
                  style={styles.input}
                  placeholder="••••••••"
                  placeholderTextColor="#94A3B8"
                  value={senha}
                  onChangeText={setSenha}
                  secureTextEntry
                  autoComplete="password"
                  textContentType="password"
                  returnKeyType="go"
                  onSubmitEditing={handleLogin}
                />
              </View>
            </View>

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.buttonText}>Entrar na conta</Text>}
            </TouchableOpacity>

            <TouchableOpacity onPress={handleForgotPassword} style={styles.forgotPasswordButton}>
              <Text style={styles.forgotPasswordText}>Esqueci minha senha</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.securityCard}>
            <View style={styles.securityIconBox}>
              <Feather name="shield" size={18} color="#0D6E4E" />
            </View>
            <View style={styles.securityTextContainer}>
              <Text style={styles.securityTitle}>Acesso protegido</Text>
              <Text style={styles.securitySubtitle}>Autenticação segura · Controle biométrico ativo</Text>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scrollContent: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 40, paddingBottom: 24, justifyContent: 'space-between' },
  header: { alignItems: 'center', marginTop: 20, marginBottom: 32 },
  logoBox: { width: 68, height: 68, borderRadius: 22, backgroundColor: '#E6F4EA', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  title: { fontSize: 26, fontWeight: 'bold', color: '#0F172A' },
  subtitle: { fontSize: 14, color: '#64748B', marginTop: 4 },
  form: { width: '100%' },
  errorText: { color: '#EF4444', textAlign: 'center', marginBottom: 12, fontSize: 13 },
  inputGroup: { marginBottom: 16 },
  label: { fontSize: 13, fontWeight: '600', color: '#475569', marginBottom: 6 },
  inputContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 14, height: 52, paddingHorizontal: 14 },
  inputIcon: { marginRight: 10 },
  input: { flex: 1, fontSize: 15, color: '#0F172A' },
  button: { backgroundColor: '#0D6E4E', height: 52, borderRadius: 14, justifyContent: 'center', alignItems: 'center', marginTop: 8 },
  buttonDisabled: { opacity: 0.7 },
  buttonText: { color: '#FFFFFF', fontWeight: 'bold', fontSize: 15 },
  forgotPasswordButton: { alignItems: 'center', marginTop: 18, paddingVertical: 6 },
  forgotPasswordText: { color: '#0D6E4E', fontSize: 14, fontWeight: '600' },
  securityCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 16, padding: 14, marginTop: 24 },
  securityIconBox: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#E6F4EA', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  securityTextContainer: { flex: 1 },
  securityTitle: { fontSize: 13, fontWeight: 'bold', color: '#0F172A' },
  securitySubtitle: { fontSize: 11, color: '#64748B', marginTop: 2 },
});

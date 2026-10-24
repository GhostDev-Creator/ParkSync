import React, { useState, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  SafeAreaView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { AuthContext } from '../AuthContext';

const API_URL = 'http://127.0.0.1:8000';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const { login } = useContext(AuthContext);

  const handleLogin = async () => {
    if (!email.trim() || !senha.trim()) {
      setErrorMsg('Preencha todos os campos.');
      return;
    }

    setLoading(true);
    setErrorMsg('');

    try {
      const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), senha }),
      });

      const data = await response.json();

      if (response.ok) {
        await login(data);
        router.replace('/(tabs)/home');
      } else if (response.status === 401) {
        setErrorMsg('E-mail ou senha incorretos.');
      } else {
        setErrorMsg(data.detail || 'Erro ao realizar login.');
      }
    } catch (err) {
      setErrorMsg('Não foi possível conectar ao servidor.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = () => {
  router.push({
    pathname: '/changePassword',
    params: { from: 'forgot', email: email.trim() },
  });
};

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
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
                />
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Senha</Text>
              <View style={styles.inputContainer}>
                <Feather name="lock" size={18} color="#94A3B8" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="••••••••"
                  placeholderTextColor="#94A3B8"
                  value={senha}
                  onChangeText={setSenha}
                  secureTextEntry
                />
              </View>
            </View>

            <TouchableOpacity
              style={styles.button}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.buttonText}>Entrar na conta</Text>
              )}
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
              <Text style={styles.securitySubtitle}>
                Autenticação segura · Controle biométrico ativo
              </Text>
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
  buttonText: { color: '#FFFFFF', fontWeight: 'bold', fontSize: 15 },
  forgotPasswordButton: { alignItems: 'center', marginTop: 18, paddingVertical: 6 },
  forgotPasswordText: { color: '#0D6E4E', fontSize: 14, fontWeight: '600' },
  securityCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 16, padding: 14, marginTop: 24 },
  securityIconBox: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#E6F4EA', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  securityTextContainer: { flex: 1 },
  securityTitle: { fontSize: 13, fontWeight: 'bold', color: '#0F172A' },
  securitySubtitle: { fontSize: 11, color: '#64748B', marginTop: 2 }
});
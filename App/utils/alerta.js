// Alert.alert não aparece no navegador (Expo Web). Estas funções funcionam nos dois.
import { Alert, Platform } from 'react-native';

export function mostrarAlerta(titulo, mensagem, aoFechar) {
  if (Platform.OS === 'web') {
    window.alert(mensagem ? `${titulo}\n\n${mensagem}` : titulo);
    aoFechar?.();
    return;
  }
  Alert.alert(titulo, mensagem, [{ text: 'OK', onPress: aoFechar }], {
    cancelable: !aoFechar,
  });
}

// Pergunta sim/não. Resolve true se o usuário confirmar.
export function confirmar(titulo, mensagem, textoConfirmar = 'Sim') {
  if (Platform.OS === 'web') {
    return Promise.resolve(window.confirm(mensagem ? `${titulo}\n\n${mensagem}` : titulo));
  }
  return new Promise((resolve) => {
    Alert.alert(
      titulo,
      mensagem,
      [
        { text: 'Não', style: 'cancel', onPress: () => resolve(false) },
        { text: textoConfirmar, style: 'destructive', onPress: () => resolve(true) },
      ],
      { cancelable: true, onDismiss: () => resolve(false) },
    );
  });
}

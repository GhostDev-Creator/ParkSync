import { Stack } from 'expo-router';
import { AuthProvider } from '../AuthContext';

export default function RootLayout() {
  return (
    <AuthProvider>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen 
          name="profileData" 
          options={{ presentation: 'transparentModal', animation: 'fade' }} 
        />
        <Stack.Screen 
          name="changePassword" 
          options={{ presentation: 'transparentModal', animation: 'fade' }} 
        />
        <Stack.Screen 
          name="helpCenter" 
          options={{ presentation: 'transparentModal', animation: 'fade' }} 
        />
        <Stack.Screen 
          name="termsOfUse" 
          options={{ presentation: 'transparentModal', animation: 'fade' }} 
        />
        <Stack.Screen 
          name="registerVisitor" 
          options={{ presentation: 'modal' }} 
        />
      </Stack>
    </AuthProvider>
  );
}
import React from 'react';
import { Tabs } from 'expo-router';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function TabLayout() {
  // Usa a área segura real do aparelho (barra de gestos do Android, home indicator do iPhone)
  const insets = useSafeAreaInsets();
  const espacoInferior = Math.max(insets.bottom, 10);

  return (
    <Tabs
      backBehavior="history"
      screenOptions={{
        headerShown: false,
        lazy: true,
        tabBarStyle: {
          height: 70 + espacoInferior,
          backgroundColor: '#FFFFFF',
          borderTopWidth: 1,
          borderTopColor: '#E2E8F0',
          paddingBottom: espacoInferior,
          paddingTop: 10,
        },
        tabBarActiveTintColor: '#0D6E4E',
        tabBarInactiveTintColor: '#94A3B8',
        tabBarLabelStyle: { fontSize: 12, marginTop: 4 },
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: 'Início',
          tabBarIcon: ({ color }) => <Feather name="grid" size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="vehicles"
        options={{
          title: 'Veículos',
          tabBarIcon: ({ color }) => <MaterialCommunityIcons name="car-side" size={26} color={color} />,
        }}
      />
      <Tabs.Screen
        name="notifications"
        options={{
          title: 'Alertas',
          tabBarIcon: ({ color }) => <Feather name="bell" size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Config.',
          tabBarIcon: ({ color }) => <Feather name="settings" size={24} color={color} />,
        }}
      />
    </Tabs>
  );
}

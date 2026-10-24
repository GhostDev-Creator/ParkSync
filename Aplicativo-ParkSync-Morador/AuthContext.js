import React, { createContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

export const AuthContext = createContext({});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    AsyncStorage.getItem('@parksync:user').then(stored => {
      if (stored) setUser(JSON.parse(stored));
      setLoading(false);
    });
  }, []);

  const login = async (userData) => {
    setUser(userData);
    await AsyncStorage.setItem('@parksync:user', JSON.stringify(userData));
  };

  const logout = async () => {
    setUser(null);
    await AsyncStorage.removeItem('@parksync:user');
  };

  const updateUserCar = async (carro) => {
    const updatedUser = { ...user, carro };
    setUser(updatedUser);
    await AsyncStorage.setItem('@parksync:user', JSON.stringify(updatedUser));
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, updateUserCar, loading }}>
      {children}
    </AuthContext.Provider>
  );
}
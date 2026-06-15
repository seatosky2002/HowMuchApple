/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { authApi, getErrorMessage, userApi } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadMe = useCallback(async () => {
    try {
      const { data } = await userApi.me();
      setUser(data);
      setError('');
      return data;
    } catch (err) {
      if (err?.response?.status !== 401) {
        setError(getErrorMessage(err, '사용자 정보를 불러오지 못했습니다.'));
      }
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let alive = true;
    const bootstrap = async () => {
      const current = await loadMe();
      if (alive && !current) setUser(null);
      if (alive) setIsLoading(false);
    };
    bootstrap();
    return () => {
      alive = false;
    };
  }, [loadMe]);

  const login = useCallback(async (payload) => {
    await authApi.login(payload);
    return loadMe();
  }, [loadMe]);

  const register = useCallback(async (payload) => {
    await authApi.register(payload);
    return loadMe();
  }, [loadMe]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      error,
      login,
      register,
      logout,
      reloadUser: loadMe,
      setUser,
    }),
    [user, isLoading, error, login, register, logout, loadMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
};

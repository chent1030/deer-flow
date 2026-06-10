import { create } from 'zustand';
import type { User } from '../types';
import { login as apiLogin, getMe } from '../api/auth';

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,

  login: async (username: string, password: string) => {
    const tokenResponse = await apiLogin({ username, password });
    localStorage.setItem('access_token', tokenResponse.access_token);
    localStorage.setItem('refresh_token', tokenResponse.refresh_token);
    const user = await getMe();
    set({ user, loading: false });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, loading: false });
  },

  refreshUser: async () => {
    try {
      const user = await getMe();
      set({ user, loading: false });
    } catch {
      set({ user: null, loading: false });
    }
  },

  initialize: async () => {
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        const user = await getMe();
        set({ user, loading: false });
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        set({ user: null, loading: false });
      }
    } else {
      set({ loading: false });
    }
  },
}));

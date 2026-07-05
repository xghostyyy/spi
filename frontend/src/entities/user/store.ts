import { create } from 'zustand';

import { setAccessToken } from '../../shared/api/client';
import type { User } from './model';

interface SessionState {
  user: User | null;
  status: 'idle' | 'loading' | 'authenticated' | 'anonymous';
  setSession: (user: User, token: string) => void;
  updateUser: (patch: Partial<User>) => void;
  clearSession: () => void;
  setStatus: (status: SessionState['status']) => void;
}

/** Токен доступа хранится только в памяти (не persist) — refresh идёт через httpOnly cookie. */
export const useSessionStore = create<SessionState>()((set) => ({
  user: null,
  status: 'idle',
  setSession: (user, token) => {
    setAccessToken(token);
    set({ user, status: 'authenticated' });
  },
  updateUser: (patch) => set((s) => ({ user: s.user ? { ...s.user, ...patch } : s.user })),
  clearSession: () => {
    setAccessToken(null);
    set({ user: null, status: 'anonymous' });
  },
  setStatus: (status) => set({ status }),
}));

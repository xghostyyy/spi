import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ThemePref = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

function systemTheme(): ResolvedTheme {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark';
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function resolveTheme(pref: ThemePref): ResolvedTheme {
  return pref === 'system' ? systemTheme() : pref;
}

function applyTheme(pref: ThemePref): void {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.theme = resolveTheme(pref);
}

interface ThemeState {
  pref: ThemePref;
  setPref: (pref: ThemePref) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      pref: 'system',
      setPref: (pref) => {
        applyTheme(pref);
        set({ pref });
      },
    }),
    {
      name: 'spi-theme',
      onRehydrateStorage: () => (state) => {
        applyTheme(state?.pref ?? 'system');
      },
    },
  ),
);

// Первичное применение до гидратации persist (первый рендер без мигания).
applyTheme(useThemeStore.getState().pref);

/** Следит за системной темой; вызывает onChange, когда pref === 'system'. */
export function watchSystemTheme(onChange: () => void): () => void {
  if (typeof window === 'undefined' || !window.matchMedia) return () => undefined;
  const mq = window.matchMedia('(prefers-color-scheme: light)');
  const handler = () => {
    if (useThemeStore.getState().pref === 'system') {
      applyTheme('system');
      onChange();
    }
  };
  mq.addEventListener('change', handler);
  return () => mq.removeEventListener('change', handler);
}

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { en } from './en';
import { ru, type TranslationKey } from './ru';

export type Locale = 'ru' | 'en';

const dictionaries: Record<Locale, Record<TranslationKey, string>> = { ru, en };

interface LocaleState {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

export const useLocaleStore = create<LocaleState>()(
  persist(
    (set) => ({
      locale: 'ru',
      setLocale: (locale) => set({ locale }),
    }),
    { name: 'spi-locale' },
  ),
);

/** Хук перевода: const t = useT(); t('nav.chats') */
export function useT(): (key: TranslationKey) => string {
  const locale = useLocaleStore((s) => s.locale);
  return (key) => dictionaries[locale][key];
}

export type { TranslationKey };

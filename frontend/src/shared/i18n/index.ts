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

/** Русские формы множественного числа: plural(21, 'минуту', 'минуты', 'минут') → 'минуту'. */
export function pluralRu(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

export type { TranslationKey };

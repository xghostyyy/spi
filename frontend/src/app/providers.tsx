import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type ReactNode, useEffect, useState } from 'react';

import { useThemeStore, watchSystemTheme } from '../shared/theme';

const [queryClient] = [
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        staleTime: 30_000,
        refetchOnWindowFocus: true,
      },
    },
  }),
];

/** Применяет выбранную тему к <html data-theme=...> и следит за системной. */
function ThemeProvider({ children }: { children: ReactNode }) {
  const pref = useThemeStore((s) => s.pref);
  const [, forceRender] = useState(0);

  useEffect(() => {
    const stop = watchSystemTheme(() => forceRender((n) => n + 1));
    return stop;
  }, [pref]);

  return children;
}

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>{children}</ThemeProvider>
    </QueryClientProvider>
  );
}

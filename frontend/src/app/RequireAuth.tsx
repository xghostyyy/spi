import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { useT } from '../shared/i18n';
import { useSessionStore } from '../entities/user/store';

export function RequireAuth({ children }: { children: ReactNode }) {
  const t = useT();
  const status = useSessionStore((s) => s.status);

  if (status === 'idle' || status === 'loading') {
    return <div role="status">{t('common.loading')}</div>;
  }
  if (status === 'anonymous') {
    return <Navigate to="/auth" replace />;
  }
  return children;
}

import { Outlet, useLocation } from 'react-router-dom';

import { ChatListPage } from '../pages/ChatListPage/ChatListPage';
import styles from './AppLayout.module.css';
import { CallOverlay } from './CallOverlay';
import { useRealtimeSync } from './useRealtimeSync';

/**
 * Десктоп: двухпанельный макет (список слева, содержимое справа) — всегда оба.
 * Мобильный: одноэкранная навигация — на "/" виден список, на вложенных
 * маршрутах (чат, настройки) список скрыт и виден только контент.
 */
export function AppLayout() {
  const { pathname } = useLocation();
  const isDetailRoute = pathname !== '/';
  useRealtimeSync();

  return (
    <div className={styles.root}>
      <aside className={[styles.sidebar, isDetailRoute ? styles.hiddenOnMobile : ''].join(' ')}>
        <ChatListPage />
      </aside>
      <main className={[styles.content, isDetailRoute ? '' : styles.hiddenOnMobile].join(' ')}>
        <Outlet />
      </main>
      <CallOverlay />
    </div>
  );
}

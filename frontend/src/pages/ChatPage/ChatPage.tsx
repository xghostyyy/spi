import { useT } from '../../shared/i18n';
import styles from './ChatPage.module.css';

export function ChatPage() {
  const t = useT();
  return (
    <div className={styles.root}>
      <p>{t('chat.selectChat')}</p>
    </div>
  );
}

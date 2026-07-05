import { Link } from 'react-router-dom';

import { useT } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { GearIcon, SearchIcon } from '../../shared/ui/icons';
import { useSessionStore } from '../../entities/user/store';
import styles from './ChatListPage.module.css';

export function ChatListPage() {
  const t = useT();
  const user = useSessionStore((s) => s.user);

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <Avatar name={user?.displayName ?? '?'} src={user?.avatarUrl} size={36} />
        <Input
          className={styles.searchInput}
          leadingIcon={<SearchIcon size={18} />}
          placeholder={t('chatlist.search')}
        />
        <Link to="/settings">
          <IconButton label={t('nav.settings')}>
            <GearIcon />
          </IconButton>
        </Link>
      </header>

      <div className={styles.empty}>
        <p className={styles.emptyTitle}>{t('chatlist.empty.title')}</p>
        <p className={styles.emptyHint}>{t('chatlist.empty.hint')}</p>
      </div>
    </div>
  );
}

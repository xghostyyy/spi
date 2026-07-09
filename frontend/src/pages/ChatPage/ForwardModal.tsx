import { useQuery } from '@tanstack/react-query';

import { listChats } from '../../features/chats/api';
import { useT } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface ForwardModalProps {
  onSelect: (chatPublicId: string) => void;
  onClose: () => void;
}

export function ForwardModal({ onSelect, onClose }: ForwardModalProps) {
  const t = useT();
  const chatsQuery = useQuery({ queryKey: ['chats'], queryFn: listChats });
  const chats = (chatsQuery.data ?? []).filter((c) => c.type !== 'saved' && !c.isSecret);

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('common.forwardTo')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>
        <div className={styles.modalList}>
          {chats.length === 0 ? (
            <p className={styles.mediaEmpty}>{t('chatlist.empty.title')}</p>
          ) : (
            chats.map((chat) => (
              <button
                key={chat.chatPublicId}
                type="button"
                className={styles.modalRow}
                onClick={() => onSelect(chat.chatPublicId)}
              >
                <Avatar name={chat.title} src={chat.avatarUrl} size={36} />
                <span>{chat.title}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';

import { listContacts } from '../../features/contacts/api';
import { useT } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface ContactPickerProps {
  onSelect: (contact: { name: string; phone: string }) => void;
  onClose: () => void;
}

export function ContactPicker({ onSelect, onClose }: ContactPickerProps) {
  const t = useT();
  const contactsQuery = useQuery({ queryKey: ['contacts'], queryFn: listContacts });
  const contacts = contactsQuery.data ?? [];

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('common.contact')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>
        <div className={styles.modalList}>
          {contacts.length === 0 ? (
            <p className={styles.mediaEmpty}>{t('settings.noContacts')}</p>
          ) : (
            contacts.map((contact) => (
              <button
                key={contact.contactPublicId}
                type="button"
                className={styles.modalRow}
                onClick={() =>
                  onSelect({
                    name: contact.alias ?? contact.displayName,
                    phone: contact.username ? `@${contact.username}` : '',
                  })
                }
              >
                <Avatar name={contact.displayName} src={contact.avatarUrl} size={36} />
                <span>{contact.alias ?? contact.displayName}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

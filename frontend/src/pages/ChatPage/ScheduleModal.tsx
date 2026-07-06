import { useState } from 'react';

import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface ScheduleModalProps {
  initialValue?: string;
  onClose: () => void;
  onConfirm: (isoDateTime: string) => void;
}

function defaultLocalValue(): string {
  const d = new Date(Date.now() + 5 * 60 * 1000);
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function ScheduleModal({ initialValue, onClose, onConfirm }: ScheduleModalProps) {
  const t = useT();
  const [value, setValue] = useState(initialValue ?? defaultLocalValue());

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('schedule.title')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>
        <div className={styles.pollCreatorBody}>
          <input
            type="datetime-local"
            className={styles.scheduleInput}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <Button
            size="lg"
            disabled={!value}
            onClick={() => {
              const iso = new Date(value).toISOString();
              onConfirm(iso);
            }}
          >
            {t('schedule.confirm')}
          </Button>
        </div>
      </div>
    </div>
  );
}

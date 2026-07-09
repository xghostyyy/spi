import { useEffect, type ReactNode } from 'react';

import { useT, type TranslationKey } from '../../shared/i18n';
import {
  ContactIcon,
  FileIcon,
  ImageIcon,
  LocationIcon,
  PollIcon,
  StickerIcon,
  VideoCircleIcon,
  VideoIcon,
} from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

export interface AttachMenuProps {
  onClose: () => void;
  onPhoto: () => void;
  onVideo: () => void;
  onFile: () => void;
  onVideoNote: () => void;
  onLocation: () => void;
  onContact: () => void;
  onPoll: () => void;
  onSticker: () => void;
}

interface Item {
  key: TranslationKey;
  icon: ReactNode;
  action: keyof Omit<AttachMenuProps, 'onClose'>;
}

const ITEMS: Item[] = [
  { key: 'attach.photo', icon: <ImageIcon size={20} />, action: 'onPhoto' },
  { key: 'attach.video', icon: <VideoIcon size={20} />, action: 'onVideo' },
  { key: 'attach.file', icon: <FileIcon size={20} />, action: 'onFile' },
  { key: 'attach.videoNote', icon: <VideoCircleIcon size={20} />, action: 'onVideoNote' },
  { key: 'attach.location', icon: <LocationIcon size={20} />, action: 'onLocation' },
  { key: 'attach.contact', icon: <ContactIcon size={20} />, action: 'onContact' },
  { key: 'attach.poll', icon: <PollIcon size={20} />, action: 'onPoll' },
  { key: 'attach.sticker', icon: <StickerIcon size={20} />, action: 'onSticker' },
];

/** Всплывающее меню вложений над кнопкой «+» композера (см. ADR-025). */
export function AttachMenu(props: AttachMenuProps) {
  const t = useT();
  const { onClose } = props;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <>
      <button
        type="button"
        className={styles.attachBackdrop}
        aria-label={t('common.cancel')}
        onClick={onClose}
      />
      <div className={styles.attachMenu} role="menu">
        {ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="menuitem"
            className={styles.attachMenuItem}
            onClick={() => {
              onClose();
              (props[item.action] as () => void)();
            }}
          >
            <span className={styles.attachMenuIcon}>{item.icon}</span>
            {t(item.key)}
          </button>
        ))}
      </div>
    </>
  );
}

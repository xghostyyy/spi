import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { exportChat, getChatMedia, type MediaTab } from '../../features/chats/api';
import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon, FileIcon } from '../../shared/ui/icons';
import { VoicePlayer } from './VoicePlayer';
import styles from './ChatPage.module.css';

interface MediaArchiveModalProps {
  chatPublicId: string;
  onClose: () => void;
}

const TABS: {
  tab: MediaTab;
  labelKey: 'media.tabs.media' | 'media.tabs.files' | 'media.tabs.voice' | 'media.tabs.links';
}[] = [
  { tab: 'media', labelKey: 'media.tabs.media' },
  { tab: 'files', labelKey: 'media.tabs.files' },
  { tab: 'links', labelKey: 'media.tabs.links' },
  { tab: 'voice', labelKey: 'media.tabs.voice' },
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function MediaArchiveModal({ chatPublicId, onClose }: MediaArchiveModalProps) {
  const t = useT();
  const [tab, setTab] = useState<MediaTab>('media');

  const mediaQuery = useQuery({
    queryKey: ['chat-media', chatPublicId, tab],
    queryFn: () => getChatMedia(chatPublicId, tab),
  });
  const messages = mediaQuery.data ?? [];

  const exportMutation = useMutation({
    mutationFn: (format: 'json' | 'html') => exportChat(chatPublicId, format),
  });

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('media.title')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>
        <div className={styles.mediaTabs}>
          {TABS.map(({ tab: tabValue, labelKey }) => (
            <button
              key={tabValue}
              type="button"
              className={[styles.mediaTab, tab === tabValue ? styles.mediaTabActive : ''].join(' ')}
              onClick={() => setTab(tabValue)}
            >
              {t(labelKey)}
            </button>
          ))}
        </div>

        <div className={styles.modalList}>
          {messages.length === 0 ? (
            <p className={styles.mediaEmpty}>{t('media.empty')}</p>
          ) : tab === 'media' ? (
            <div className={styles.mediaGridArchive}>
              {messages.flatMap((m) =>
                m.attachments.map((a) => (
                  <a key={a.publicId} href={a.url} target="_blank" rel="noreferrer">
                    <img
                      className={styles.mediaGridThumb}
                      src={a.thumbUrl ?? a.url}
                      alt=""
                      loading="lazy"
                    />
                  </a>
                )),
              )}
            </div>
          ) : tab === 'files' ? (
            messages.flatMap((m) =>
              m.attachments.map((a) => (
                <a
                  key={a.publicId}
                  href={a.url}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.modalRow}
                >
                  <FileIcon size={28} />
                  <span className={styles.fileInfo}>
                    <span className={styles.fileName}>{a.originalName ?? a.publicId}</span>
                    <span className={styles.fileSize}>{formatSize(a.sizeBytes)}</span>
                  </span>
                </a>
              )),
            )
          ) : tab === 'voice' ? (
            messages.flatMap((m) =>
              m.attachments.map((a) => (
                <div key={a.publicId} className={styles.modalRow}>
                  <VoicePlayer file={a} />
                </div>
              )),
            )
          ) : (
            messages.map((m) => (
              <div key={m.messagePublicId} className={styles.modalRow}>
                <span className={styles.fileInfo}>
                  <span className={styles.fileName}>{m.body}</span>
                </span>
              </div>
            ))
          )}
        </div>

        <div className={styles.exportRow}>
          <Button
            variant="secondary"
            size="md"
            type="button"
            disabled={exportMutation.isPending}
            onClick={() => exportMutation.mutate('json')}
          >
            {t('media.export.json')}
          </Button>
          <Button
            variant="secondary"
            size="md"
            type="button"
            disabled={exportMutation.isPending}
            onClick={() => exportMutation.mutate('html')}
          >
            {t('media.export.html')}
          </Button>
        </div>
      </div>
    </div>
  );
}

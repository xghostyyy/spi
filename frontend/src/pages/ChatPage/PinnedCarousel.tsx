import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Message } from '../../entities/message/model';
import { listPinnedMessages, unpinMessage } from '../../features/groups/api';
import { useT, type TranslationKey } from '../../shared/i18n';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon, PinIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

const PREVIEW_KEY_BY_TYPE: Partial<Record<string, TranslationKey>> = {
  photo: 'preview.photo',
  video: 'preview.video',
  voice: 'preview.voice',
  audio: 'preview.audio',
  document: 'preview.document',
  album: 'preview.album',
};

function previewText(message: Message, t: (key: TranslationKey) => string): string {
  if (message.deletedForAll) return '';
  if (message.body) return message.body;
  const key = PREVIEW_KEY_BY_TYPE[message.type];
  return key ? t(key) : '';
}

interface PinnedCarouselProps {
  chatPublicId: string;
  canUnpin: boolean;
  onMessageClick: (messagePublicId: string) => void;
}

export function PinnedCarousel({ chatPublicId, canUnpin, onMessageClick }: PinnedCarouselProps) {
  const t = useT();
  const queryClient = useQueryClient();
  const [index, setIndex] = useState(0);

  const pinnedQuery = useQuery({
    queryKey: ['pinned', chatPublicId],
    queryFn: () => listPinnedMessages(chatPublicId),
  });
  const pinned = pinnedQuery.data ?? [];

  const unpinMutation = useMutation({
    mutationFn: (messagePublicId: string) => unpinMessage(chatPublicId, messagePublicId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['pinned', chatPublicId] }),
  });

  if (pinned.length === 0) return null;

  const current = pinned[Math.min(index, pinned.length - 1)]!;

  return (
    <div className={styles.pinnedBar}>
      <button
        type="button"
        className={styles.pinnedContent}
        onClick={() => {
          onMessageClick(current.messagePublicId);
          setIndex((i) => (i + 1) % pinned.length);
        }}
      >
        <PinIcon size={16} />
        <span className={styles.pinnedText}>{previewText(current, t)}</span>
        {pinned.length > 1 ? (
          <span className={styles.pinnedCount}>
            {index + 1}/{pinned.length}
          </span>
        ) : null}
      </button>
      {canUnpin ? (
        <IconButton
          label={t('common.remove')}
          onClick={() => unpinMutation.mutate(current.messagePublicId)}
        >
          <CloseIcon size={14} />
        </IconButton>
      ) : null}
    </div>
  );
}

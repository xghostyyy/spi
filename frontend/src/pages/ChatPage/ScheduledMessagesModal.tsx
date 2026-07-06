import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Message } from '../../entities/message/model';
import {
  cancelScheduledMessage,
  listScheduledMessages,
  rescheduleMessage,
} from '../../features/messages/api';
import { useT } from '../../shared/i18n';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon, PencilIcon, TrashIcon } from '../../shared/ui/icons';
import { ScheduleModal } from './ScheduleModal';
import styles from './ChatPage.module.css';

interface ScheduledMessagesModalProps {
  chatPublicId: string;
  onClose: () => void;
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString([], {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ScheduledMessagesModal({ chatPublicId, onClose }: ScheduledMessagesModalProps) {
  const t = useT();
  const queryClient = useQueryClient();
  const [rescheduling, setRescheduling] = useState<Message | null>(null);

  const scheduledQuery = useQuery({
    queryKey: ['scheduled', chatPublicId],
    queryFn: () => listScheduledMessages(chatPublicId),
  });
  const messages = scheduledQuery.data ?? [];

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['scheduled', chatPublicId] });
  }

  const cancelMutation = useMutation({
    mutationFn: (messagePublicId: string) => cancelScheduledMessage(chatPublicId, messagePublicId),
    onSuccess: invalidate,
  });

  const rescheduleMutation = useMutation({
    mutationFn: ({
      messagePublicId,
      isoDateTime,
    }: {
      messagePublicId: string;
      isoDateTime: string;
    }) => rescheduleMessage(chatPublicId, messagePublicId, isoDateTime),
    onSuccess: () => {
      invalidate();
      setRescheduling(null);
    },
  });

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('schedule.list.title')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>
        <div className={styles.modalList}>
          {messages.length === 0 ? (
            <p className={styles.mediaEmpty}>{t('schedule.list.empty')}</p>
          ) : (
            messages.map((message) => (
              <div key={message.messagePublicId} className={styles.modalRow}>
                <span className={styles.fileInfo}>
                  <span className={styles.fileName}>{message.body}</span>
                  <span className={styles.fileSize}>
                    {message.scheduledAt ? formatWhen(message.scheduledAt) : ''}
                  </span>
                </span>
                <IconButton
                  label={t('schedule.reschedule')}
                  onClick={() => setRescheduling(message)}
                >
                  <PencilIcon size={16} />
                </IconButton>
                <IconButton
                  label={t('common.remove')}
                  onClick={() => cancelMutation.mutate(message.messagePublicId)}
                >
                  <TrashIcon size={16} />
                </IconButton>
              </div>
            ))
          )}
        </div>
      </div>

      {rescheduling ? (
        <ScheduleModal
          onClose={() => setRescheduling(null)}
          onConfirm={(isoDateTime) =>
            rescheduleMutation.mutate({
              messagePublicId: rescheduling.messagePublicId,
              isoDateTime,
            })
          }
        />
      ) : null}
    </div>
  );
}

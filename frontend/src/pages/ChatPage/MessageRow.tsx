import { useState } from 'react';

import type { Message } from '../../entities/message/model';
import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { MessageBubble } from '../../shared/ui/MessageBubble';
import { PencilIcon, ReplyIcon, TrashIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface MessageRowProps {
  message: Message;
  isOwn: boolean;
  quotedMessage: Message | undefined;
  onReply: () => void;
  onQuoteClick: () => void;
  onToggleHeart: () => void;
  onEdit: (body: string) => void;
  onDelete: (scope: 'self' | 'all') => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function MessageRow({
  message,
  isOwn,
  quotedMessage,
  onReply,
  onQuoteClick,
  onToggleHeart,
  onEdit,
  onDelete,
}: MessageRowProps) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.body ?? '');
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  if (editing) {
    return (
      <div className={styles.editRow} data-message-id={message.messagePublicId}>
        <textarea
          className={styles.editTextarea}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoFocus
        />
        <div className={styles.editActions}>
          <Button
            variant="secondary"
            size="md"
            type="button"
            onClick={() => {
              setEditing(false);
              setDraft(message.body ?? '');
            }}
          >
            {t('common.cancel')}
          </Button>
          <Button
            size="md"
            type="button"
            onClick={() => {
              if (draft.trim()) onEdit(draft.trim());
              setEditing(false);
            }}
          >
            {t('common.save')}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={[styles.messageWrap, isOwn ? styles.messageWrapOut : ''].join(' ')}
      data-message-id={message.messagePublicId}
      onDoubleClick={onToggleHeart}
    >
      <div className={styles.messageActions}>
        <button
          type="button"
          className={styles.actionIcon}
          onClick={onReply}
          aria-label={t('common.reply')}
        >
          <ReplyIcon size={16} />
        </button>
        {isOwn && !message.deletedForAll ? (
          <button
            type="button"
            className={styles.actionIcon}
            onClick={() => setEditing(true)}
            aria-label={t('common.save')}
          >
            <PencilIcon size={16} />
          </button>
        ) : null}
        {!message.deletedForAll ? (
          <button
            type="button"
            className={styles.actionIcon}
            onClick={() => setConfirmingDelete(true)}
            aria-label={t('common.remove')}
          >
            <TrashIcon size={16} />
          </button>
        ) : null}
      </div>

      {quotedMessage ? (
        <button type="button" className={styles.quote} onClick={onQuoteClick}>
          {quotedMessage.deletedForAll ? '…' : (quotedMessage.body ?? '')}
        </button>
      ) : message.replyToPublicId ? (
        <div className={styles.quote}>…</div>
      ) : null}

      <MessageBubble
        out={isOwn}
        time={formatTime(message.createdAt)}
        status={isOwn ? message.status : undefined}
        edited={!!message.editedAt}
      >
        {message.deletedForAll ? <em>{t('chat.deleted')}</em> : message.body}
      </MessageBubble>

      {message.reactions.length > 0 ? (
        <div className={[styles.reactions, isOwn ? styles.reactionsOut : ''].join(' ')}>
          {message.reactions.map((r) => (
            <span
              key={r.emoji}
              className={[styles.reactionChip, r.reactedByMe ? styles.reactionChipMine : ''].join(
                ' ',
              )}
            >
              {r.emoji} {r.count}
            </span>
          ))}
        </div>
      ) : null}

      {confirmingDelete ? (
        <div className={styles.deleteConfirm}>
          {isOwn ? (
            <button type="button" onClick={() => onDelete('all')}>
              {t('common.deleteForAll')}
            </button>
          ) : null}
          <button type="button" onClick={() => onDelete('self')}>
            {t('common.deleteForMe')}
          </button>
          <button type="button" onClick={() => setConfirmingDelete(false)}>
            {t('common.cancel')}
          </button>
        </div>
      ) : null}
    </div>
  );
}

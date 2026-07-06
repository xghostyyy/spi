import { useState } from 'react';

import type {
  CallPayload,
  ContactPayload,
  GifPayload,
  LocationPayload,
  Message,
  StickerPayload,
} from '../../entities/message/model';
import { useT, type TranslationKey } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { MessageBubble } from '../../shared/ui/MessageBubble';
import {
  BookmarkFilledIcon,
  BookmarkIcon,
  ContactIcon,
  ForwardIcon,
  LocationIcon,
  PencilIcon,
  PhoneIcon,
  PinIcon,
  ReplyIcon,
  TrashIcon,
  VideoIcon,
} from '../../shared/ui/icons';
import styles from './ChatPage.module.css';
import { MessageAttachments } from './MessageAttachments';
import { PollView } from './PollView';

interface MessageRowProps {
  message: Message;
  isOwn: boolean;
  quotedMessage: Message | undefined;
  onReply: () => void;
  onQuoteClick: () => void;
  onToggleHeart: () => void;
  onEdit: (body: string) => void;
  onDelete: (scope: 'self' | 'all') => void;
  onImageClick: (url: string) => void;
  onToggleBookmark: () => void;
  onForward: () => void;
  onPin?: () => void;
  onVotePoll: (optionPositions: number[]) => void;
  onClosePoll: () => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatCallDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

const MENTION_RE = /@[a-zA-Z][a-zA-Z0-9_]{2,31}/g;

function renderWithMentions(text: string) {
  const parts = text.split(MENTION_RE);
  const mentions = text.match(MENTION_RE) ?? [];
  if (mentions.length === 0) return text;
  const nodes: (string | JSX.Element)[] = [];
  parts.forEach((part, i) => {
    nodes.push(part);
    if (mentions[i]) {
      nodes.push(
        <span key={i} className={styles.mention}>
          {mentions[i]}
        </span>,
      );
    }
  });
  return nodes;
}

interface SpecialContentProps {
  message: Message;
  isOwn: boolean;
  onVotePoll: (optionPositions: number[]) => void;
  onClosePoll: () => void;
  onImageClick: (url: string) => void;
}

function SpecialContent({
  message,
  isOwn,
  onVotePoll,
  onClosePoll,
  onImageClick,
}: SpecialContentProps) {
  const t = useT();
  if (message.type === 'poll' && message.poll) {
    return <PollView poll={message.poll} isOwn={isOwn} onVote={onVotePoll} onClose={onClosePoll} />;
  }
  if (message.type === 'call' && message.payload) {
    const call = message.payload as CallPayload;
    const Icon = call.kind === 'video' ? VideoIcon : PhoneIcon;
    const label = t(`call.log.${call.outcome}` as TranslationKey);
    const duration =
      call.outcome === 'answered' && call.duration_seconds != null
        ? formatCallDuration(call.duration_seconds)
        : null;
    return (
      <div className={styles.fileCard}>
        <Icon size={28} />
        <span className={styles.fileInfo}>
          <span className={styles.fileName}>{label}</span>
          {duration ? <span className={styles.fileSize}>{duration}</span> : null}
        </span>
      </div>
    );
  }
  if (message.type === 'sticker' && message.payload) {
    const sticker = message.payload as StickerPayload;
    return (
      <img
        src={sticker.url}
        alt={sticker.emoji}
        className={styles.stickerImage}
        onClick={() => onImageClick(sticker.url)}
      />
    );
  }
  if (message.type === 'gif' && message.payload) {
    const gif = message.payload as GifPayload;
    return (
      <img
        src={gif.url}
        alt=""
        className={styles.mediaImage}
        onClick={() => onImageClick(gif.url)}
      />
    );
  }
  if (message.type === 'contact' && message.payload) {
    const contact = message.payload as ContactPayload;
    return (
      <div className={styles.fileCard}>
        <ContactIcon size={28} />
        <span className={styles.fileInfo}>
          <span className={styles.fileName}>{contact.name}</span>
          <span className={styles.fileSize}>{contact.phone}</span>
        </span>
      </div>
    );
  }
  if (message.type === 'location' && message.payload) {
    const location = message.payload as LocationPayload;
    return (
      <a
        className={styles.fileCard}
        href={`https://www.google.com/maps?q=${location.lat},${location.lng}`}
        target="_blank"
        rel="noreferrer"
      >
        <LocationIcon size={28} />
        <span className={styles.fileInfo}>
          <span className={styles.fileName}>{t('common.location')}</span>
          <span className={styles.fileSize}>{t('common.openMap')}</span>
        </span>
      </a>
    );
  }
  return null;
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
  onImageClick,
  onToggleBookmark,
  onForward,
  onPin,
  onVotePoll,
  onClosePoll,
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
        {!message.deletedForAll ? (
          <button
            type="button"
            className={styles.actionIcon}
            onClick={onForward}
            aria-label={t('common.forward')}
          >
            <ForwardIcon size={16} />
          </button>
        ) : null}
        {!message.deletedForAll ? (
          <button
            type="button"
            className={styles.actionIcon}
            onClick={onToggleBookmark}
            aria-label={t('chatlist.savedMessages')}
          >
            {message.bookmarked ? <BookmarkFilledIcon size={16} /> : <BookmarkIcon size={16} />}
          </button>
        ) : null}
        {!message.deletedForAll && onPin ? (
          <button
            type="button"
            className={styles.actionIcon}
            onClick={onPin}
            aria-label={t('common.pin')}
          >
            <PinIcon size={16} />
          </button>
        ) : null}
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
        {message.deletedForAll ? (
          <em>{t('chat.deleted')}</em>
        ) : (
          <>
            {message.forwardedFromUserPublicId ? (
              <div className={styles.forwardedLabel}>{t('common.forwardedFrom')}</div>
            ) : null}
            <SpecialContent
              message={message}
              isOwn={isOwn}
              onVotePoll={onVotePoll}
              onClosePoll={onClosePoll}
              onImageClick={onImageClick}
            />
            <MessageAttachments
              attachments={message.attachments}
              type={message.type}
              onImageClick={onImageClick}
            />
            {message.body ? (
              <div className={styles.caption}>{renderWithMentions(message.body)}</div>
            ) : null}
          </>
        )}
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

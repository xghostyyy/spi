import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { Chat } from '../../entities/chat/model';
import type { Message } from '../../entities/message/model';
import { useSessionStore } from '../../entities/user/store';
import { listChats } from '../../features/chats/api';
import {
  deleteMessage,
  editMessage,
  listMessages,
  sendMessage,
  toggleReaction,
} from '../../features/messages/api';
import { pluralRu, useLocaleStore, useT } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { BackIcon, CloseIcon, PaperclipIcon, PhoneIcon, SendIcon } from '../../shared/ui/icons';
import { wsClient } from '../../shared/ws/client';
import { useTypingStore } from '../../shared/ws/typingStore';
import { MessageRow } from './MessageRow';
import styles from './ChatPage.module.css';

const TYPING_IDLE_MS = 3000;

function dayKey(iso: string): string {
  return new Date(iso).toDateString();
}

function formatDateSeparator(
  iso: string,
  t: (k: 'chat.today' | 'chat.yesterday') => string,
): string {
  const date = new Date(iso);
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === now.toDateString()) return t('chat.today');
  if (date.toDateString() === yesterday.toDateString()) return t('chat.yesterday');
  return date.toLocaleDateString([], { day: '2-digit', month: 'long', year: 'numeric' });
}

function formatPresence(chat: Chat, locale: 'ru' | 'en', t: (k: 'chat.online') => string): string {
  if (chat.peerOnline) return t('chat.online');
  if (!chat.peerLastSeenAt) return '';
  const minutes = Math.max(
    0,
    Math.round((Date.now() - new Date(chat.peerLastSeenAt).getTime()) / 60000),
  );
  if (minutes < 1) return t('chat.online');

  if (locale === 'ru') {
    if (minutes < 60) {
      return `был(а) в сети ${minutes} ${pluralRu(minutes, 'минуту', 'минуты', 'минут')} назад`;
    }
    const hours = Math.round(minutes / 60);
    if (hours < 24)
      return `был(а) в сети ${hours} ${pluralRu(hours, 'час', 'часа', 'часов')} назад`;
    return '';
  }

  if (minutes < 60) return `last seen ${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `last seen ${hours}h ago` : '';
}

export function ChatPage() {
  const t = useT();
  const locale = useLocaleStore((s) => s.locale);
  const { chatId } = useParams<{ chatId: string }>();
  const queryClient = useQueryClient();
  const me = useSessionStore((s) => s.user);

  const [draft, setDraft] = useState('');
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const typingActiveRef = useRef(false);
  const typingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const chatsQuery = useQuery({ queryKey: ['chats'], queryFn: listChats });
  const chat = chatsQuery.data?.find((c) => c.chatPublicId === chatId);
  const typing = useTypingStore((s) => (chatId ? s.byChat[chatId] : null));

  const messagesQuery = useQuery({
    queryKey: ['messages', chatId],
    queryFn: () => listMessages(chatId!),
    enabled: !!chatId,
  });
  const messages = useMemo(() => messagesQuery.data ?? [], [messagesQuery.data]);

  const messageByPublicId = useMemo(() => {
    const map = new Map<string, Message>();
    for (const m of messages) map.set(m.messagePublicId, m);
    return map;
  }, [messages]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages.length]);

  useEffect(() => {
    if (!chatId || messages.length === 0) return;
    const last = messages[messages.length - 1]!;
    wsClient.send('read', { chat_id: chatId, message_id: last.messagePublicId });
  }, [chatId, messages]);

  const sendMutation = useMutation({
    mutationFn: (body: string) =>
      sendMessage(chatId!, {
        clientMsgId: crypto.randomUUID(),
        body,
        replyToPublicId: replyTo?.messagePublicId,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['messages', chatId] });
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
    },
  });

  const editMutation = useMutation({
    mutationFn: ({ messagePublicId, body }: { messagePublicId: string; body: string }) =>
      editMessage(chatId!, messagePublicId, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['messages', chatId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ messagePublicId, scope }: { messagePublicId: string; scope: 'self' | 'all' }) =>
      deleteMessage(chatId!, messagePublicId, scope),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['messages', chatId] }),
  });

  const reactionMutation = useMutation({
    mutationFn: ({ messagePublicId }: { messagePublicId: string }) =>
      toggleReaction(chatId!, messagePublicId, '❤️'),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['messages', chatId] }),
  });

  function handleDraftChange(value: string) {
    setDraft(value);
    if (!chatId) return;
    if (value && !typingActiveRef.current) {
      typingActiveRef.current = true;
      wsClient.send('typing', { chat_id: chatId, kind: 'text', active: true });
    }
    if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
    typingTimerRef.current = setTimeout(() => {
      typingActiveRef.current = false;
      wsClient.send('typing', { chat_id: chatId, kind: 'text', active: false });
    }, TYPING_IDLE_MS);
  }

  function handleSend() {
    const body = draft.trim();
    if (!body || !chatId) return;
    sendMutation.mutate(body);
    setDraft('');
    setReplyTo(null);
    typingActiveRef.current = false;
    wsClient.send('typing', { chat_id: chatId, kind: 'text', active: false });
  }

  if (!chatId) {
    return (
      <div className={styles.placeholder}>
        <p>{t('chat.selectChat')}</p>
      </div>
    );
  }

  let lastDay = '';

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <Link to="/" className={styles.backLink}>
          <IconButton label={t('nav.back')}>
            <BackIcon />
          </IconButton>
        </Link>
        <Avatar
          name={chat?.title ?? '…'}
          src={chat?.avatarUrl}
          size={40}
          online={chat?.peerOnline}
        />
        <div className={styles.headerInfo}>
          <span className={styles.headerTitle}>{chat?.title ?? '…'}</span>
          <span className={styles.headerStatus}>
            {typing ? t('chat.typing') : chat ? formatPresence(chat, locale, t) : ''}
          </span>
        </div>
        <IconButton label={t('chat.call')} onClick={() => alert(t('chat.callsSoon'))}>
          <PhoneIcon />
        </IconButton>
      </header>

      <div className={styles.list} ref={listRef}>
        {messages.map((message) => {
          const showSeparator = dayKey(message.createdAt) !== lastDay;
          lastDay = dayKey(message.createdAt);
          return (
            <div key={message.messagePublicId}>
              {showSeparator ? (
                <div className={styles.dateSeparator}>
                  <span>{formatDateSeparator(message.createdAt, t)}</span>
                </div>
              ) : null}
              <MessageRow
                message={message}
                isOwn={message.senderPublicId === me?.publicId}
                quotedMessage={
                  message.replyToPublicId
                    ? messageByPublicId.get(message.replyToPublicId)
                    : undefined
                }
                onReply={() => setReplyTo(message)}
                onQuoteClick={() => {
                  const el = listRef.current?.querySelector(
                    `[data-message-id="${message.replyToPublicId}"]`,
                  );
                  el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }}
                onToggleHeart={() =>
                  reactionMutation.mutate({ messagePublicId: message.messagePublicId })
                }
                onEdit={(body) =>
                  editMutation.mutate({ messagePublicId: message.messagePublicId, body })
                }
                onDelete={(scope) =>
                  deleteMutation.mutate({ messagePublicId: message.messagePublicId, scope })
                }
              />
            </div>
          );
        })}
      </div>

      <div className={styles.composer}>
        {replyTo ? (
          <div className={styles.replyPreview}>
            <span className={styles.replyText}>
              {t('chat.replyingTo')}: {replyTo.deletedForAll ? '…' : replyTo.body}
            </span>
            <button
              type="button"
              className={styles.replyCancel}
              onClick={() => setReplyTo(null)}
              aria-label={t('common.cancel')}
            >
              <CloseIcon size={14} />
            </button>
          </div>
        ) : null}
        <div className={styles.composerRow}>
          <IconButton label={t('chat.attach')} disabled>
            <PaperclipIcon />
          </IconButton>
          <Input
            className={styles.composerInput}
            placeholder={t('chat.placeholder')}
            value={draft}
            onChange={(e) => handleDraftChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <Button
            variant="primary"
            size="md"
            type="button"
            onClick={handleSend}
            disabled={!draft.trim()}
          >
            <SendIcon size={18} />
          </Button>
        </div>
      </div>
    </div>
  );
}

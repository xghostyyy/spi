import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { Chat } from '../../entities/chat/model';
import type { FileKind, Message } from '../../entities/message/model';
import { useSessionStore } from '../../entities/user/store';
import { toggleBookmark } from '../../features/bookmarks/api';
import { listChats } from '../../features/chats/api';
import { guessFileKind, uploadFile } from '../../features/files/api';
import { pinMessage } from '../../features/groups/api';
import { useVoiceRecorder } from '../../features/messages/useVoiceRecorder';
import { ContactPicker } from './ContactPicker';
import { ForwardModal } from './ForwardModal';
import { InviteModal } from './InviteModal';
import { PinnedCarousel } from './PinnedCarousel';
import { PollCreator } from './PollCreator';
import {
  closePoll,
  deleteMessage,
  editMessage,
  listMessages,
  sendMessage,
  toggleReaction,
  votePoll,
} from '../../features/messages/api';
import { pluralRu, useLocaleStore, useT } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import {
  BackIcon,
  CloseIcon,
  ContactIcon,
  LinkIcon,
  LocationIcon,
  MicIcon,
  PaperclipIcon,
  PhoneIcon,
  PollIcon,
  SendIcon,
  TrashIcon,
} from '../../shared/ui/icons';
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
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [forwardingMessage, setForwardingMessage] = useState<Message | null>(null);
  const [showContactPicker, setShowContactPicker] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showPollCreator, setShowPollCreator] = useState(false);
  const typingActiveRef = useRef(false);
  const typingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const voiceRecorder = useVoiceRecorder();

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

  const sendMediaMutation = useMutation({
    mutationFn: async (input: {
      file: File | Blob;
      kind: FileKind;
      durationMs?: number;
      waveform?: number[];
    }) => {
      const uploaded = await uploadFile(input.file, input.kind, {
        durationMs: input.durationMs,
        waveform: input.waveform,
      });
      return sendMessage(chatId!, {
        clientMsgId: crypto.randomUUID(),
        filePublicIds: [uploaded.publicId],
        replyToPublicId: replyTo?.messagePublicId,
      });
    },
    onMutate: () => setUploading(true),
    onSettled: () => setUploading(false),
    onSuccess: () => {
      setReplyTo(null);
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

  const bookmarkMutation = useMutation({
    mutationFn: (messagePublicId: string) => toggleBookmark(messagePublicId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['messages', chatId] });
      void queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
    },
  });

  const pinMutation = useMutation({
    mutationFn: (messagePublicId: string) => pinMessage(chatId!, messagePublicId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['pinned', chatId] }),
  });

  const forwardMutation = useMutation({
    mutationFn: ({
      targetChatPublicId,
      messagePublicId,
    }: {
      targetChatPublicId: string;
      messagePublicId: string;
    }) =>
      sendMessage(targetChatPublicId, {
        clientMsgId: crypto.randomUUID(),
        forwardFromMessagePublicId: messagePublicId,
      }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['messages', variables.targetChatPublicId] });
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
    },
  });

  const contactMutation = useMutation({
    mutationFn: (contact: { name: string; phone: string }) =>
      sendMessage(chatId!, { clientMsgId: crypto.randomUUID(), contact }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['messages', chatId] });
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
    },
  });

  const locationMutation = useMutation({
    mutationFn: (location: { lat: number; lng: number }) =>
      sendMessage(chatId!, { clientMsgId: crypto.randomUUID(), location }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['messages', chatId] });
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
    },
  });

  const pollMutation = useMutation({
    mutationFn: (poll: {
      question: string;
      options: string[];
      isAnonymous: boolean;
      multiChoice: boolean;
    }) => sendMessage(chatId!, { clientMsgId: crypto.randomUUID(), poll }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['messages', chatId] });
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
    },
  });

  const voteMutation = useMutation({
    mutationFn: ({
      messagePublicId,
      optionPositions,
    }: {
      messagePublicId: string;
      optionPositions: number[];
    }) => votePoll(chatId!, messagePublicId, optionPositions),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['messages', chatId] }),
  });

  const closePollMutation = useMutation({
    mutationFn: (messagePublicId: string) => closePoll(chatId!, messagePublicId),
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

  function handleFileSelected(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    sendMediaMutation.mutate({ file, kind: guessFileKind(file) });
  }

  async function handleStopAndSendVoice() {
    const recording = await voiceRecorder.stop();
    if (recording) {
      sendMediaMutation.mutate({
        file: recording.blob,
        kind: 'voice',
        durationMs: recording.durationMs,
        waveform: recording.waveform,
      });
    }
  }

  function handleCancelVoice() {
    voiceRecorder.cancel();
  }

  function handleSendLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((position) => {
      locationMutation.mutate({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      });
    });
  }

  if (!chatId) {
    return (
      <div className={styles.placeholder}>
        <p>{t('chat.selectChat')}</p>
      </div>
    );
  }

  const isSaved = chat?.type === 'saved';
  const displayTitle = isSaved ? t('chatlist.savedMessages') : (chat?.title ?? '…');

  let lastDay = '';

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <Link to="/" className={styles.backLink}>
          <IconButton label={t('nav.back')}>
            <BackIcon />
          </IconButton>
        </Link>
        <Avatar name={displayTitle} src={chat?.avatarUrl} size={40} online={chat?.peerOnline} />
        <div className={styles.headerInfo}>
          <span className={styles.headerTitle}>{displayTitle}</span>
          <span className={styles.headerStatus}>
            {typing ? t('chat.typing') : chat && !isSaved ? formatPresence(chat, locale, t) : ''}
          </span>
        </div>
        {chat?.type === 'group' ? (
          <IconButton label={t('group.invite.create')} onClick={() => setShowInviteModal(true)}>
            <LinkIcon />
          </IconButton>
        ) : null}
        {!isSaved ? (
          <IconButton label={t('chat.call')} onClick={() => alert(t('chat.callsSoon'))}>
            <PhoneIcon />
          </IconButton>
        ) : null}
      </header>

      {chat?.type === 'group' ? (
        <PinnedCarousel
          chatPublicId={chatId}
          canUnpin={chat.myRole === 'owner' || chat.myRole === 'admin'}
          onMessageClick={(messagePublicId) => {
            const el = listRef.current?.querySelector(`[data-message-id="${messagePublicId}"]`);
            el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }}
        />
      ) : null}

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
                onImageClick={setLightboxUrl}
                onToggleBookmark={() => bookmarkMutation.mutate(message.messagePublicId)}
                onForward={() => setForwardingMessage(message)}
                onPin={
                  chat?.type === 'group'
                    ? () => pinMutation.mutate(message.messagePublicId)
                    : undefined
                }
                onVotePoll={(optionPositions) =>
                  voteMutation.mutate({ messagePublicId: message.messagePublicId, optionPositions })
                }
                onClosePoll={() => closePollMutation.mutate(message.messagePublicId)}
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
        {voiceRecorder.isRecording ? (
          <div className={styles.composerRow}>
            <IconButton label={t('common.cancel')} onClick={handleCancelVoice}>
              <TrashIcon />
            </IconButton>
            <span className={styles.recordingIndicator}>{t('chat.recordingVoice')}</span>
            <IconButton
              label={t('chat.voiceMessage')}
              variant="accent"
              onClick={() => void handleStopAndSendVoice()}
            >
              <SendIcon size={18} />
            </IconButton>
          </div>
        ) : (
          <div className={styles.composerRow}>
            <input
              ref={fileInputRef}
              type="file"
              hidden
              onChange={handleFileSelected}
              accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.zip,.rar,.txt"
            />
            <IconButton
              label={t('chat.attach')}
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              <PaperclipIcon />
            </IconButton>
            <IconButton label={t('common.location')} onClick={handleSendLocation}>
              <LocationIcon />
            </IconButton>
            <IconButton label={t('common.contact')} onClick={() => setShowContactPicker(true)}>
              <ContactIcon />
            </IconButton>
            <IconButton label={t('poll.create')} onClick={() => setShowPollCreator(true)}>
              <PollIcon />
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
            {draft.trim() ? (
              <Button variant="primary" size="md" type="button" onClick={handleSend}>
                <SendIcon size={18} />
              </Button>
            ) : (
              <IconButton
                label={t('chat.voiceMessage')}
                onClick={() => void voiceRecorder.start()}
                disabled={uploading}
              >
                <MicIcon />
              </IconButton>
            )}
          </div>
        )}
      </div>

      {lightboxUrl ? (
        <div className={styles.lightbox} onClick={() => setLightboxUrl(null)}>
          <img src={lightboxUrl} alt="" className={styles.lightboxImage} />
          <IconButton
            label={t('common.cancel')}
            className={styles.lightboxClose}
            onClick={() => setLightboxUrl(null)}
          >
            <CloseIcon />
          </IconButton>
        </div>
      ) : null}

      {forwardingMessage ? (
        <ForwardModal
          onClose={() => setForwardingMessage(null)}
          onSelect={(targetChatPublicId) => {
            forwardMutation.mutate({
              targetChatPublicId,
              messagePublicId: forwardingMessage.messagePublicId,
            });
            setForwardingMessage(null);
          }}
        />
      ) : null}

      {showContactPicker ? (
        <ContactPicker
          onClose={() => setShowContactPicker(false)}
          onSelect={(contact) => {
            contactMutation.mutate(contact);
            setShowContactPicker(false);
          }}
        />
      ) : null}

      {showInviteModal && chatId ? (
        <InviteModal chatPublicId={chatId} onClose={() => setShowInviteModal(false)} />
      ) : null}

      {showPollCreator ? (
        <PollCreator
          onClose={() => setShowPollCreator(false)}
          onSubmit={(poll) => {
            pollMutation.mutate(poll);
            setShowPollCreator(false);
          }}
        />
      ) : null}
    </div>
  );
}

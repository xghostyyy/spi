import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import type { Chat } from '../../entities/chat/model';
import type { Message } from '../../entities/message/model';
import { useSessionStore } from '../../entities/user/store';
import { createDirectChat, getSavedChat, listChats } from '../../features/chats/api';
import { search as searchApi } from '../../features/search/api';
import { useT, type TranslationKey } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { Badge } from '../../shared/ui/Badge';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { BookmarkFilledIcon, GearIcon, PlusIcon, SearchIcon } from '../../shared/ui/icons';
import { useTypingStore } from '../../shared/ws/typingStore';
import styles from './ChatListPage.module.css';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_MIN_LENGTH = 2;

const PREVIEW_KEY_BY_TYPE: Partial<Record<string, TranslationKey>> = {
  photo: 'preview.photo',
  video: 'preview.video',
  voice: 'preview.voice',
  audio: 'preview.audio',
  document: 'preview.document',
  album: 'preview.album',
};

function formatTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString([], { day: '2-digit', month: '2-digit' });
}

function previewText(message: Message, t: (key: TranslationKey) => string): string {
  if (message.deletedForAll) return '';
  if (message.body) return message.body;
  const key = PREVIEW_KEY_BY_TYPE[message.type];
  return key ? t(key) : '';
}

function ChatRow({ chat }: { chat: Chat }) {
  const t = useT();
  const { chatId } = useParams();
  const typing = useTypingStore((s) => s.byChat[chat.chatPublicId]);
  const isActive = chatId === chat.chatPublicId;

  const preview = typing
    ? t('chat.typing')
    : chat.lastMessage
      ? previewText(chat.lastMessage, t)
      : '';

  return (
    <Link
      to={`/chat/${chat.chatPublicId}`}
      className={[styles.row, isActive ? styles.rowActive : ''].join(' ')}
    >
      <Avatar name={chat.title} src={chat.avatarUrl} size={52} online={chat.peerOnline} />
      <div className={styles.rowBody}>
        <div className={styles.rowTop}>
          <span className={styles.rowTitle}>{chat.title}</span>
          {chat.lastMessage ? (
            <span className={styles.rowTime}>{formatTime(chat.lastMessage.createdAt)}</span>
          ) : null}
        </div>
        <div className={styles.rowBottom}>
          <span className={[styles.rowPreview, typing ? styles.rowTyping : ''].join(' ')}>
            {preview}
          </span>
          {chat.mentionsCount > 0 ? <Badge count={chat.mentionsCount} mention /> : null}
          {chat.unreadCount > 0 ? (
            <Badge count={chat.unreadCount} muted={!!chat.mutedUntil} />
          ) : null}
        </div>
      </div>
    </Link>
  );
}

function SavedMessagesRow() {
  const t = useT();
  const navigate = useNavigate();
  const { chatId } = useParams();
  const queryClient = useQueryClient();
  const chatsQuery = useQuery({ queryKey: ['chats'], queryFn: listChats });
  const saved = chatsQuery.data?.find((c) => c.type === 'saved');
  const isActive = !!saved && chatId === saved.chatPublicId;

  const openSavedMutation = useMutation({
    mutationFn: getSavedChat,
    onSuccess: (chat) => {
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
      navigate(`/chat/${chat.chatPublicId}`);
    },
  });

  return (
    <button
      type="button"
      className={[styles.row, isActive ? styles.rowActive : ''].join(' ')}
      onClick={() => {
        if (saved) navigate(`/chat/${saved.chatPublicId}`);
        else openSavedMutation.mutate();
      }}
    >
      <span className={styles.savedIcon}>
        <BookmarkFilledIcon size={22} />
      </span>
      <div className={styles.rowBody}>
        <div className={styles.rowTop}>
          <span className={styles.rowTitle}>{t('chatlist.savedMessages')}</span>
        </div>
      </div>
    </button>
  );
}

function MessageResultRow({ message }: { message: Message }) {
  return (
    <Link to={`/chat/${message.chatPublicId}`} className={styles.row}>
      <div className={styles.rowBody}>
        <div className={styles.rowTop}>
          <span className={styles.rowTitle}>{formatTime(message.createdAt)}</span>
        </div>
        <span className={styles.rowPreview}>{message.body}</span>
      </div>
    </Link>
  );
}

export function ChatListPage() {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useSessionStore((s) => s.user);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [creating, setCreating] = useState(false);
  const [newChatUsername, setNewChatUsername] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const chatsQuery = useQuery({ queryKey: ['chats'], queryFn: listChats });

  const searchQuery = useQuery({
    queryKey: ['search', debouncedSearch],
    queryFn: () => searchApi(debouncedSearch),
    enabled: debouncedSearch.length >= SEARCH_MIN_LENGTH,
  });

  const createChatMutation = useMutation({
    mutationFn: (username: string) => createDirectChat(username),
    onSuccess: (chat) => {
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
      setCreating(false);
      setNewChatUsername('');
      setCreateError(null);
      navigate(`/chat/${chat.chatPublicId}`);
    },
    onError: () => setCreateError('Пользователь не найден'),
  });

  const filteredChats = useMemo(() => {
    const chats = (chatsQuery.data ?? []).filter((c) => c.type !== 'saved');
    const query = search.trim().toLowerCase();
    if (!query) return chats;
    return chats.filter(
      (c) =>
        c.title.toLowerCase().includes(query) ||
        (c.peerUsername ?? '').toLowerCase().includes(query),
    );
  }, [chatsQuery.data, search]);

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <Avatar name={user?.displayName ?? '?'} src={user?.avatarUrl} size={36} />
        <Input
          className={styles.searchInput}
          leadingIcon={<SearchIcon size={18} />}
          placeholder={t('chatlist.search')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <IconButton label={t('chatlist.newChat')} onClick={() => setCreating((v) => !v)}>
          <PlusIcon />
        </IconButton>
        <Link to="/settings">
          <IconButton label={t('nav.settings')}>
            <GearIcon />
          </IconButton>
        </Link>
      </header>

      {creating ? (
        <form
          className={styles.newChatForm}
          onSubmit={(e) => {
            e.preventDefault();
            const username = newChatUsername.trim().replace(/^@/, '');
            if (username) createChatMutation.mutate(username);
          }}
        >
          <Input
            autoFocus
            placeholder={t('chatlist.newChatPlaceholder')}
            value={newChatUsername}
            onChange={(e) => setNewChatUsername(e.target.value)}
          />
          {createError ? <p className={styles.newChatError}>{createError}</p> : null}
        </form>
      ) : null}

      <SavedMessagesRow />

      {filteredChats.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>{t('chatlist.empty.title')}</p>
          <p className={styles.emptyHint}>{t('chatlist.empty.hint')}</p>
        </div>
      ) : (
        <div className={styles.list}>
          {filteredChats.map((chat) => (
            <ChatRow key={chat.chatPublicId} chat={chat} />
          ))}
        </div>
      )}

      {searchQuery.data && searchQuery.data.messages.length > 0 ? (
        <div className={styles.list}>
          <div className={styles.searchSectionTitle}>{t('chatlist.search')}</div>
          {searchQuery.data.messages.map((message) => (
            <MessageResultRow key={message.messagePublicId} message={message} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

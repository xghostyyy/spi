import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import type { Chat } from '../../entities/chat/model';
import { useSessionStore } from '../../entities/user/store';
import { createDirectChat, listChats } from '../../features/chats/api';
import { useT } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { Badge } from '../../shared/ui/Badge';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { GearIcon, PlusIcon, SearchIcon } from '../../shared/ui/icons';
import { useTypingStore } from '../../shared/ws/typingStore';
import styles from './ChatListPage.module.css';

function formatTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString([], { day: '2-digit', month: '2-digit' });
}

function ChatRow({ chat }: { chat: Chat }) {
  const t = useT();
  const { chatId } = useParams();
  const typing = useTypingStore((s) => s.byChat[chat.chatPublicId]);
  const isActive = chatId === chat.chatPublicId;

  const preview = typing
    ? t('chat.typing')
    : ((chat.lastMessage?.deletedForAll ? null : chat.lastMessage?.body) ?? '');

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
          {chat.unreadCount > 0 ? (
            <Badge count={chat.unreadCount} muted={!!chat.mutedUntil} />
          ) : null}
        </div>
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
  const [creating, setCreating] = useState(false);
  const [newChatUsername, setNewChatUsername] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);

  const chatsQuery = useQuery({ queryKey: ['chats'], queryFn: listChats });

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
    const chats = chatsQuery.data ?? [];
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
    </div>
  );
}

import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import type { Chat } from '../entities/chat/model';
import { messageFromDto, type MessageDto } from '../entities/message/dto';
import type { Message } from '../entities/message/model';
import { wsClient, type WsEvent } from '../shared/ws/client';
import { useTypingStore } from '../shared/ws/typingStore';

interface DeletedPayload {
  message_public_id: string;
  scope: 'all';
}

interface TypingPayload {
  chat_id: string;
  kind: 'text' | 'voice';
  active: boolean;
}

interface PresencePayload {
  user_public_id: string;
  online: boolean;
  last_seen_at: string | null;
}

interface PinnedUpdatedPayload {
  chat_public_id: string;
  pinned: MessageDto[];
}

function upsertMessageInList(messages: Message[] | undefined, message: Message): Message[] {
  if (!messages) return [message];
  const idx = messages.findIndex((m) => m.messagePublicId === message.messagePublicId);
  if (idx === -1) return [...messages, message];
  const next = messages.slice();
  next[idx] = message;
  return next;
}

/** Подключает WS-клиент и синхронизирует его события с кэшем TanStack Query. */
export function useRealtimeSync(): void {
  const queryClient = useQueryClient();
  const setTyping = useTypingStore((s) => s.setTyping);

  useEffect(() => {
    wsClient.start();

    const unsubscribe = wsClient.subscribe((event: WsEvent) => {
      switch (event.type) {
        case 'message.new':
        case 'message.edited':
        case 'reaction.updated': {
          const message = messageFromDto(event.payload as MessageDto);
          queryClient.setQueryData<Message[]>(['messages', message.chatPublicId], (prev) =>
            upsertMessageInList(prev, message),
          );
          void queryClient.invalidateQueries({ queryKey: ['chats'] });
          break;
        }
        case 'message.deleted': {
          const payload = event.payload as DeletedPayload;
          queryClient.setQueriesData<Message[]>({ queryKey: ['messages'] }, (prev) =>
            prev?.map((m) =>
              m.messagePublicId === payload.message_public_id
                ? { ...m, deletedForAll: true, body: null }
                : m,
            ),
          );
          break;
        }
        case 'typing': {
          const payload = event.payload as TypingPayload;
          setTyping(payload.chat_id, payload.active ? payload.kind : null);
          break;
        }
        case 'presence': {
          const payload = event.payload as PresencePayload;
          queryClient.setQueriesData<Chat[]>({ queryKey: ['chats'] }, (prev) =>
            prev?.map((c) =>
              c.peerPublicId === payload.user_public_id
                ? { ...c, peerOnline: payload.online, peerLastSeenAt: payload.last_seen_at }
                : c,
            ),
          );
          break;
        }
        case 'read.updated': {
          const payload = event.payload as { chat_id: string };
          void queryClient.invalidateQueries({ queryKey: ['messages', payload.chat_id] });
          break;
        }
        case 'pinned.updated': {
          const payload = event.payload as PinnedUpdatedPayload;
          queryClient.setQueryData<Message[]>(
            ['pinned', payload.chat_public_id],
            payload.pinned.map(messageFromDto),
          );
          break;
        }
        default:
          break;
      }
    });

    return () => {
      unsubscribe();
      wsClient.stop();
    };
  }, [queryClient, setTyping]);
}

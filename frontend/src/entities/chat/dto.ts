import { resolveMediaUrl } from '../../shared/api/client';
import { messageFromDto, type MessageDto } from '../message/dto';
import type { Chat } from './model';

export interface ChatDto {
  chat_public_id: string;
  type: string;
  title: string;
  avatar_url: string | null;
  is_pinned: boolean;
  is_archived: boolean;
  muted_until: string | null;
  unread_count: number;
  last_message: MessageDto | null;
  peer_public_id: string | null;
  peer_username: string | null;
  peer_online: boolean;
  peer_last_seen_at: string | null;
}

export function chatFromDto(dto: ChatDto): Chat {
  return {
    chatPublicId: dto.chat_public_id,
    type: dto.type,
    title: dto.title,
    avatarUrl: resolveMediaUrl(dto.avatar_url),
    isPinned: dto.is_pinned,
    isArchived: dto.is_archived,
    mutedUntil: dto.muted_until,
    unreadCount: dto.unread_count,
    lastMessage: dto.last_message ? messageFromDto(dto.last_message) : null,
    peerPublicId: dto.peer_public_id,
    peerUsername: dto.peer_username,
    peerOnline: dto.peer_online,
    peerLastSeenAt: dto.peer_last_seen_at,
  };
}

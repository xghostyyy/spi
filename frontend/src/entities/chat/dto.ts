import { resolveMediaUrl } from '../../shared/api/client';
import { messageFromDto, type MessageDto } from '../message/dto';
import type { Chat, ChatInvite, ChatMember, InvitePreview } from './model';

export interface ChatDto {
  chat_public_id: string;
  type: string;
  title: string;
  description: string | null;
  avatar_url: string | null;
  is_pinned: boolean;
  is_archived: boolean;
  muted_until: string | null;
  unread_count: number;
  mentions_count: number;
  member_count: number | null;
  my_role: string | null;
  last_message: MessageDto | null;
  peer_public_id: string | null;
  peer_username: string | null;
  peer_online: boolean;
  peer_last_seen_at: string | null;
  is_secret: boolean;
  peer_e2ee_public_key: string | null;
  is_channel: boolean;
}

export function chatFromDto(dto: ChatDto): Chat {
  return {
    chatPublicId: dto.chat_public_id,
    type: dto.type,
    title: dto.title,
    description: dto.description,
    avatarUrl: resolveMediaUrl(dto.avatar_url),
    isPinned: dto.is_pinned,
    isArchived: dto.is_archived,
    mutedUntil: dto.muted_until,
    unreadCount: dto.unread_count,
    mentionsCount: dto.mentions_count,
    memberCount: dto.member_count,
    myRole: dto.my_role,
    lastMessage: dto.last_message ? messageFromDto(dto.last_message) : null,
    peerPublicId: dto.peer_public_id,
    peerUsername: dto.peer_username,
    peerOnline: dto.peer_online,
    peerLastSeenAt: dto.peer_last_seen_at,
    isSecret: dto.is_secret,
    peerE2eePublicKey: dto.peer_e2ee_public_key,
    isChannel: dto.is_channel,
  };
}

export interface ChatMemberDto {
  user_public_id: string;
  username: string | null;
  display_name: string;
  avatar_url: string | null;
  role: string;
  can_delete_messages: boolean;
  can_ban: boolean;
  can_invite: boolean;
  can_pin: boolean;
  can_edit_info: boolean;
  online: boolean;
  last_seen_at: string | null;
}

export function chatMemberFromDto(dto: ChatMemberDto): ChatMember {
  return {
    userPublicId: dto.user_public_id,
    username: dto.username,
    displayName: dto.display_name,
    avatarUrl: resolveMediaUrl(dto.avatar_url),
    role: dto.role as ChatMember['role'],
    canDeleteMessages: dto.can_delete_messages,
    canBan: dto.can_ban,
    canInvite: dto.can_invite,
    canPin: dto.can_pin,
    canEditInfo: dto.can_edit_info,
    online: dto.online,
    lastSeenAt: dto.last_seen_at,
  };
}

export interface ChatInviteDto {
  token: string;
  chat_public_id: string;
  max_uses: number | null;
  used_count: number;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export function chatInviteFromDto(dto: ChatInviteDto): ChatInvite {
  return {
    token: dto.token,
    chatPublicId: dto.chat_public_id,
    maxUses: dto.max_uses,
    usedCount: dto.used_count,
    expiresAt: dto.expires_at,
    revokedAt: dto.revoked_at,
    createdAt: dto.created_at,
  };
}

export interface InvitePreviewDto {
  chat_title: string;
  chat_description: string | null;
  member_count: number;
  avatar_url: string | null;
  valid: boolean;
}

export function invitePreviewFromDto(dto: InvitePreviewDto): InvitePreview {
  return {
    chatTitle: dto.chat_title,
    chatDescription: dto.chat_description,
    memberCount: dto.member_count,
    avatarUrl: resolveMediaUrl(dto.avatar_url),
    valid: dto.valid,
  };
}

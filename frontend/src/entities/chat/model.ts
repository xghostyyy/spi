import type { Message } from '../message/model';

export interface Chat {
  chatPublicId: string;
  type: string;
  title: string;
  description: string | null;
  avatarUrl: string | null;
  isPinned: boolean;
  isArchived: boolean;
  mutedUntil: string | null;
  unreadCount: number;
  mentionsCount: number;
  memberCount: number | null;
  myRole: string | null;
  lastMessage: Message | null;
  peerPublicId: string | null;
  peerUsername: string | null;
  peerOnline: boolean;
  peerLastSeenAt: string | null;
  isSecret: boolean;
  peerE2eePublicKey: string | null;
}

export interface ChatMember {
  userPublicId: string;
  username: string | null;
  displayName: string;
  avatarUrl: string | null;
  role: 'owner' | 'admin' | 'member';
  canDeleteMessages: boolean;
  canBan: boolean;
  canInvite: boolean;
  canPin: boolean;
  canEditInfo: boolean;
  online: boolean;
  lastSeenAt: string | null;
}

export interface ChatInvite {
  token: string;
  chatPublicId: string;
  maxUses: number | null;
  usedCount: number;
  expiresAt: string | null;
  revokedAt: string | null;
  createdAt: string;
}

export interface InvitePreview {
  chatTitle: string;
  chatDescription: string | null;
  memberCount: number;
  avatarUrl: string | null;
  valid: boolean;
}

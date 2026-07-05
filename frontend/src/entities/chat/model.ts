import type { Message } from '../message/model';

export interface Chat {
  chatPublicId: string;
  type: string;
  title: string;
  avatarUrl: string | null;
  isPinned: boolean;
  isArchived: boolean;
  mutedUntil: string | null;
  unreadCount: number;
  lastMessage: Message | null;
  peerPublicId: string | null;
  peerUsername: string | null;
  peerOnline: boolean;
  peerLastSeenAt: string | null;
}

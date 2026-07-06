import {
  chatFromDto,
  chatInviteFromDto,
  chatMemberFromDto,
  invitePreviewFromDto,
  type ChatDto,
  type ChatInviteDto,
  type ChatMemberDto,
  type InvitePreviewDto,
} from '../../entities/chat/dto';
import type { Chat, ChatInvite, ChatMember, InvitePreview } from '../../entities/chat/model';
import { messageFromDto, type MessageDto } from '../../entities/message/dto';
import type { Message } from '../../entities/message/model';
import { apiFetch } from '../../shared/api/client';

export async function createGroup(title: string, memberUsernames: string[]): Promise<Chat> {
  const res = await apiFetch<ChatDto>('/api/v1/chats/group', {
    method: 'POST',
    body: { title, member_usernames: memberUsernames },
  });
  return chatFromDto(res);
}

export async function updateGroupInfo(
  chatPublicId: string,
  patch: { title?: string; description?: string | null },
): Promise<Chat> {
  const res = await apiFetch<ChatDto>(`/api/v1/chats/${chatPublicId}/info`, {
    method: 'PATCH',
    body: patch,
  });
  return chatFromDto(res);
}

export async function listGroupMembers(chatPublicId: string): Promise<ChatMember[]> {
  const res = await apiFetch<ChatMemberDto[]>(`/api/v1/chats/${chatPublicId}/members`);
  return res.map(chatMemberFromDto);
}

export async function addGroupMembers(
  chatPublicId: string,
  usernames: string[],
): Promise<ChatMember[]> {
  const res = await apiFetch<ChatMemberDto[]>(`/api/v1/chats/${chatPublicId}/members`, {
    method: 'POST',
    body: { usernames },
  });
  return res.map(chatMemberFromDto);
}

export async function removeGroupMember(chatPublicId: string, userPublicId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/chats/${chatPublicId}/members/${userPublicId}`, {
    method: 'DELETE',
  });
}

export async function updateGroupMember(
  chatPublicId: string,
  userPublicId: string,
  patch: {
    role?: 'admin' | 'member';
    canDeleteMessages?: boolean;
    canBan?: boolean;
    canInvite?: boolean;
    canPin?: boolean;
    canEditInfo?: boolean;
  },
): Promise<ChatMember> {
  const body: Record<string, unknown> = {};
  if (patch.role !== undefined) body.role = patch.role;
  if (patch.canDeleteMessages !== undefined) body.can_delete_messages = patch.canDeleteMessages;
  if (patch.canBan !== undefined) body.can_ban = patch.canBan;
  if (patch.canInvite !== undefined) body.can_invite = patch.canInvite;
  if (patch.canPin !== undefined) body.can_pin = patch.canPin;
  if (patch.canEditInfo !== undefined) body.can_edit_info = patch.canEditInfo;

  const res = await apiFetch<ChatMemberDto>(
    `/api/v1/chats/${chatPublicId}/members/${userPublicId}`,
    { method: 'PATCH', body },
  );
  return chatMemberFromDto(res);
}

export async function createGroupInvite(
  chatPublicId: string,
  options: { maxUses?: number; expiresInHours?: number } = {},
): Promise<ChatInvite> {
  const res = await apiFetch<ChatInviteDto>(`/api/v1/chats/${chatPublicId}/invites`, {
    method: 'POST',
    body: { max_uses: options.maxUses, expires_in_hours: options.expiresInHours },
  });
  return chatInviteFromDto(res);
}

export async function listGroupInvites(chatPublicId: string): Promise<ChatInvite[]> {
  const res = await apiFetch<ChatInviteDto[]>(`/api/v1/chats/${chatPublicId}/invites`);
  return res.map(chatInviteFromDto);
}

export async function revokeGroupInvite(chatPublicId: string, token: string): Promise<void> {
  await apiFetch<void>(`/api/v1/chats/${chatPublicId}/invites/${token}`, { method: 'DELETE' });
}

export async function previewInvite(token: string): Promise<InvitePreview> {
  const res = await apiFetch<InvitePreviewDto>(`/api/v1/invites/${token}`, { skipAuth: true });
  return invitePreviewFromDto(res);
}

export async function joinInvite(token: string): Promise<Chat> {
  const res = await apiFetch<ChatDto>(`/api/v1/invites/${token}/join`, { method: 'POST' });
  return chatFromDto(res);
}

export function inviteJoinUrl(token: string): string {
  return `${window.location.origin}/join/${token}`;
}

export async function listPinnedMessages(chatPublicId: string): Promise<Message[]> {
  const res = await apiFetch<MessageDto[]>(`/api/v1/chats/${chatPublicId}/pinned`);
  return res.map(messageFromDto);
}

export async function pinMessage(chatPublicId: string, messagePublicId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/chats/${chatPublicId}/messages/${messagePublicId}/pin`, {
    method: 'POST',
  });
}

export async function unpinMessage(chatPublicId: string, messagePublicId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/chats/${chatPublicId}/messages/${messagePublicId}/pin`, {
    method: 'DELETE',
  });
}

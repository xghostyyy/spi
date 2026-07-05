import { chatFromDto, type ChatDto } from '../../entities/chat/dto';
import type { Chat } from '../../entities/chat/model';
import { apiFetch } from '../../shared/api/client';

export async function listChats(): Promise<Chat[]> {
  const res = await apiFetch<ChatDto[]>('/api/v1/chats');
  return res.map(chatFromDto);
}

export async function createDirectChat(username: string): Promise<Chat> {
  const res = await apiFetch<ChatDto>('/api/v1/chats', { method: 'POST', body: { username } });
  return chatFromDto(res);
}

interface UpdateChatMembershipInput {
  isPinned?: boolean;
  isArchived?: boolean;
  muteForever?: boolean;
  mutedUntil?: string | null;
}

export async function updateChatMembership(
  chatPublicId: string,
  patch: UpdateChatMembershipInput,
): Promise<Chat> {
  const body: Record<string, unknown> = {};
  if (patch.isPinned !== undefined) body.is_pinned = patch.isPinned;
  if (patch.isArchived !== undefined) body.is_archived = patch.isArchived;
  if (patch.muteForever !== undefined) body.mute_forever = patch.muteForever;
  if (patch.mutedUntil !== undefined) body.muted_until = patch.mutedUntil;

  const res = await apiFetch<ChatDto>(`/api/v1/chats/${chatPublicId}`, {
    method: 'PATCH',
    body,
  });
  return chatFromDto(res);
}

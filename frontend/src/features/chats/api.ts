import { chatFromDto, type ChatDto } from '../../entities/chat/dto';
import type { Chat } from '../../entities/chat/model';
import { messageFromDto, type MessageDto } from '../../entities/message/dto';
import type { Message } from '../../entities/message/model';
import { apiFetch, apiFetchBlob, triggerBlobDownload } from '../../shared/api/client';

export type MediaTab = 'media' | 'files' | 'voice' | 'links';
export type ExportFormat = 'json' | 'html';

export async function listChats(): Promise<Chat[]> {
  const res = await apiFetch<ChatDto[]>('/api/v1/chats');
  return res.map(chatFromDto);
}

export async function createDirectChat(username: string): Promise<Chat> {
  const res = await apiFetch<ChatDto>('/api/v1/chats', { method: 'POST', body: { username } });
  return chatFromDto(res);
}

/** Открыть/создать личный чат с сотрудником из каталога по его public_id (ADR-025). */
export async function createDirectChatByPublicId(peerPublicId: string): Promise<Chat> {
  const res = await apiFetch<ChatDto>('/api/v1/chats', {
    method: 'POST',
    body: { peer_public_id: peerPublicId },
  });
  return chatFromDto(res);
}

export async function createSecretChat(username: string): Promise<Chat> {
  const res = await apiFetch<ChatDto>('/api/v1/chats/secret', {
    method: 'POST',
    body: { username },
  });
  return chatFromDto(res);
}

export async function getSavedChat(): Promise<Chat> {
  const res = await apiFetch<ChatDto>('/api/v1/chats/saved');
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

export async function getChatMedia(chatPublicId: string, tab: MediaTab): Promise<Message[]> {
  const res = await apiFetch<MessageDto[]>(`/api/v1/chats/${chatPublicId}/media?tab=${tab}`);
  return res.map(messageFromDto);
}

export async function exportChat(chatPublicId: string, format: ExportFormat): Promise<void> {
  const { blob, filename } = await apiFetchBlob(
    `/api/v1/chats/${chatPublicId}/export?format=${format}`,
  );
  triggerBlobDownload(blob, filename ?? `chat-${chatPublicId}.${format}`);
}

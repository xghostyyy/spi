import { messageFromDto, type MessageDto } from '../../entities/message/dto';
import type { Message } from '../../entities/message/model';
import { apiFetch } from '../../shared/api/client';

export async function listMessages(chatPublicId: string, before?: string): Promise<Message[]> {
  const query = before ? `?before=${encodeURIComponent(before)}` : '';
  const res = await apiFetch<MessageDto[]>(`/api/v1/chats/${chatPublicId}/messages${query}`);
  return res.map(messageFromDto);
}

export async function sendMessage(
  chatPublicId: string,
  input: {
    clientMsgId: string;
    body?: string | null;
    replyToPublicId?: string | null;
    filePublicIds?: string[];
  },
): Promise<Message> {
  const res = await apiFetch<MessageDto>(`/api/v1/chats/${chatPublicId}/messages`, {
    method: 'POST',
    body: {
      client_msg_id: input.clientMsgId,
      body: input.body ?? null,
      reply_to_public_id: input.replyToPublicId ?? null,
      file_public_ids: input.filePublicIds ?? [],
    },
  });
  return messageFromDto(res);
}

export async function editMessage(
  chatPublicId: string,
  messagePublicId: string,
  body: string,
): Promise<Message> {
  const res = await apiFetch<MessageDto>(
    `/api/v1/chats/${chatPublicId}/messages/${messagePublicId}`,
    { method: 'PATCH', body: { body } },
  );
  return messageFromDto(res);
}

export async function deleteMessage(
  chatPublicId: string,
  messagePublicId: string,
  scope: 'self' | 'all',
): Promise<void> {
  await apiFetch<void>(`/api/v1/chats/${chatPublicId}/messages/${messagePublicId}?scope=${scope}`, {
    method: 'DELETE',
  });
}

export async function toggleReaction(
  chatPublicId: string,
  messagePublicId: string,
  emoji: string,
): Promise<Message> {
  const res = await apiFetch<MessageDto>(
    `/api/v1/chats/${chatPublicId}/messages/${messagePublicId}/reactions`,
    { method: 'POST', body: { emoji } },
  );
  return messageFromDto(res);
}

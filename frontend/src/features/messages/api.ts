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
    forwardFromMessagePublicId?: string;
    contact?: { name: string; phone: string };
    location?: { lat: number; lng: number };
    poll?: {
      question: string;
      options: string[];
      isAnonymous?: boolean;
      multiChoice?: boolean;
    };
    sticker?: { pack: string; stickerId: string; emoji: string; url: string };
    gif?: { url: string; previewUrl?: string; width?: number; height?: number };
    scheduledAt?: string;
  },
): Promise<Message> {
  const res = await apiFetch<MessageDto>(`/api/v1/chats/${chatPublicId}/messages`, {
    method: 'POST',
    body: {
      client_msg_id: input.clientMsgId,
      body: input.body ?? null,
      reply_to_public_id: input.replyToPublicId ?? null,
      file_public_ids: input.filePublicIds ?? [],
      forward_from_message_public_id: input.forwardFromMessagePublicId ?? null,
      contact: input.contact ?? null,
      location: input.location ?? null,
      poll: input.poll
        ? {
            question: input.poll.question,
            options: input.poll.options,
            is_anonymous: input.poll.isAnonymous ?? true,
            multi_choice: input.poll.multiChoice ?? false,
          }
        : null,
      sticker: input.sticker
        ? {
            pack: input.sticker.pack,
            sticker_id: input.sticker.stickerId,
            emoji: input.sticker.emoji,
            url: input.sticker.url,
          }
        : null,
      gif: input.gif
        ? {
            url: input.gif.url,
            preview_url: input.gif.previewUrl ?? null,
            width: input.gif.width ?? null,
            height: input.gif.height ?? null,
          }
        : null,
      scheduled_at: input.scheduledAt ?? null,
    },
  });
  return messageFromDto(res);
}

export async function listScheduledMessages(chatPublicId: string): Promise<Message[]> {
  const res = await apiFetch<MessageDto[]>(`/api/v1/chats/${chatPublicId}/messages/scheduled`);
  return res.map(messageFromDto);
}

export async function rescheduleMessage(
  chatPublicId: string,
  messagePublicId: string,
  scheduledAt: string,
): Promise<Message> {
  const res = await apiFetch<MessageDto>(
    `/api/v1/chats/${chatPublicId}/messages/scheduled/${messagePublicId}`,
    { method: 'PATCH', body: { scheduled_at: scheduledAt } },
  );
  return messageFromDto(res);
}

export async function cancelScheduledMessage(
  chatPublicId: string,
  messagePublicId: string,
): Promise<void> {
  await apiFetch<void>(`/api/v1/chats/${chatPublicId}/messages/scheduled/${messagePublicId}`, {
    method: 'DELETE',
  });
}

export async function votePoll(
  chatPublicId: string,
  messagePublicId: string,
  optionPositions: number[],
): Promise<Message> {
  const res = await apiFetch<MessageDto>(
    `/api/v1/chats/${chatPublicId}/messages/${messagePublicId}/poll/vote`,
    { method: 'POST', body: { option_positions: optionPositions } },
  );
  return messageFromDto(res);
}

export async function closePoll(chatPublicId: string, messagePublicId: string): Promise<Message> {
  const res = await apiFetch<MessageDto>(
    `/api/v1/chats/${chatPublicId}/messages/${messagePublicId}/poll/close`,
    { method: 'POST' },
  );
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

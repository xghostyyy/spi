import { messageFromDto, type MessageDto } from '../../entities/message/dto';
import type { Message } from '../../entities/message/model';
import { apiFetch } from '../../shared/api/client';

export async function listBookmarks(): Promise<Message[]> {
  const res = await apiFetch<MessageDto[]>('/api/v1/bookmarks');
  return res.map(messageFromDto);
}

export async function toggleBookmark(messagePublicId: string): Promise<boolean> {
  const res = await apiFetch<{ bookmarked: boolean }>(`/api/v1/bookmarks/${messagePublicId}`, {
    method: 'POST',
  });
  return res.bookmarked;
}

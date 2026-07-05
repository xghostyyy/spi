import { chatFromDto, type ChatDto } from '../../entities/chat/dto';
import type { Chat } from '../../entities/chat/model';
import { messageFromDto, type MessageDto } from '../../entities/message/dto';
import type { Message } from '../../entities/message/model';
import { apiFetch } from '../../shared/api/client';

export interface SearchResult {
  chats: Chat[];
  messages: Message[];
}

interface SearchResultDto {
  chats: ChatDto[];
  messages: MessageDto[];
}

export async function search(query: string): Promise<SearchResult> {
  const res = await apiFetch<SearchResultDto>(`/api/v1/search?q=${encodeURIComponent(query)}`);
  return {
    chats: res.chats.map(chatFromDto),
    messages: res.messages.map(messageFromDto),
  };
}

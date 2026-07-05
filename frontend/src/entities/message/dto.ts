import type { Message, MessageStatus, Reaction } from './model';

interface ReactionDto {
  emoji: string;
  count: number;
  reacted_by_me: boolean;
}

export interface MessageDto {
  message_public_id: string;
  chat_public_id: string;
  sender_public_id: string | null;
  type: string;
  body: string | null;
  reply_to_public_id: string | null;
  edited_at: string | null;
  deleted_for_all: boolean;
  created_at: string;
  status: string;
  reactions: ReactionDto[];
}

function reactionFromDto(dto: ReactionDto): Reaction {
  return { emoji: dto.emoji, count: dto.count, reactedByMe: dto.reacted_by_me };
}

export function messageFromDto(dto: MessageDto): Message {
  return {
    messagePublicId: dto.message_public_id,
    chatPublicId: dto.chat_public_id,
    senderPublicId: dto.sender_public_id,
    type: dto.type,
    body: dto.body,
    replyToPublicId: dto.reply_to_public_id,
    editedAt: dto.edited_at,
    deletedForAll: dto.deleted_for_all,
    createdAt: dto.created_at,
    status: dto.status as MessageStatus,
    reactions: dto.reactions.map(reactionFromDto),
  };
}

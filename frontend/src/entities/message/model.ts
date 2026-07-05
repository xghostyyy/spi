export interface Reaction {
  emoji: string;
  count: number;
  reactedByMe: boolean;
}

export type MessageStatus = 'sent' | 'read';

export interface Message {
  messagePublicId: string;
  chatPublicId: string;
  senderPublicId: string | null;
  type: string;
  body: string | null;
  replyToPublicId: string | null;
  editedAt: string | null;
  deletedForAll: boolean;
  createdAt: string;
  status: MessageStatus;
  reactions: Reaction[];
}

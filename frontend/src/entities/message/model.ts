export interface Reaction {
  emoji: string;
  count: number;
  reactedByMe: boolean;
}

export type MessageStatus = 'sent' | 'read';

export type FileKind = 'image' | 'video' | 'audio' | 'voice' | 'document' | 'avatar' | 'sticker';

export interface FileAttachment {
  publicId: string;
  kind: FileKind;
  url: string;
  thumbUrl: string | null;
  mimeType: string;
  sizeBytes: number;
  width: number | null;
  height: number | null;
  durationMs: number | null;
  waveform: number[] | null;
  originalName: string | null;
}

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
  attachments: FileAttachment[];
}

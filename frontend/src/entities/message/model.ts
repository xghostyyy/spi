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

export interface ContactPayload {
  name: string;
  phone: string;
}

export interface LocationPayload {
  lat: number;
  lng: number;
}

/** Поле message.payload передаётся с бэкенда как есть (без camelCase-конвертации),
 * поэтому имена полей здесь совпадают с сырым JSON, а не с остальным кодом. */
export interface StickerPayload {
  pack: string;
  sticker_id: string;
  emoji: string;
  url: string;
}

export interface GifPayload {
  url: string;
  preview_url: string | null;
  width: number | null;
  height: number | null;
}

export interface PollOption {
  position: number;
  text: string;
  votes: number;
  votedByMe: boolean;
}

export interface Poll {
  question: string;
  isAnonymous: boolean;
  multiChoice: boolean;
  closedAt: string | null;
  totalVotes: number;
  options: PollOption[];
}

export interface Message {
  messagePublicId: string;
  chatPublicId: string;
  senderPublicId: string | null;
  type: string;
  body: string | null;
  payload:
    ContactPayload | LocationPayload | StickerPayload | GifPayload | Record<string, unknown> | null;
  poll: Poll | null;
  replyToPublicId: string | null;
  forwardedFromUserPublicId: string | null;
  editedAt: string | null;
  deletedForAll: boolean;
  createdAt: string;
  status: MessageStatus;
  reactions: Reaction[];
  attachments: FileAttachment[];
  bookmarked: boolean;
  scheduledAt: string | null;
}

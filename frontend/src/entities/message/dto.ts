import { resolveMediaUrl } from '../../shared/api/client';
import type { FileAttachment, FileKind, Message, MessageStatus, Poll, Reaction } from './model';

interface ReactionDto {
  emoji: string;
  count: number;
  reacted_by_me: boolean;
}

interface PollOptionDto {
  position: number;
  text: string;
  votes: number;
  voted_by_me: boolean;
}

interface PollDto {
  question: string;
  is_anonymous: boolean;
  multi_choice: boolean;
  closed_at: string | null;
  total_votes: number;
  options: PollOptionDto[];
}

function pollFromDto(dto: PollDto): Poll {
  return {
    question: dto.question,
    isAnonymous: dto.is_anonymous,
    multiChoice: dto.multi_choice,
    closedAt: dto.closed_at,
    totalVotes: dto.total_votes,
    options: dto.options.map((o) => ({
      position: o.position,
      text: o.text,
      votes: o.votes,
      votedByMe: o.voted_by_me,
    })),
  };
}

export interface FileDto {
  public_id: string;
  kind: string;
  url: string;
  thumb_url: string | null;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  waveform: number[] | null;
  original_name: string | null;
}

export interface MessageDto {
  message_public_id: string;
  chat_public_id: string;
  sender_public_id: string | null;
  type: string;
  body: string | null;
  payload: Record<string, unknown> | null;
  poll: PollDto | null;
  reply_to_public_id: string | null;
  forwarded_from_user_public_id: string | null;
  edited_at: string | null;
  deleted_for_all: boolean;
  created_at: string;
  status: string;
  reactions: ReactionDto[];
  attachments: FileDto[];
  bookmarked: boolean;
  scheduled_at: string | null;
}

function reactionFromDto(dto: ReactionDto): Reaction {
  return { emoji: dto.emoji, count: dto.count, reactedByMe: dto.reacted_by_me };
}

export function fileFromDto(dto: FileDto): FileAttachment {
  return {
    publicId: dto.public_id,
    kind: dto.kind as FileKind,
    url: resolveMediaUrl(dto.url)!,
    thumbUrl: resolveMediaUrl(dto.thumb_url),
    mimeType: dto.mime_type,
    sizeBytes: dto.size_bytes,
    width: dto.width,
    height: dto.height,
    durationMs: dto.duration_ms,
    waveform: dto.waveform,
    originalName: dto.original_name,
  };
}

export function messageFromDto(dto: MessageDto): Message {
  return {
    messagePublicId: dto.message_public_id,
    chatPublicId: dto.chat_public_id,
    senderPublicId: dto.sender_public_id,
    type: dto.type,
    body: dto.body,
    payload: dto.payload,
    poll: dto.poll ? pollFromDto(dto.poll) : null,
    replyToPublicId: dto.reply_to_public_id,
    forwardedFromUserPublicId: dto.forwarded_from_user_public_id,
    editedAt: dto.edited_at,
    deletedForAll: dto.deleted_for_all,
    createdAt: dto.created_at,
    status: dto.status as MessageStatus,
    reactions: dto.reactions.map(reactionFromDto),
    attachments: dto.attachments.map(fileFromDto),
    bookmarked: dto.bookmarked,
    scheduledAt: dto.scheduled_at,
  };
}

import { fileFromDto, type FileDto } from '../../entities/message/dto';
import type { FileAttachment, FileKind } from '../../entities/message/model';
import { apiBaseUrl, getAccessToken } from '../../shared/api/client';

export function guessFileKind(file: File): FileKind {
  if (file.type.startsWith('image/')) return 'image';
  if (file.type.startsWith('video/')) return 'video';
  if (file.type.startsWith('audio/')) return 'audio';
  return 'document';
}

interface UploadFileOptions {
  durationMs?: number;
  waveform?: number[];
}

export async function uploadFile(
  file: File | Blob,
  kind: FileKind,
  options: UploadFileOptions = {},
): Promise<FileAttachment> {
  const form = new FormData();
  form.append('file', file, file instanceof File ? file.name : 'blob');
  form.append('kind', kind);
  if (options.durationMs !== undefined)
    form.append('duration_ms', String(Math.round(options.durationMs)));
  if (options.waveform) form.append('waveform', JSON.stringify(options.waveform));

  const token = getAccessToken();
  const res = await fetch(`${apiBaseUrl()}/api/v1/files`, {
    method: 'POST',
    body: form,
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { message?: string }).message ?? 'Не удалось загрузить файл');
  }
  return fileFromDto((await res.json()) as FileDto);
}

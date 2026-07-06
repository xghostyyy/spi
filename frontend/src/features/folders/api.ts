import { folderFromDto, type FolderDto } from '../../entities/folder/dto';
import type { Folder } from '../../entities/folder/model';
import { apiFetch } from '../../shared/api/client';

export async function listFolders(): Promise<Folder[]> {
  const res = await apiFetch<FolderDto[]>('/api/v1/folders');
  return res.map(folderFromDto);
}

export async function createFolder(name: string, chatPublicIds: string[]): Promise<Folder> {
  const res = await apiFetch<FolderDto>('/api/v1/folders', {
    method: 'POST',
    body: { name, chat_public_ids: chatPublicIds },
  });
  return folderFromDto(res);
}

interface UpdateFolderInput {
  name?: string;
  chatPublicIds?: string[];
}

export async function updateFolder(
  folderPublicId: string,
  patch: UpdateFolderInput,
): Promise<Folder> {
  const body: Record<string, unknown> = {};
  if (patch.name !== undefined) body.name = patch.name;
  if (patch.chatPublicIds !== undefined) body.chat_public_ids = patch.chatPublicIds;

  const res = await apiFetch<FolderDto>(`/api/v1/folders/${folderPublicId}`, {
    method: 'PATCH',
    body,
  });
  return folderFromDto(res);
}

export async function deleteFolder(folderPublicId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/folders/${folderPublicId}`, { method: 'DELETE' });
}

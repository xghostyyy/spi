import type { Folder } from './model';

export interface FolderDto {
  folder_public_id: string;
  name: string;
  position: number;
  chat_public_ids: string[];
}

export function folderFromDto(dto: FolderDto): Folder {
  return {
    folderPublicId: dto.folder_public_id,
    name: dto.name,
    position: dto.position,
    chatPublicIds: dto.chat_public_ids,
  };
}

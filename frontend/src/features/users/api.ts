import { apiFetch, resolveMediaUrl } from '../../shared/api/client';

export interface DirectoryUser {
  publicId: string;
  username: string | null;
  displayName: string;
  avatarUrl: string | null;
  online: boolean;
}

interface DirectoryUserDto {
  public_id: string;
  username: string | null;
  display_name: string;
  avatar_url: string | null;
  online: boolean;
}

/** Открытый каталог сотрудников (ADR-025): поиск/просмотр всех пользователей. */
export async function searchDirectory(q: string): Promise<DirectoryUser[]> {
  const res = await apiFetch<DirectoryUserDto[]>(
    `/api/v1/users/directory?q=${encodeURIComponent(q)}`,
  );
  return res.map((d) => ({
    publicId: d.public_id,
    username: d.username,
    displayName: d.display_name,
    avatarUrl: resolveMediaUrl(d.avatar_url),
    online: d.online,
  }));
}

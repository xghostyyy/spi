import { apiFetch, getAccessToken } from '../../shared/api/client';
import { userFromDto, type UserDto } from '../../entities/user/dto';
import type { User } from '../../entities/user/model';

export interface ProfilePatch {
  displayName?: string;
  bio?: string | null;
  username?: string;
  theme?: User['theme'];
  locale?: User['locale'];
  privacyLastSeen?: User['privacyLastSeen'];
  privacyAvatar?: User['privacyAvatar'];
}

export async function updateProfile(patch: ProfilePatch): Promise<User> {
  const body: Record<string, unknown> = {};
  if (patch.displayName !== undefined) body.display_name = patch.displayName;
  if (patch.bio !== undefined) body.bio = patch.bio;
  if (patch.username !== undefined) body.username = patch.username;
  if (patch.theme !== undefined) body.theme = patch.theme;
  if (patch.locale !== undefined) body.locale = patch.locale;
  if (patch.privacyLastSeen !== undefined) body.privacy_last_seen = patch.privacyLastSeen;
  if (patch.privacyAvatar !== undefined) body.privacy_avatar = patch.privacyAvatar;

  const res = await apiFetch<UserDto>('/api/v1/users/me', { method: 'PATCH', body });
  return userFromDto(res);
}

export async function checkUsernameAvailable(username: string): Promise<boolean> {
  const res = await apiFetch<{ available: boolean }>(
    `/api/v1/users/check-username?username=${encodeURIComponent(username)}`,
  );
  return res.available;
}

export async function uploadE2eeKey(publicKey: string): Promise<User> {
  const res = await apiFetch<UserDto>('/api/v1/users/me/e2ee-key', {
    method: 'POST',
    body: { public_key: publicKey },
  });
  return userFromDto(res);
}

const API_BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

export async function uploadAvatar(file: File): Promise<User> {
  const form = new FormData();
  form.append('file', file);
  const token = getAccessToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/users/me/avatar`, {
    method: 'POST',
    body: form,
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!res.ok) {
    throw new Error('Не удалось загрузить аватар');
  }
  return userFromDto((await res.json()) as UserDto);
}

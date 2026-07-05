import { resolveMediaUrl } from '../../shared/api/client';
import type { User } from './model';

/** Форма пользователя, как её отдаёт backend (snake_case). */
export interface UserDto {
  public_id: string;
  email: string;
  username: string | null;
  display_name: string;
  bio: string | null;
  avatar_url: string | null;
  theme: 'system' | 'light' | 'dark';
  locale: 'ru' | 'en';
  privacy_last_seen: 'all' | 'contacts' | 'nobody';
  privacy_avatar: 'all' | 'contacts' | 'nobody';
}

export function userFromDto(dto: UserDto): User {
  return {
    publicId: dto.public_id,
    email: dto.email,
    username: dto.username,
    displayName: dto.display_name,
    bio: dto.bio,
    avatarUrl: resolveMediaUrl(dto.avatar_url),
    theme: dto.theme,
    locale: dto.locale,
    privacyLastSeen: dto.privacy_last_seen,
    privacyAvatar: dto.privacy_avatar,
  };
}

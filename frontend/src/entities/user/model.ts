export interface User {
  publicId: string;
  email: string;
  username: string | null;
  displayName: string;
  bio: string | null;
  avatarUrl: string | null;
  theme: 'system' | 'light' | 'dark';
  locale: 'ru' | 'en';
  privacyLastSeen: 'all' | 'contacts' | 'nobody';
  privacyAvatar: 'all' | 'contacts' | 'nobody';
}

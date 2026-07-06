import { apiFetch } from '../../shared/api/client';
import { userFromDto, type UserDto } from '../../entities/user/dto';
import type { User } from '../../entities/user/model';

interface AuthResponse {
  access_token: string;
  user: UserDto;
}

export async function requestLoginCode(email: string): Promise<void> {
  await apiFetch<void>('/api/v1/auth/request-code', {
    method: 'POST',
    body: { email },
    skipAuth: true,
  });
}

export async function verifyLoginCode(
  email: string,
  code: string,
): Promise<{ user: User; token: string }> {
  const res = await apiFetch<AuthResponse>('/api/v1/auth/verify-code', {
    method: 'POST',
    body: { email, code },
    skipAuth: true,
  });
  return { user: userFromDto(res.user), token: res.access_token };
}

export async function refreshSession(): Promise<{ user: User; token: string }> {
  const res = await apiFetch<AuthResponse>('/api/v1/auth/refresh', {
    method: 'POST',
    skipAuth: true,
  });
  return { user: userFromDto(res.user), token: res.access_token };
}

export async function logout(): Promise<void> {
  await apiFetch<void>('/api/v1/auth/logout', { method: 'POST' });
}

export interface Session {
  id: number;
  deviceLabel: string | null;
  ip: string | null;
  createdAt: string;
  lastUsedAt: string;
  isCurrent: boolean;
}

interface SessionDto {
  id: number;
  device_label: string | null;
  ip: string | null;
  created_at: string;
  last_used_at: string;
  is_current: boolean;
}

export async function listSessions(): Promise<Session[]> {
  const res = await apiFetch<SessionDto[]>('/api/v1/auth/sessions');
  return res.map((s) => ({
    id: s.id,
    deviceLabel: s.device_label,
    ip: s.ip,
    createdAt: s.created_at,
    lastUsedAt: s.last_used_at,
    isCurrent: s.is_current,
  }));
}

export async function revokeSession(sessionId: number): Promise<void> {
  await apiFetch<void>(`/api/v1/auth/sessions/${sessionId}`, { method: 'DELETE' });
}

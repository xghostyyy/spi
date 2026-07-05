import { apiFetch, resolveMediaUrl } from '../../shared/api/client';
import type { Contact } from '../../entities/contact/model';

interface ContactDto {
  contact_public_id: string;
  username: string | null;
  display_name: string;
  avatar_url: string | null;
  alias: string | null;
}

function fromDto(dto: ContactDto): Contact {
  return {
    contactPublicId: dto.contact_public_id,
    username: dto.username,
    displayName: dto.display_name,
    avatarUrl: resolveMediaUrl(dto.avatar_url),
    alias: dto.alias,
  };
}

export async function listContacts(): Promise<Contact[]> {
  const res = await apiFetch<ContactDto[]>('/api/v1/contacts');
  return res.map(fromDto);
}

export async function addContact(username: string): Promise<Contact> {
  const res = await apiFetch<ContactDto>('/api/v1/contacts', {
    method: 'POST',
    body: { username },
  });
  return fromDto(res);
}

export async function removeContact(contactPublicId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/contacts/${contactPublicId}`, { method: 'DELETE' });
}

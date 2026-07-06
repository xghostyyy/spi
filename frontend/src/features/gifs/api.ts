import { apiFetch } from '../../shared/api/client';

export interface GifResult {
  id: string;
  url: string;
  previewUrl: string;
  width: number;
  height: number;
}

interface GifResultDto {
  id: string;
  url: string;
  preview_url: string;
  width: number;
  height: number;
}

export async function gifsEnabled(): Promise<boolean> {
  const res = await apiFetch<{ enabled: boolean }>('/api/v1/gifs/enabled');
  return res.enabled;
}

export async function searchGifs(query: string): Promise<GifResult[]> {
  const res = await apiFetch<GifResultDto[]>(`/api/v1/gifs/search?q=${encodeURIComponent(query)}`);
  return res.map((dto) => ({
    id: dto.id,
    url: dto.url,
    previewUrl: dto.preview_url,
    width: dto.width,
    height: dto.height,
  }));
}

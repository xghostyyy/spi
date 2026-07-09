import { apiFetch } from '../api/client';

export interface WsEvent {
  type: string;
  payload: unknown;
  seq: number;
}

type Listener = (event: WsEvent) => void;

const MAX_BACKOFF_MS = 15_000;
const PING_INTERVAL_MS = 25_000;

/**
 * Адрес WebSocket:
 * - VITE_WS_URL задан непустым (dev или split-origin деплой) → используем его;
 * - VITE_WS_URL === '' (прод-сборка, same-origin за Caddy) → выводим из
 *   window.location: тот же хост, wss на https, ws на http;
 * - VITE_WS_URL не задан вовсе → дефолт для локальной разработки.
 */
function resolveWsBaseUrl(): string {
  const configured = import.meta.env.VITE_WS_URL as string | undefined;
  if (configured === undefined) return 'ws://localhost:8000/ws';
  if (configured) return configured;
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/ws`;
}

class WsClient {
  private socket: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private backoffMs = 1000;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped = true;

  start(): void {
    this.stopped = false;
    void this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.socket?.close();
    this.socket = null;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  send(type: string, payload: unknown): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, payload }));
    }
  }

  private async connect(): Promise<void> {
    if (this.stopped) return;
    try {
      const { ticket } = await apiFetch<{ ticket: string }>('/api/v1/auth/ws-ticket', {
        method: 'POST',
      });
      const socket = new WebSocket(`${resolveWsBaseUrl()}?ticket=${encodeURIComponent(ticket)}`);
      this.socket = socket;

      socket.onopen = () => {
        this.backoffMs = 1000;
        this.pingTimer = setInterval(() => this.send('ping', {}), PING_INTERVAL_MS);
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const parsed = JSON.parse(event.data) as WsEvent;
          for (const listener of this.listeners) listener(parsed);
        } catch {
          // игнорируем некорректный JSON
        }
      };

      socket.onclose = () => {
        if (this.pingTimer) clearInterval(this.pingTimer);
        this.socket = null;
        if (!this.stopped) this.scheduleReconnect();
      };

      socket.onerror = () => socket.close();
    } catch {
      if (!this.stopped) this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    this.reconnectTimer = setTimeout(() => void this.connect(), this.backoffMs);
    this.backoffMs = Math.min(this.backoffMs * 2, MAX_BACKOFF_MS);
  }
}

export const wsClient = new WsClient();

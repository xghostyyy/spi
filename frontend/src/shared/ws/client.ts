import { apiFetch } from '../api/client';

export interface WsEvent {
  type: string;
  payload: unknown;
  seq: number;
}

type Listener = (event: WsEvent) => void;

const WS_BASE_URL = (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws';
const MAX_BACKOFF_MS = 15_000;
const PING_INTERVAL_MS = 25_000;

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
      const socket = new WebSocket(`${WS_BASE_URL}?ticket=${encodeURIComponent(ticket)}`);
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

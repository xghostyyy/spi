/// <reference lib="webworker" />
import { BackgroundSyncPlugin } from 'workbox-background-sync';
import { precacheAndRoute } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, NetworkOnly } from 'workbox-strategies';

declare const self: ServiceWorkerGlobalScope;

precacheAndRoute(self.__WB_MANIFEST);

// Офлайн-просмотр истории: последний успешный ответ на список чатов/сообщений
// остаётся доступен из кэша, пока нет сети.
registerRoute(
  ({ url }) => /\/api\/v1\/chats(\/[^/]+\/messages)?$/.test(url.pathname),
  new NetworkFirst({ cacheName: 'spi-chats-cache', networkTimeoutSeconds: 3 }),
  'GET',
);

// Очередь исходящих сообщений: если POST не смог уйти (нет сети), Workbox
// сохраняет запрос и повторяет его автоматически при восстановлении связи.
const outboxSync = new BackgroundSyncPlugin('spi-outbox', {
  maxRetentionTime: 24 * 60,
});

registerRoute(
  ({ url }) => /\/api\/v1\/chats\/[^/]+\/messages$/.test(url.pathname),
  new NetworkOnly({ plugins: [outboxSync] }),
  'POST',
);

self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return;
  const payload = event.data.json() as {
    title: string;
    body: string;
    chatPublicId?: string;
    icon?: string;
  };
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: payload.icon ?? '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { chatPublicId: payload.chatPublicId },
    }),
  );
});

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();
  const chatPublicId = (event.notification.data as { chatPublicId?: string } | undefined)
    ?.chatPublicId;
  const url = chatPublicId ? `/chat/${chatPublicId}` : '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          void (client as WindowClient).navigate(url);
          return (client as WindowClient).focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});

self.addEventListener('install', () => {
  void self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

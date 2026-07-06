import { apiFetch } from '../../shared/api/client';

export async function getVapidPublicKey(): Promise<string> {
  const res = await apiFetch<{ public_key: string }>('/api/v1/push/vapid-public-key', {
    skipAuth: true,
  });
  return res.public_key;
}

export async function subscribePush(subscription: PushSubscriptionJSON): Promise<void> {
  await apiFetch<void>('/api/v1/push/subscribe', {
    method: 'POST',
    body: {
      endpoint: subscription.endpoint,
      keys: subscription.keys,
    },
  });
}

export async function unsubscribePush(endpoint: string): Promise<void> {
  await apiFetch<void>('/api/v1/push/unsubscribe', {
    method: 'POST',
    body: { endpoint },
  });
}

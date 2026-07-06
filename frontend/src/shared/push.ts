import { getVapidPublicKey, subscribePush, unsubscribePush } from '../features/push/api';

export type PushSupport = 'unsupported' | 'denied' | 'unsubscribed' | 'subscribed';

function isPushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const base64Safe = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64Safe);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export async function getPushStatus(): Promise<PushSupport> {
  if (!isPushSupported()) return 'unsupported';
  if (Notification.permission === 'denied') return 'denied';

  const registration = await navigator.serviceWorker.ready.catch(() => null);
  if (!registration) return 'unsupported';
  const subscription = await registration.pushManager.getSubscription();
  return subscription ? 'subscribed' : 'unsubscribed';
}

export async function enablePush(): Promise<PushSupport> {
  if (!isPushSupported()) return 'unsupported';

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return 'denied';

  const registration = await navigator.serviceWorker.ready;
  const publicKey = await getVapidPublicKey();
  if (!publicKey) return 'unsubscribed';

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });
  await subscribePush(subscription.toJSON() as PushSubscriptionJSON);
  return 'subscribed';
}

export async function disablePush(): Promise<PushSupport> {
  if (!isPushSupported()) return 'unsupported';

  const registration = await navigator.serviceWorker.ready.catch(() => null);
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await unsubscribePush(subscription.endpoint);
    await subscription.unsubscribe();
  }
  return 'unsubscribed';
}

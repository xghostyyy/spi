/** Секретные чаты (Фаза 6, ADR-021): ECDH P-256 (Web Crypto, широко поддерживается
 * в браузерах — в отличие от X25519) + AES-GCM. Упрощённая схема без Double Ratchet:
 * один статический общий ключ на пару собеседников, без ротации/forward secrecy
 * на уровне сообщений. */

import { uploadE2eeKey } from '../../features/settings/api';
import { loadIdentityKeyPair, saveIdentityKeyPair } from './keyStore';

const ECDH_PARAMS = { name: 'ECDH', namedCurve: 'P-256' } as const;

function bufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function base64ToBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

let cachedKeyPair: CryptoKeyPair | null = null;
const sharedKeyCache = new Map<string, CryptoKey>();

/** Генерирует (или загружает из IndexedDB) идентити-ключ и, если на сервере ещё
 * нет публичного ключа этого пользователя, загружает его. */
export async function ensureIdentityKeyPair(
  currentUserE2eePublicKey: string | null,
): Promise<CryptoKeyPair> {
  if (cachedKeyPair) return cachedKeyPair;

  let pair = await loadIdentityKeyPair();
  if (!pair) {
    pair = (await crypto.subtle.generateKey(ECDH_PARAMS, true, ['deriveKey'])) as CryptoKeyPair;
    await saveIdentityKeyPair(pair);
  }
  cachedKeyPair = pair;

  if (!currentUserE2eePublicKey) {
    const exported = await crypto.subtle.exportKey('spki', pair.publicKey);
    await uploadE2eeKey(bufferToBase64(exported));
  }
  return pair;
}

async function importPeerPublicKey(base64: string): Promise<CryptoKey> {
  return crypto.subtle.importKey('spki', base64ToBuffer(base64), ECDH_PARAMS, false, []);
}

async function deriveSharedKey(
  myPrivateKey: CryptoKey,
  peerPublicKey: CryptoKey,
): Promise<CryptoKey> {
  return crypto.subtle.deriveKey(
    { name: 'ECDH', public: peerPublicKey },
    myPrivateKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

/** Общий ключ кэшируется по chatPublicId, чтобы не пересчитывать ECDH на каждый рендер. */
export async function getOrDeriveSharedKey(
  chatPublicId: string,
  myPrivateKey: CryptoKey,
  peerPublicKeyBase64: string,
): Promise<CryptoKey> {
  const cached = sharedKeyCache.get(chatPublicId);
  if (cached) return cached;
  const peerKey = await importPeerPublicKey(peerPublicKeyBase64);
  const shared = await deriveSharedKey(myPrivateKey, peerKey);
  sharedKeyCache.set(chatPublicId, shared);
  return shared;
}

export async function encryptText(
  sharedKey: CryptoKey,
  plaintext: string,
): Promise<{ ciphertext: string; iv: string }> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertextBuf = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, sharedKey, encoded);
  return { ciphertext: bufferToBase64(ciphertextBuf), iv: bufferToBase64(iv.buffer) };
}

/** Возвращает null при ошибке расшифровки (неверный/устаревший ключ) вместо throw —
 * вызывающий код показывает плейсхолдер вместо падения рендера. */
export async function decryptText(
  sharedKey: CryptoKey,
  ciphertext: string,
  iv: string,
): Promise<string | null> {
  try {
    const plainBuf = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: base64ToBuffer(iv) },
      sharedKey,
      base64ToBuffer(ciphertext),
    );
    return new TextDecoder().decode(plainBuf);
  } catch {
    return null;
  }
}

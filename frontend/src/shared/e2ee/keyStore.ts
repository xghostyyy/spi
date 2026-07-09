/** Хранилище идентити-ключа секретных чатов — только IndexedDB, никогда localStorage
 * (см. ADR-021): CryptoKey хранится структурным клоном, не как экспортированные байты. */

const DB_NAME = 'spi-e2ee';
const STORE_NAME = 'keys';
const KEY_ID = 'identity';

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveIdentityKeyPair(pair: CryptoKeyPair): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).put(pair, KEY_ID);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function loadIdentityKeyPair(): Promise<CryptoKeyPair | null> {
  const db = await openDb();
  const pair = await new Promise<CryptoKeyPair | null>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const request = tx.objectStore(STORE_NAME).get(KEY_ID);
    request.onsuccess = () => resolve((request.result as CryptoKeyPair | undefined) ?? null);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return pair;
}

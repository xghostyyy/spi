export interface StickerDef {
  pack: string;
  id: string;
  emoji: string;
  url: string;
}

export interface StickerPack {
  pack: string;
  label: string;
  stickers: StickerDef[];
}

/** Встроенный набор — без внешнего сервиса стикеров/загрузки пользователем (см. ADR-019). */
export const STICKER_PACKS: StickerPack[] = [
  {
    pack: 'cats',
    label: 'Коты',
    stickers: [
      { pack: 'cats', id: 'wave', emoji: '👋', url: '/stickers/cats/wave.svg' },
      { pack: 'cats', id: 'laugh', emoji: '😂', url: '/stickers/cats/laugh.svg' },
      { pack: 'cats', id: 'love', emoji: '😍', url: '/stickers/cats/love.svg' },
      { pack: 'cats', id: 'sleep', emoji: '😴', url: '/stickers/cats/sleep.svg' },
      { pack: 'cats', id: 'wink', emoji: '😉', url: '/stickers/cats/wink.svg' },
      { pack: 'cats', id: 'surprised', emoji: '😮', url: '/stickers/cats/surprised.svg' },
    ],
  },
];

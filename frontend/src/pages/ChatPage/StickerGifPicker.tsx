import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { gifsEnabled, searchGifs, type GifResult } from '../../features/gifs/api';
import { useT } from '../../shared/i18n';
import { STICKER_PACKS, type StickerDef } from '../../shared/stickers/catalog';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { CloseIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_MIN_LENGTH = 2;

interface StickerGifPickerProps {
  onClose: () => void;
  onSelectSticker: (sticker: StickerDef) => void;
  onSelectGif: (gif: GifResult) => void;
}

export function StickerGifPicker({ onClose, onSelectSticker, onSelectGif }: StickerGifPickerProps) {
  const t = useT();
  const [tab, setTab] = useState<'stickers' | 'gifs'>('stickers');
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const enabledQuery = useQuery({ queryKey: ['gifs-enabled'], queryFn: gifsEnabled });
  const gifsQuery = useQuery({
    queryKey: ['gifs-search', debouncedQuery],
    queryFn: () => searchGifs(debouncedQuery),
    enabled: tab === 'gifs' && debouncedQuery.length >= SEARCH_MIN_LENGTH,
  });

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.pickerTabs}>
            <button
              type="button"
              className={[styles.pickerTab, tab === 'stickers' ? styles.pickerTabActive : ''].join(
                ' ',
              )}
              onClick={() => setTab('stickers')}
            >
              {t('sticker.tab')}
            </button>
            {enabledQuery.data ? (
              <button
                type="button"
                className={[styles.pickerTab, tab === 'gifs' ? styles.pickerTabActive : ''].join(
                  ' ',
                )}
                onClick={() => setTab('gifs')}
              >
                {t('gif.tab')}
              </button>
            ) : null}
          </div>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>

        {tab === 'stickers' ? (
          <div className={styles.stickerGrid}>
            {STICKER_PACKS.flatMap((pack) => pack.stickers).map((sticker) => (
              <button
                key={`${sticker.pack}-${sticker.id}`}
                type="button"
                className={styles.stickerGridItem}
                onClick={() => onSelectSticker(sticker)}
              >
                <img src={sticker.url} alt={sticker.emoji} />
              </button>
            ))}
          </div>
        ) : (
          <div className={styles.gifPanel}>
            <Input
              autoFocus
              placeholder={t('gif.searchPlaceholder')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className={styles.gifGrid}>
              {(gifsQuery.data ?? []).map((gif) => (
                <button
                  key={gif.id}
                  type="button"
                  className={styles.gifGridItem}
                  onClick={() => onSelectGif(gif)}
                >
                  <img src={gif.previewUrl} alt="" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

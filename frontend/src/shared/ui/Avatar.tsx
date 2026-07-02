import styles from './Avatar.module.css';

interface AvatarProps {
  /** URL картинки; если нет — инициалы из name */
  src?: string | null;
  name: string;
  size?: number;
  online?: boolean;
}

const PALETTE = ['#e87b2d', '#5b8def', '#4cc35e', '#b06ae8', '#e05d7b', '#3fb6c9'];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p.charAt(0).toUpperCase()).join('');
}

function colorFor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.codePointAt(0)!) | 0;
  return PALETTE[Math.abs(hash) % PALETTE.length]!;
}

export function Avatar({ src, name, size = 48, online }: AvatarProps) {
  return (
    <span className={styles.root} style={{ width: size, height: size }}>
      {src ? (
        <img className={styles.image} src={src} alt="" width={size} height={size} />
      ) : (
        <span
          className={styles.fallback}
          style={{ background: colorFor(name), fontSize: size * 0.38 }}
        >
          {initials(name)}
        </span>
      )}
      {online ? <span className={styles.online} /> : null}
    </span>
  );
}

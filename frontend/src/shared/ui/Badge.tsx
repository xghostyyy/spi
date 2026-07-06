import styles from './Badge.module.css';

interface BadgeProps {
  /** Счётчик непрочитанных; > 99 показывается как 99+ */
  count: number;
  muted?: boolean;
  /** Показывать «@» вместо числа — для счётчика непрочитанных упоминаний */
  mention?: boolean;
}

export function Badge({ count, muted, mention }: BadgeProps) {
  if (count <= 0) return null;
  return (
    <span
      className={[styles.badge, muted ? styles.muted : '', mention ? styles.mention : '']
        .filter(Boolean)
        .join(' ')}
    >
      {mention ? '@' : count > 99 ? '99+' : count}
    </span>
  );
}

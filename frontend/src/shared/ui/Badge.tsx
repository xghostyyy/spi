import styles from './Badge.module.css';

interface BadgeProps {
  /** Счётчик непрочитанных; > 99 показывается как 99+ */
  count: number;
  muted?: boolean;
}

export function Badge({ count, muted }: BadgeProps) {
  if (count <= 0) return null;
  return (
    <span className={[styles.badge, muted ? styles.muted : ''].filter(Boolean).join(' ')}>
      {count > 99 ? '99+' : count}
    </span>
  );
}

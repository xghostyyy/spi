import type { ReactNode } from 'react';

import { CheckIcon, DoubleCheckIcon } from './icons';
import styles from './MessageBubble.module.css';

export type DeliveryStatus = 'sending' | 'sent' | 'read';

interface MessageBubbleProps {
  children: ReactNode;
  /** Своё сообщение (справа, светлый пузырь по макету) или входящее */
  out?: boolean;
  time: string;
  status?: DeliveryStatus;
  edited?: boolean;
}

/** Пузырь сообщения по макетам: скругление 16px, время и галочки в углу. */
export function MessageBubble({ children, out, time, status, edited }: MessageBubbleProps) {
  return (
    <div className={[styles.row, out ? styles.rowOut : styles.rowIn].join(' ')}>
      <div className={[styles.bubble, out ? styles.out : styles.in].join(' ')}>
        <span className={styles.body}>{children}</span>
        <span className={styles.meta}>
          {edited ? <span className={styles.edited}>ред.</span> : null}
          <span className={styles.time}>{time}</span>
          {out && status ? (
            <span className={styles.status}>
              {status === 'read' ? <DoubleCheckIcon size={15} /> : <CheckIcon size={15} />}
            </span>
          ) : null}
        </span>
      </div>
    </div>
  );
}

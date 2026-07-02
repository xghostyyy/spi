import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';

import styles from './Input.module.css';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Иконка слева внутри поля (например, лупа) */
  leadingIcon?: ReactNode;
}

/** Инпут-«pill» по макету (поиск, поле сообщения, формы). */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { leadingIcon, className, ...rest },
  ref,
) {
  return (
    <div className={[styles.wrapper, className].filter(Boolean).join(' ')}>
      {leadingIcon ? <span className={styles.icon}>{leadingIcon}</span> : null}
      <input ref={ref} className={styles.input} {...rest} />
    </div>
  );
});

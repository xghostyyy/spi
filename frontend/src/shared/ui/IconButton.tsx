import type { ButtonHTMLAttributes, ReactNode } from 'react';

import styles from './IconButton.module.css';

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Обязательная aria-подпись — кнопка без текста */
  label: string;
  variant?: 'plain' | 'filled' | 'accent';
  children: ReactNode;
}

export function IconButton({
  label,
  variant = 'plain',
  className,
  children,
  ...rest
}: IconButtonProps) {
  const classes = [styles.iconButton, styles[variant], className].filter(Boolean).join(' ');
  return (
    <button className={classes} aria-label={label} title={label} {...rest}>
      {children}
    </button>
  );
}

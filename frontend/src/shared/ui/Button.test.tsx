import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Avatar } from './Avatar';
import { Badge } from './Badge';
import { Button } from './Button';
import { MessageBubble } from './MessageBubble';

describe('ui-kit', () => {
  it('Button рендерит текст и обрабатывает disabled', () => {
    render(<Button disabled>Войти</Button>);
    const btn = screen.getByRole('button', { name: 'Войти' });
    expect(btn).toBeDisabled();
  });

  it('Avatar показывает инициалы без картинки', () => {
    render(<Avatar name="Дмитрий Цавалюк" />);
    expect(screen.getByText('ДЦ')).toBeInTheDocument();
  });

  it('Badge скрывается при count=0 и показывает 99+', () => {
    const { rerender, container } = render(<Badge count={0} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<Badge count={150} />);
    expect(screen.getByText('99+')).toBeInTheDocument();
  });

  it('MessageBubble показывает время и текст', () => {
    render(
      <MessageBubble out time="12:00" status="read">
        Как тебе новый мессенджер?
      </MessageBubble>,
    );
    expect(screen.getByText('Как тебе новый мессенджер?')).toBeInTheDocument();
    expect(screen.getByText('12:00')).toBeInTheDocument();
  });
});

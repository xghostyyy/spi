import type { Message } from '../../entities/message/model';
import type { Locale } from '../../shared/i18n';
import styles from './ChatPage.module.css';

interface SystemPayload {
  event: string;
  actor?: string;
  target?: string;
  title?: string;
}

interface SystemMessageRowProps {
  message: Message;
  memberNames: Record<string, string>;
  locale: Locale;
}

export function SystemMessageRow({ message, memberNames, locale }: SystemMessageRowProps) {
  const payload = message.payload as SystemPayload | null;
  if (!payload) return null;

  const actor = payload.actor ? (memberNames[payload.actor] ?? '') : '';
  const target = payload.target ? (memberNames[payload.target] ?? '') : '';
  const isRu = locale === 'ru';

  let text = '';
  switch (payload.event) {
    case 'group_created':
      text = isRu
        ? `${actor} создал(а) группу «${payload.title ?? ''}»`
        : `${actor} created the group "${payload.title ?? ''}"`;
      break;
    case 'member_added':
      text = isRu ? `${actor} добавил(а) ${target}` : `${actor} added ${target}`;
      break;
    case 'member_removed':
      text = isRu ? `${actor} удалил(а) ${target}` : `${actor} removed ${target}`;
      break;
    case 'member_left':
      text = isRu ? `${actor} покинул(а) группу` : `${actor} left the group`;
      break;
    case 'role_changed':
      text = isRu
        ? `${actor} изменил(а) права участника ${target}`
        : `${actor} changed ${target}'s permissions`;
      break;
    case 'info_updated':
      text = isRu ? `${actor} изменил(а) информацию о группе` : `${actor} updated the group info`;
      break;
    case 'message_pinned':
      text = isRu ? `${actor} закрепил(а) сообщение` : `${actor} pinned a message`;
      break;
    case 'member_joined_via_invite':
      text = isRu ? `${actor} присоединился(лась) по ссылке` : `${actor} joined via invite link`;
      break;
    default:
      return null;
  }

  return <div className={styles.systemMessage}>{text}</div>;
}

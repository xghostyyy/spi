/** Русский — основной язык интерфейса. Источник истины для ключей. */
export const ru = {
  'app.name': 'SPI Messenger',

  'nav.chats': 'Чаты',
  'nav.settings': 'Настройки',
  'nav.back': 'Назад',

  'chatlist.search': 'Поиск',
  'chatlist.newChat': 'Новый чат',
  'chatlist.empty.title': 'Пока нет чатов',
  'chatlist.empty.hint': 'Найдите собеседника по @username и начните переписку',
  'chatlist.savedMessages': 'Сохраненные сообщения',

  'chat.placeholder': 'Сообщение',
  'chat.selectChat': 'Выберите чат, чтобы начать переписку',
  'chat.today': 'Сегодня',
  'chat.yesterday': 'Вчера',
  'chat.typing': 'Печатает...',
  'chat.recordingVoice': 'Записывает голосовое сообщение..',
  'chat.online': 'В сети',
  'chat.attach': 'Прикрепить файл',
  'chat.voiceMessage': 'Голосовое сообщение',
  'chat.call': 'Позвонить',
  'chat.callsSoon': 'Звонки скоро появятся',

  'auth.title': 'Вход в SPI',
  'auth.emailLabel': 'E-mail',
  'auth.emailPlaceholder': 'you@example.com',
  'auth.sendCode': 'Получить код',
  'auth.codeLabel': 'Код из письма',
  'auth.signIn': 'Войти',

  'settings.title': 'Настройки',
  'settings.profile': 'Профиль',
  'settings.theme': 'Тема',
  'settings.theme.system': 'Системная',
  'settings.theme.light': 'Светлая',
  'settings.theme.dark': 'Тёмная',
  'settings.language': 'Язык',
  'settings.editProfile': 'Изменить профиль',

  'common.save': 'Сохранить',
  'common.cancel': 'Отмена',
  'common.loading': 'Загрузка…',
} as const;

export type TranslationKey = keyof typeof ru;

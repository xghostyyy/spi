import type { TranslationKey } from './ru';

/** Английский — второй язык. Ключи проверяются tsc: Record по ключам ru. */
export const en: Record<TranslationKey, string> = {
  'app.name': 'SPI Messenger',

  'nav.chats': 'Chats',
  'nav.settings': 'Settings',
  'nav.back': 'Back',

  'chatlist.search': 'Search',
  'chatlist.newChat': 'New chat',
  'chatlist.empty.title': 'No chats yet',
  'chatlist.empty.hint': 'Find a person by @username and start chatting',
  'chatlist.savedMessages': 'Saved Messages',

  'chat.placeholder': 'Message',
  'chat.selectChat': 'Select a chat to start messaging',
  'chat.today': 'Today',
  'chat.yesterday': 'Yesterday',
  'chat.typing': 'Typing...',
  'chat.recordingVoice': 'Recording a voice message..',
  'chat.online': 'Online',
  'chat.attach': 'Attach file',
  'chat.voiceMessage': 'Voice message',
  'chat.call': 'Call',
  'chat.callsSoon': 'Calls are coming soon',

  'auth.title': 'Sign in to SPI',
  'auth.emailLabel': 'E-mail',
  'auth.emailPlaceholder': 'you@example.com',
  'auth.sendCode': 'Get code',
  'auth.codeLabel': 'Code from e-mail',
  'auth.signIn': 'Sign in',

  'settings.title': 'Settings',
  'settings.profile': 'Profile',
  'settings.theme': 'Theme',
  'settings.theme.system': 'System',
  'settings.theme.light': 'Light',
  'settings.theme.dark': 'Dark',
  'settings.language': 'Language',
  'settings.editProfile': 'Edit profile',

  'common.save': 'Save',
  'common.cancel': 'Cancel',
  'common.loading': 'Loading…',
};

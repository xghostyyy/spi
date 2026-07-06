import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useLocaleStore, useT, type Locale } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { BackIcon, PencilIcon } from '../../shared/ui/icons';
import { disablePush, enablePush, getPushStatus, type PushSupport } from '../../shared/push';
import { useThemeStore, type ThemePref } from '../../shared/theme';
import { useSessionStore } from '../../entities/user/store';
import { addContact, listContacts, removeContact } from '../../features/contacts/api';
import { logout } from '../../features/auth/api';
import { updateProfile, uploadAvatar } from '../../features/settings/api';
import styles from './SettingsPage.module.css';

export function SettingsPage() {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useSessionStore((s) => s.user);
  const updateUser = useSessionStore((s) => s.updateUser);
  const clearSession = useSessionStore((s) => s.clearSession);
  const themePref = useThemeStore((s) => s.pref);
  const setThemePref = useThemeStore((s) => s.setPref);
  const locale = useLocaleStore((s) => s.locale);
  const setLocale = useLocaleStore((s) => s.setLocale);

  const [displayName, setDisplayName] = useState(user?.displayName ?? '');
  const [username, setUsername] = useState(user?.username ?? '');
  const [bio, setBio] = useState(user?.bio ?? '');
  const [newContact, setNewContact] = useState('');
  const [profileError, setProfileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pushStatus, setPushStatus] = useState<PushSupport | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getPushStatus().then((status) => {
      if (!cancelled) setPushStatus(status);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const contactsQuery = useQuery({ queryKey: ['contacts'], queryFn: listContacts });

  const profileMutation = useMutation({
    mutationFn: () => updateProfile({ displayName, username, bio: bio || null }),
    onSuccess: (updated) => {
      updateUser(updated);
      setProfileError(null);
    },
    onError: (err: unknown) => {
      setProfileError(err instanceof Error ? err.message : t('settings.usernameTaken'));
    },
  });

  const avatarMutation = useMutation({
    mutationFn: (file: File) => uploadAvatar(file),
    onSuccess: (updated) => updateUser(updated),
  });

  const addContactMutation = useMutation({
    mutationFn: () => addContact(newContact.trim().replace(/^@/, '')),
    onSuccess: () => {
      setNewContact('');
      void queryClient.invalidateQueries({ queryKey: ['contacts'] });
    },
  });

  const removeContactMutation = useMutation({
    mutationFn: (contactPublicId: string) => removeContact(contactPublicId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['contacts'] }),
  });

  const pushMutation = useMutation({
    mutationFn: () => (pushStatus === 'subscribed' ? disablePush() : enablePush()),
    onSuccess: setPushStatus,
  });

  async function handleLogout() {
    await logout().catch(() => undefined);
    clearSession();
    navigate('/auth', { replace: true });
  }

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <IconButton label={t('nav.back')} onClick={() => navigate(-1)}>
          <BackIcon />
        </IconButton>
        <h1 className={styles.title}>{t('settings.title')}</h1>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('settings.profile')}</h2>

        <div className={styles.avatarRow}>
          <Avatar name={displayName || '?'} src={user?.avatarUrl} size={72} />
          <Button
            variant="secondary"
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={avatarMutation.isPending}
          >
            <PencilIcon size={16} /> {t('settings.avatarChange')}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) avatarMutation.mutate(file);
            }}
          />
        </div>

        <form
          className={styles.form}
          onSubmit={(e) => {
            e.preventDefault();
            profileMutation.mutate();
          }}
        >
          <label className={styles.label} htmlFor="settings-name">
            {t('settings.displayName')}
          </label>
          <Input
            id="settings-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />

          <label className={styles.label} htmlFor="settings-username">
            {t('settings.username')}
          </label>
          <Input
            id="settings-username"
            value={username}
            onChange={(e) => setUsername(e.target.value.replace(/^@/, ''))}
          />

          <label className={styles.label} htmlFor="settings-bio">
            {t('settings.bio')}
          </label>
          <Input id="settings-bio" value={bio} onChange={(e) => setBio(e.target.value)} />

          <label className={styles.label}>{t('settings.email')}</label>
          <p className={styles.staticValue}>{user?.email}</p>

          {profileError ? <p className={styles.error}>{profileError}</p> : null}

          <Button type="submit" disabled={profileMutation.isPending}>
            {t('common.save')}
          </Button>
        </form>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('settings.theme')}</h2>
        <div className={styles.optionRow}>
          {(['system', 'light', 'dark'] as ThemePref[]).map((pref) => (
            <Button
              key={pref}
              variant={themePref === pref ? 'primary' : 'secondary'}
              type="button"
              onClick={() => setThemePref(pref)}
            >
              {t(`settings.theme.${pref}`)}
            </Button>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('settings.push')}</h2>
        {pushStatus === 'unsupported' ? (
          <p className={styles.staticValue}>{t('settings.push.unsupported')}</p>
        ) : pushStatus === 'denied' ? (
          <p className={styles.staticValue}>{t('settings.push.denied')}</p>
        ) : (
          <Button
            variant={pushStatus === 'subscribed' ? 'secondary' : 'primary'}
            type="button"
            disabled={pushStatus === null || pushMutation.isPending}
            onClick={() => pushMutation.mutate()}
          >
            {pushStatus === 'subscribed' ? t('settings.push.disable') : t('settings.push.enable')}
          </Button>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('settings.language')}</h2>
        <div className={styles.optionRow}>
          {(['ru', 'en'] as Locale[]).map((loc) => (
            <Button
              key={loc}
              variant={locale === loc ? 'primary' : 'secondary'}
              type="button"
              onClick={() => setLocale(loc)}
            >
              {loc.toUpperCase()}
            </Button>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('settings.contacts')}</h2>
        <form
          className={styles.contactForm}
          onSubmit={(e) => {
            e.preventDefault();
            if (newContact.trim()) addContactMutation.mutate();
          }}
        >
          <Input
            placeholder="@username"
            value={newContact}
            onChange={(e) => setNewContact(e.target.value)}
          />
          <Button type="submit" disabled={addContactMutation.isPending}>
            {t('common.add')}
          </Button>
        </form>

        {contactsQuery.data?.length ? (
          <ul className={styles.contactList}>
            {contactsQuery.data.map((c) => (
              <li key={c.contactPublicId} className={styles.contactRow}>
                <Avatar name={c.displayName} src={c.avatarUrl} size={40} />
                <div className={styles.contactInfo}>
                  <span className={styles.contactName}>{c.alias ?? c.displayName}</span>
                  {c.username ? (
                    <span className={styles.contactUsername}>@{c.username}</span>
                  ) : null}
                </div>
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() => removeContactMutation.mutate(c.contactPublicId)}
                >
                  {t('common.remove')}
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.staticValue}>{t('settings.noContacts')}</p>
        )}
      </section>

      <section className={styles.section}>
        <Button variant="danger" type="button" onClick={handleLogout}>
          {t('settings.logout')}
        </Button>
      </section>
    </div>
  );
}

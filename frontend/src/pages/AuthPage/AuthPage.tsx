import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../../shared/api/client';
import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { Input } from '../../shared/ui/Input';
import { useSessionStore } from '../../entities/user/store';
import { requestLoginCode, verifyLoginCode } from '../../features/auth/api';
import { PENDING_INVITE_KEY } from '../JoinInvitePage/JoinInvitePage';
import styles from './AuthPage.module.css';

type Step = 'email' | 'code';

export function AuthPage() {
  const t = useT();
  const navigate = useNavigate();
  const setSession = useSessionStore((s) => s.setSession);

  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSendCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await requestLoginCode(email.trim());
      setStep('code');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить код');
    } finally {
      setPending(false);
    }
  }

  async function handleVerifyCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const { user, token } = await verifyLoginCode(email.trim(), code.trim());
      setSession(user, token);
      const pendingInvite = sessionStorage.getItem(PENDING_INVITE_KEY);
      navigate(pendingInvite ? `/join/${pendingInvite}` : '/', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Неверный код');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.card}>
        <h1 className={styles.title}>{t('auth.title')}</h1>

        {step === 'email' ? (
          <form className={styles.form} onSubmit={handleSendCode}>
            <label className={styles.label} htmlFor="auth-email">
              {t('auth.emailLabel')}
            </label>
            <Input
              id="auth-email"
              type="email"
              required
              autoFocus
              placeholder={t('auth.emailPlaceholder')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {error ? <p className={styles.error}>{error}</p> : null}
            <Button type="submit" size="lg" disabled={pending}>
              {t('auth.sendCode')}
            </Button>
          </form>
        ) : (
          <form className={styles.form} onSubmit={handleVerifyCode}>
            <label className={styles.label} htmlFor="auth-code">
              {t('auth.codeLabel')}
            </label>
            <Input
              id="auth-code"
              type="text"
              inputMode="numeric"
              autoFocus
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            {error ? <p className={styles.error}>{error}</p> : null}
            <Button type="submit" size="lg" disabled={pending}>
              {t('auth.signIn')}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}

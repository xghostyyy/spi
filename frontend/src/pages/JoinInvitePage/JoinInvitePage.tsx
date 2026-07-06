import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../../shared/api/client';
import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { useSessionStore } from '../../entities/user/store';
import type { InvitePreview } from '../../entities/chat/model';
import { joinInvite, previewInvite } from '../../features/groups/api';
import styles from './JoinInvitePage.module.css';

export const PENDING_INVITE_KEY = 'spi.pendingInviteToken';

export function JoinInvitePage() {
  const t = useT();
  const navigate = useNavigate();
  const { token } = useParams<{ token: string }>();
  const status = useSessionStore((s) => s.status);

  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    previewInvite(token)
      .then((p) => {
        if (!cancelled) setPreview(p);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleJoin() {
    if (!token) return;
    if (status !== 'authenticated') {
      sessionStorage.setItem(PENDING_INVITE_KEY, token);
      navigate('/auth');
      return;
    }
    setJoining(true);
    setJoinError(null);
    try {
      const chat = await joinInvite(token);
      sessionStorage.removeItem(PENDING_INVITE_KEY);
      navigate(`/chat/${chat.chatPublicId}`, { replace: true });
    } catch (err) {
      setJoinError(err instanceof ApiError ? err.message : t('group.join.error'));
    } finally {
      setJoining(false);
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.card}>
        <h1 className={styles.title}>{t('group.join.title')}</h1>

        {loadError || (preview && !preview.valid) ? (
          <p className={styles.error}>{t('group.join.invalid')}</p>
        ) : preview ? (
          <>
            <div className={styles.groupInfo}>
              {preview.avatarUrl ? (
                <img className={styles.avatar} src={preview.avatarUrl} alt="" />
              ) : (
                <div className={styles.avatarPlaceholder}>{preview.chatTitle.charAt(0)}</div>
              )}
              <div className={styles.groupName}>{preview.chatTitle}</div>
              {preview.chatDescription ? (
                <div className={styles.groupDescription}>{preview.chatDescription}</div>
              ) : null}
              <div className={styles.memberCount}>
                {preview.memberCount} {t('group.membersCount')}
              </div>
            </div>
            {joinError ? <p className={styles.error}>{joinError}</p> : null}
            <Button size="lg" disabled={joining} onClick={handleJoin}>
              {joining ? t('group.join.joining') : t('group.join.button')}
            </Button>
          </>
        ) : (
          <p role="status">{t('common.loading')}</p>
        )}
      </div>
    </div>
  );
}

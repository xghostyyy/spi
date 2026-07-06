import { useMutation } from '@tanstack/react-query';
import QRCode from 'qrcode';
import { useEffect, useRef, useState } from 'react';

import { createGroupInvite, inviteJoinUrl } from '../../features/groups/api';
import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface InviteModalProps {
  chatPublicId: string;
  onClose: () => void;
}

export function InviteModal({ chatPublicId, onClose }: InviteModalProps) {
  const t = useT();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [copied, setCopied] = useState(false);

  const inviteMutation = useMutation({
    mutationFn: () => createGroupInvite(chatPublicId),
  });

  useEffect(() => {
    inviteMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatPublicId]);

  const link = inviteMutation.data ? inviteJoinUrl(inviteMutation.data.token) : null;

  useEffect(() => {
    if (link && canvasRef.current) {
      void QRCode.toCanvas(canvasRef.current, link, { width: 200, margin: 1 });
    }
  }, [link]);

  async function handleCopy() {
    if (!link) return;
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('group.invite.create')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>
        <div className={styles.inviteBody}>
          {inviteMutation.isPending ? (
            <p role="status">{t('common.loading')}</p>
          ) : inviteMutation.isError ? (
            <p className={styles.inviteError}>{t('group.join.error')}</p>
          ) : (
            <>
              <canvas ref={canvasRef} className={styles.inviteQr} />
              <div className={styles.inviteLinkRow}>
                <code className={styles.inviteLink}>{link}</code>
              </div>
              <Button size="md" onClick={() => void handleCopy()}>
                {copied ? t('group.invite.copied') : t('group.invite.copy')}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

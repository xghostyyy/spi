import { useEffect, useRef } from 'react';

import { useVideoRecorder, type VideoRecording } from '../../features/messages/useVideoRecorder';
import { useT } from '../../shared/i18n';
import { IconButton } from '../../shared/ui/IconButton';
import { CloseIcon, SendIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface VideoNoteRecorderProps {
  onSend: (recording: VideoRecording) => void;
  onCancel: () => void;
}

/** Полноэкранный оверлей записи видеокружка с живым превью (см. ADR-026). */
export function VideoNoteRecorder({ onSend, onCancel }: VideoNoteRecorderProps) {
  const t = useT();
  const recorder = useVideoRecorder();
  const videoRef = useRef<HTMLVideoElement>(null);
  // onCancel в ref, чтобы эффект старта запустился строго один раз.
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stream = await recorder.start();
        if (cancelled) return;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
      } catch {
        if (!cancelled) onCancelRef.current();
      }
    })();
    return () => {
      cancelled = true;
      recorder.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleStop() {
    const recording = await recorder.stop();
    if (recording) onSend(recording);
  }

  return (
    <div className={styles.videoNoteRecorder}>
      <video ref={videoRef} className={styles.videoNotePreview} muted playsInline />
      <p className={styles.videoNoteHint}>{t('videoNote.hint')}</p>
      <div className={styles.videoNoteControls}>
        <IconButton label={t('common.cancel')} onClick={onCancel}>
          <CloseIcon />
        </IconButton>
        <IconButton
          label={t('videoNote.record')}
          variant="accent"
          onClick={() => void handleStop()}
        >
          <SendIcon />
        </IconButton>
      </div>
    </div>
  );
}

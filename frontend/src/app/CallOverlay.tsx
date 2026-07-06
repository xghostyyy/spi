import { useEffect, useRef, useState } from 'react';

import { callManager } from '../shared/calls/CallManager';
import { useCallStore } from '../shared/calls/callStore';
import { useT } from '../shared/i18n';
import { Avatar } from '../shared/ui/Avatar';
import { IconButton } from '../shared/ui/IconButton';
import { MicIcon, MicOffIcon, PhoneIcon, VideoIcon } from '../shared/ui/icons';
import styles from './CallOverlay.module.css';

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function useElapsedSeconds(connectedAt: number | null): number {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!connectedAt) {
      setElapsed(0);
      return;
    }
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - connectedAt) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [connectedAt]);
  return elapsed;
}

function LocalVideo({ stream }: { stream: MediaStream | null }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = stream;
  }, [stream]);
  return <video ref={ref} className={styles.localVideo} autoPlay playsInline muted />;
}

function RemoteVideo({ stream }: { stream: MediaStream | null }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = stream;
  }, [stream]);
  return <video ref={ref} className={styles.remoteVideo} autoPlay playsInline />;
}

function RemoteAudio({ stream }: { stream: MediaStream | null }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = stream;
  }, [stream]);
  return <audio ref={ref} autoPlay />;
}

export function CallOverlay() {
  const t = useT();
  const call = useCallStore();

  if (call.phase === 'idle') return null;

  const isVideo = call.kind === 'video';

  if (call.phase === 'incoming') {
    return (
      <div className={styles.overlay}>
        <div className={styles.card}>
          <Avatar name={call.peerDisplayName ?? '?'} src={call.peerAvatarUrl} size={88} />
          <div className={styles.peerName}>{call.peerDisplayName}</div>
          <div className={styles.status}>
            {isVideo ? t('call.incomingVideo') : t('call.incomingAudio')}
          </div>
          <div className={styles.actions}>
            <IconButton
              label={t('call.decline')}
              className={styles.declineButton}
              onClick={() => callManager.declineIncoming()}
            >
              <PhoneIcon />
            </IconButton>
            <IconButton
              label={t('call.accept')}
              className={styles.acceptButton}
              onClick={() => void callManager.acceptIncoming()}
            >
              <PhoneIcon />
            </IconButton>
          </div>
        </div>
      </div>
    );
  }

  if (call.phase === 'outgoing') {
    return (
      <div className={styles.overlay}>
        <div className={styles.card}>
          <Avatar name={call.peerDisplayName ?? '?'} src={call.peerAvatarUrl} size={88} />
          <div className={styles.peerName}>{call.peerDisplayName}</div>
          <div className={styles.status}>{t('call.outgoing')}</div>
          <div className={styles.actions}>
            <IconButton
              label={t('call.cancel')}
              className={styles.declineButton}
              onClick={() => callManager.hangup()}
            >
              <PhoneIcon />
            </IconButton>
          </div>
        </div>
      </div>
    );
  }

  return <ConnectedCallView isVideo={isVideo} />;
}

function ConnectedCallView({ isVideo }: { isVideo: boolean }) {
  const t = useT();
  const call = useCallStore();
  const elapsed = useElapsedSeconds(call.connectedAt);

  return (
    <div className={styles.overlay}>
      <div className={styles.connectedCard}>
        {isVideo ? (
          <div className={styles.videoStage}>
            <RemoteVideo stream={call.remoteStream} />
            <LocalVideo stream={call.localStream} />
          </div>
        ) : (
          <>
            <RemoteAudio stream={call.remoteStream} />
            <Avatar name={call.peerDisplayName ?? '?'} src={call.peerAvatarUrl} size={96} />
          </>
        )}
        <div className={styles.peerName}>{call.peerDisplayName}</div>
        <div className={styles.status}>{formatDuration(elapsed)}</div>
        <div className={styles.actions}>
          <IconButton
            label={call.muted ? t('call.unmute') : t('call.mute')}
            variant={call.muted ? 'accent' : 'plain'}
            onClick={() => callManager.toggleMute()}
          >
            {call.muted ? <MicOffIcon /> : <MicIcon />}
          </IconButton>
          {isVideo ? (
            <IconButton
              label={call.videoOff ? t('call.videoOn') : t('call.videoOff')}
              variant={call.videoOff ? 'accent' : 'plain'}
              onClick={() => callManager.toggleVideo()}
            >
              <VideoIcon />
            </IconButton>
          ) : null}
          <IconButton
            label={t('call.hangup')}
            className={styles.declineButton}
            onClick={() => callManager.hangup()}
          >
            <PhoneIcon />
          </IconButton>
        </div>
      </div>
    </div>
  );
}

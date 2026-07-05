import { useEffect, useRef, useState } from 'react';

import type { FileAttachment } from '../../entities/message/model';
import { IconButton } from '../../shared/ui/IconButton';
import { PauseIcon, PlayIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

const SPEEDS = [1, 1.5, 2] as const;

function formatDuration(ms: number): string {
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

export function VoicePlayer({ file }: { file: FileAttachment }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [speedIndex, setSpeedIndex] = useState(0);
  const waveform =
    file.waveform && file.waveform.length > 0 ? file.waveform : new Array(30).fill(0.3);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTimeUpdate = () => {
      if (audio.duration) setProgress(audio.currentTime / audio.duration);
    };
    const onEnded = () => {
      setPlaying(false);
      setProgress(0);
    };
    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('ended', onEnded);
    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('ended', onEnded);
    };
  }, []);

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
    } else {
      void audio.play();
    }
    setPlaying(!playing);
  }

  function cycleSpeed() {
    const nextIndex = (speedIndex + 1) % SPEEDS.length;
    setSpeedIndex(nextIndex);
    if (audioRef.current) audioRef.current.playbackRate = SPEEDS[nextIndex] ?? 1;
  }

  return (
    <div className={styles.voicePlayer}>
      <audio ref={audioRef} src={file.url} preload="metadata" />
      <IconButton label={playing ? 'Пауза' : 'Играть'} onClick={togglePlay} variant="accent">
        {playing ? <PauseIcon size={16} /> : <PlayIcon size={16} />}
      </IconButton>
      <div className={styles.waveform}>
        {waveform.map((v, i) => (
          <span
            key={i}
            className={styles.waveformBar}
            style={{
              height: `${Math.max(15, v * 100)}%`,
              opacity: i / waveform.length < progress ? 1 : 0.4,
            }}
          />
        ))}
      </div>
      <button type="button" className={styles.speedButton} onClick={cycleSpeed}>
        {SPEEDS[speedIndex] ?? 1}x
      </button>
      {file.durationMs ? (
        <span className={styles.voiceDuration}>{formatDuration(file.durationMs)}</span>
      ) : null}
    </div>
  );
}

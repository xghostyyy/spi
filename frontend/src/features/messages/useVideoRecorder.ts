import { useRef, useState } from 'react';

export interface VideoRecording {
  blob: Blob;
  durationMs: number;
}

/**
 * Запись видеокружка: MediaRecorder поверх getUserMedia({video,audio}).
 * `start` возвращает MediaStream для живого превью (см. ADR-026, зеркало
 * useVoiceRecorder). Кружок — квадратное видео, круглая форма задаётся в CSS.
 */
export function useVideoRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const startedAtRef = useRef(0);
  const mimeRef = useRef('video/webm');

  function cleanup() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    setIsRecording(false);
  }

  async function start(): Promise<MediaStream> {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 480 }, height: { ideal: 480 } },
      audio: true,
    });
    streamRef.current = stream;

    const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
      ? 'video/webm;codecs=vp8,opus'
      : 'video/webm';
    mimeRef.current = mime;
    const recorder = new MediaRecorder(stream, { mimeType: mime });
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorderRef.current = recorder;
    startedAtRef.current = Date.now();
    recorder.start();
    setIsRecording(true);
    return stream;
  }

  function stop(): Promise<VideoRecording | null> {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder) {
        resolve(null);
        return;
      }
      recorder.onstop = () => {
        const durationMs = Date.now() - startedAtRef.current;
        const blob = new Blob(chunksRef.current, { type: 'video/webm' });
        cleanup();
        resolve({ blob, durationMs });
      };
      recorder.stop();
    });
  }

  function cancel(): void {
    try {
      recorderRef.current?.stop();
    } catch {
      // recorder мог быть неактивен — не важно
    }
    cleanup();
  }

  return { isRecording, start, stop, cancel };
}

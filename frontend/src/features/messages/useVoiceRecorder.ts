import { useRef, useState } from 'react';

export interface VoiceRecording {
  blob: Blob;
  durationMs: number;
  waveform: number[];
}

function downsampleWaveform(samples: number[], targetLength: number): number[] {
  if (samples.length === 0) return new Array(targetLength).fill(0);
  if (samples.length <= targetLength) return samples;
  const factor = samples.length / targetLength;
  const result: number[] = [];
  for (let i = 0; i < targetLength; i++) {
    const start = Math.floor(i * factor);
    const end = Math.max(Math.floor((i + 1) * factor), start + 1);
    const slice = samples.slice(start, end);
    result.push(slice.reduce((a, b) => a + b, 0) / slice.length);
  }
  return result;
}

/** Запись голосового: MediaRecorder + волновая форма через AnalyserNode в реальном времени. */
export function useVoiceRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const waveformRef = useRef<number[]>([]);
  const startedAtRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  function cleanup() {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void audioContextRef.current?.close();
    audioContextRef.current = null;
    setIsRecording(false);
  }

  async function start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;

    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    waveformRef.current = [];

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const sample = () => {
      analyser.getByteTimeDomainData(dataArray);
      let sumSquares = 0;
      for (const value of dataArray) {
        const normalized = (value - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / dataArray.length);
      waveformRef.current.push(Math.min(1, rms * 4));
      rafRef.current = requestAnimationFrame(sample);
    };
    sample();

    const recorder = new MediaRecorder(stream);
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorderRef.current = recorder;
    startedAtRef.current = Date.now();
    recorder.start();
    setIsRecording(true);
  }

  function stop(): Promise<VoiceRecording | null> {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder) {
        resolve(null);
        return;
      }
      recorder.onstop = () => {
        const durationMs = Date.now() - startedAtRef.current;
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const waveform = downsampleWaveform(waveformRef.current, 40);
        cleanup();
        resolve({ blob, durationMs, waveform });
      };
      recorder.stop();
    });
  }

  function cancel(): void {
    recorderRef.current?.stop();
    cleanup();
  }

  return { isRecording, start, stop, cancel };
}

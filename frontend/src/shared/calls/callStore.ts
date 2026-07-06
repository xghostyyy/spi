import { create } from 'zustand';

export type CallPhase = 'idle' | 'outgoing' | 'incoming' | 'connected';
export type CallKind = 'audio' | 'video';

export interface CallStoreState {
  phase: CallPhase;
  chatPublicId: string | null;
  callId: string | null;
  peerPublicId: string | null;
  peerDisplayName: string | null;
  peerAvatarUrl: string | null;
  kind: CallKind | null;
  localStream: MediaStream | null;
  remoteStream: MediaStream | null;
  muted: boolean;
  videoOff: boolean;
  connectedAt: number | null;
  errorKey: string | null;
}

const initialState: CallStoreState = {
  phase: 'idle',
  chatPublicId: null,
  callId: null,
  peerPublicId: null,
  peerDisplayName: null,
  peerAvatarUrl: null,
  kind: null,
  localStream: null,
  remoteStream: null,
  muted: false,
  videoOff: false,
  connectedAt: null,
  errorKey: null,
};

export const useCallStore = create<CallStoreState>()(() => ({ ...initialState }));

export function setCallState(patch: Partial<CallStoreState>): void {
  useCallStore.setState(patch);
}

export function resetCallState(): void {
  useCallStore.setState(initialState);
}

import { useSessionStore } from '../../entities/user/store';
import { sendMessage } from '../../features/messages/api';
import { wsClient, type WsEvent } from '../ws/client';
import { resetCallState, setCallState, useCallStore, type CallKind } from './callStore';

/** Только STUN (без TURN) — звонок не соединится через ограничительный
 * симметричный NAT/файрвол на одной из сторон. См. ADR-020. */
const ICE_SERVERS: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }];
const RING_TIMEOUT_MS = 45_000;

interface CallInvitePayload {
  chat_id: string;
  call_id: string;
  kind: CallKind;
  sdp: RTCSessionDescriptionInit;
  from_public_id: string;
  caller_display_name?: string;
  caller_avatar_url?: string | null;
}

interface CallAnswerPayload {
  chat_id: string;
  call_id: string;
  sdp: RTCSessionDescriptionInit;
}

interface CallIceCandidatePayload {
  chat_id: string;
  call_id: string;
  candidate: RTCIceCandidateInit;
}

interface CallDeclinePayload {
  chat_id: string;
  call_id: string;
  reason: 'declined' | 'busy';
}

interface CallHangupPayload {
  chat_id: string;
  call_id: string;
}

class CallManager {
  private pc: RTCPeerConnection | null = null;
  private pendingCandidates: RTCIceCandidateInit[] = [];
  private ringTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingOffer: CallInvitePayload | null = null;

  constructor() {
    wsClient.subscribe((event) => this.handleEvent(event));
  }

  private handleEvent(event: WsEvent): void {
    switch (event.type) {
      case 'call.invite':
        this.onInvite(event.payload as CallInvitePayload);
        break;
      case 'call.answer':
        void this.onAnswer(event.payload as CallAnswerPayload);
        break;
      case 'call.ice-candidate':
        void this.onRemoteIceCandidate(event.payload as CallIceCandidatePayload);
        break;
      case 'call.decline':
        this.onDeclined(event.payload as CallDeclinePayload);
        break;
      case 'call.hangup':
        this.onRemoteHangup(event.payload as CallHangupPayload);
        break;
      default:
        break;
    }
  }

  private onInvite(payload: CallInvitePayload): void {
    if (useCallStore.getState().phase !== 'idle') {
      wsClient.send('call.decline', {
        chat_id: payload.chat_id,
        call_id: payload.call_id,
        reason: 'busy',
      });
      return;
    }

    this.pendingOffer = payload;
    setCallState({
      phase: 'incoming',
      chatPublicId: payload.chat_id,
      callId: payload.call_id,
      peerPublicId: payload.from_public_id,
      peerDisplayName: payload.caller_display_name ?? payload.from_public_id,
      peerAvatarUrl: payload.caller_avatar_url ?? null,
      kind: payload.kind,
    });
  }

  private async onAnswer(payload: CallAnswerPayload): Promise<void> {
    const state = useCallStore.getState();
    if (state.callId !== payload.call_id || !this.pc) return;
    await this.pc.setRemoteDescription(payload.sdp);
    await this.flushPendingCandidates();
    this.clearRingTimer();
    setCallState({ phase: 'connected', connectedAt: Date.now() });
  }

  private async onRemoteIceCandidate(payload: CallIceCandidatePayload): Promise<void> {
    const state = useCallStore.getState();
    if (state.callId !== payload.call_id) return;
    if (!this.pc?.remoteDescription) {
      this.pendingCandidates.push(payload.candidate);
      return;
    }
    await this.pc.addIceCandidate(payload.candidate);
  }

  private onDeclined(payload: CallDeclinePayload): void {
    const state = useCallStore.getState();
    if (state.callId !== payload.call_id) return;
    void this.logCall('declined');
    this.cleanup();
  }

  private onRemoteHangup(payload: CallHangupPayload): void {
    const state = useCallStore.getState();
    if (state.callId !== payload.call_id) return;
    if (state.phase === 'connected') {
      void this.logCall('answered');
    }
    this.cleanup();
  }

  private async flushPendingCandidates(): Promise<void> {
    if (!this.pc) return;
    const queued = this.pendingCandidates;
    this.pendingCandidates = [];
    for (const candidate of queued) {
      await this.pc.addIceCandidate(candidate);
    }
  }

  private clearRingTimer(): void {
    if (this.ringTimer) {
      clearTimeout(this.ringTimer);
      this.ringTimer = null;
    }
  }

  private createPeerConnection(chatPublicId: string, callId: string): RTCPeerConnection {
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    pc.onicecandidate = (e) => {
      if (e.candidate) {
        wsClient.send('call.ice-candidate', {
          chat_id: chatPublicId,
          call_id: callId,
          candidate: e.candidate.toJSON(),
        });
      }
    };
    pc.ontrack = (e) => {
      setCallState({ remoteStream: e.streams[0] ?? null });
    };
    return pc;
  }

  private async logCall(outcome: 'answered' | 'missed' | 'declined' | 'canceled'): Promise<void> {
    const state = useCallStore.getState();
    if (!state.chatPublicId || !state.kind) return;
    const durationSeconds =
      outcome === 'answered' && state.connectedAt
        ? Math.round((Date.now() - state.connectedAt) / 1000)
        : undefined;
    try {
      await sendMessage(state.chatPublicId, {
        clientMsgId: crypto.randomUUID(),
        call: { kind: state.kind, outcome, durationSeconds },
      });
    } catch {
      // лог звонка — best-effort, не должен мешать завершению звонка
    }
  }

  private cleanup(): void {
    this.clearRingTimer();
    this.pendingCandidates = [];
    this.pendingOffer = null;
    this.pc?.close();
    this.pc = null;
    const state = useCallStore.getState();
    state.localStream?.getTracks().forEach((track) => track.stop());
    resetCallState();
  }

  async startCall(
    chatPublicId: string,
    peerPublicId: string,
    peerDisplayName: string,
    kind: CallKind,
  ): Promise<void> {
    if (useCallStore.getState().phase !== 'idle') return;
    const callId = crypto.randomUUID();
    const me = useSessionStore.getState().user;

    setCallState({
      phase: 'outgoing',
      chatPublicId,
      callId,
      peerPublicId,
      peerDisplayName,
      peerAvatarUrl: null,
      kind,
      errorKey: null,
    });

    let localStream: MediaStream;
    try {
      localStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: kind === 'video',
      });
    } catch {
      resetCallState();
      setCallState({ errorKey: 'call.error.mediaDenied' });
      return;
    }
    setCallState({ localStream });

    const pc = this.createPeerConnection(chatPublicId, callId);
    this.pc = pc;
    for (const track of localStream.getTracks()) pc.addTrack(track, localStream);

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    wsClient.send('call.invite', {
      chat_id: chatPublicId,
      call_id: callId,
      kind,
      sdp: offer,
      caller_display_name: me?.displayName,
      caller_avatar_url: me?.avatarUrl,
    });

    this.ringTimer = setTimeout(() => {
      wsClient.send('call.hangup', { chat_id: chatPublicId, call_id: callId });
      void this.logCall('missed');
      this.cleanup();
    }, RING_TIMEOUT_MS);
  }

  async acceptIncoming(): Promise<void> {
    const offer = this.pendingOffer;
    const state = useCallStore.getState();
    if (!offer || state.phase !== 'incoming') return;

    let localStream: MediaStream;
    try {
      localStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: offer.kind === 'video',
      });
    } catch {
      this.declineIncoming();
      return;
    }
    setCallState({ localStream });

    const pc = this.createPeerConnection(offer.chat_id, offer.call_id);
    this.pc = pc;
    for (const track of localStream.getTracks()) pc.addTrack(track, localStream);

    await pc.setRemoteDescription(offer.sdp);
    await this.flushPendingCandidates();
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    wsClient.send('call.answer', {
      chat_id: offer.chat_id,
      call_id: offer.call_id,
      sdp: answer,
    });

    this.pendingOffer = null;
    setCallState({ phase: 'connected', connectedAt: Date.now() });
  }

  declineIncoming(): void {
    const offer = this.pendingOffer;
    if (!offer) return;
    wsClient.send('call.decline', {
      chat_id: offer.chat_id,
      call_id: offer.call_id,
      reason: 'declined',
    });
    this.cleanup();
  }

  hangup(): void {
    const state = useCallStore.getState();
    if (!state.chatPublicId || !state.callId) return;
    wsClient.send('call.hangup', { chat_id: state.chatPublicId, call_id: state.callId });
    if (state.phase === 'connected') {
      void this.logCall('answered');
    } else if (state.phase === 'outgoing') {
      void this.logCall('canceled');
    }
    this.cleanup();
  }

  toggleMute(): void {
    const state = useCallStore.getState();
    if (!state.localStream) return;
    const nextMuted = !state.muted;
    for (const track of state.localStream.getAudioTracks()) track.enabled = !nextMuted;
    setCallState({ muted: nextMuted });
  }

  toggleVideo(): void {
    const state = useCallStore.getState();
    if (!state.localStream) return;
    const nextOff = !state.videoOff;
    for (const track of state.localStream.getVideoTracks()) track.enabled = !nextOff;
    setCallState({ videoOff: nextOff });
  }
}

export const callManager = new CallManager();

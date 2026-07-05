import { create } from 'zustand';

interface TypingState {
  /** chatPublicId -> "text" | "voice" | null (кто печатает прямо сейчас, для 1-на-1) */
  byChat: Record<string, 'text' | 'voice' | null>;
  setTyping: (chatPublicId: string, kind: 'text' | 'voice' | null) => void;
}

export const useTypingStore = create<TypingState>()((set) => ({
  byChat: {},
  setTyping: (chatPublicId, kind) =>
    set((s) => ({ byChat: { ...s.byChat, [chatPublicId]: kind } })),
}));

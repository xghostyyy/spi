import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Chat } from '../../entities/chat/model';
import type { Folder } from '../../entities/folder/model';
import { listChats } from '../../features/chats/api';
import { createFolder, deleteFolder, updateFolder } from '../../features/folders/api';
import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { CloseIcon, PencilIcon, TrashIcon } from '../../shared/ui/icons';
import styles from './ChatListPage.module.css';

interface FoldersModalProps {
  folders: Folder[];
  onClose: () => void;
}

interface FolderFormProps {
  chats: Chat[];
  initial?: Folder;
  onCancel: () => void;
  onSubmit: (name: string, chatPublicIds: string[]) => void;
}

function FolderForm({ chats, initial, onCancel, onSubmit }: FolderFormProps) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? '');
  const [selected, setSelected] = useState<Set<string>>(new Set(initial?.chatPublicIds ?? []));

  function toggle(chatPublicId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(chatPublicId)) next.delete(chatPublicId);
      else next.add(chatPublicId);
      return next;
    });
  }

  return (
    <form
      className={styles.folderForm}
      onSubmit={(e) => {
        e.preventDefault();
        const trimmed = name.trim();
        if (trimmed) onSubmit(trimmed, Array.from(selected));
      }}
    >
      <Input
        autoFocus
        placeholder={t('folders.namePlaceholder')}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <div className={styles.folderChatList}>
        {chats.map((chat) => (
          <label key={chat.chatPublicId} className={styles.folderChatRow}>
            <input
              type="checkbox"
              checked={selected.has(chat.chatPublicId)}
              onChange={() => toggle(chat.chatPublicId)}
            />
            <span>{chat.title}</span>
          </label>
        ))}
      </div>
      <div className={styles.folderFormActions}>
        <Button type="button" variant="secondary" size="md" onClick={onCancel}>
          {t('common.cancel')}
        </Button>
        <Button type="submit" size="md" disabled={!name.trim()}>
          {t('common.save')}
        </Button>
      </div>
    </form>
  );
}

export function FoldersModal({ folders, onClose }: FoldersModalProps) {
  const t = useT();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<'list' | 'create' | 'edit'>('list');
  const [editing, setEditing] = useState<Folder | null>(null);

  const chatsQuery = useQuery({ queryKey: ['chats'], queryFn: listChats });
  const chats = (chatsQuery.data ?? []).filter((c) => c.type !== 'saved');

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['folders'] });
  }

  const createMutation = useMutation({
    mutationFn: ({ name, chatPublicIds }: { name: string; chatPublicIds: string[] }) =>
      createFolder(name, chatPublicIds),
    onSuccess: () => {
      invalidate();
      setMode('list');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      folderPublicId,
      name,
      chatPublicIds,
    }: {
      folderPublicId: string;
      name: string;
      chatPublicIds: string[];
    }) => updateFolder(folderPublicId, { name, chatPublicIds }),
    onSuccess: () => {
      invalidate();
      setMode('list');
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (folderPublicId: string) => deleteFolder(folderPublicId),
    onSuccess: invalidate,
  });

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('folders.title')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>

        {mode === 'list' ? (
          <>
            <div className={styles.modalList}>
              {folders.length === 0 ? (
                <p className={styles.mediaEmpty}>{t('folders.empty')}</p>
              ) : (
                folders.map((folder) => (
                  <div key={folder.folderPublicId} className={styles.modalRow}>
                    <span className={styles.fileInfo}>{folder.name}</span>
                    <IconButton
                      label={t('folders.edit')}
                      onClick={() => {
                        setEditing(folder);
                        setMode('edit');
                      }}
                    >
                      <PencilIcon size={16} />
                    </IconButton>
                    <IconButton
                      label={t('common.remove')}
                      onClick={() => deleteMutation.mutate(folder.folderPublicId)}
                    >
                      <TrashIcon size={16} />
                    </IconButton>
                  </div>
                ))
              )}
            </div>
            <div className={styles.folderFormActions}>
              <Button size="md" onClick={() => setMode('create')}>
                {t('folders.create')}
              </Button>
            </div>
          </>
        ) : null}

        {mode === 'create' ? (
          <FolderForm
            chats={chats}
            onCancel={() => setMode('list')}
            onSubmit={(name, chatPublicIds) => createMutation.mutate({ name, chatPublicIds })}
          />
        ) : null}

        {mode === 'edit' && editing ? (
          <FolderForm
            chats={chats}
            initial={editing}
            onCancel={() => {
              setMode('list');
              setEditing(null);
            }}
            onSubmit={(name, chatPublicIds) =>
              updateMutation.mutate({ folderPublicId: editing.folderPublicId, name, chatPublicIds })
            }
          />
        ) : null}
      </div>
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Chat } from '../../entities/chat/model';
import { useSessionStore } from '../../entities/user/store';
import {
  addGroupMembers,
  listGroupMembers,
  removeGroupMember,
  updateGroupInfo,
  updateGroupMember,
} from '../../features/groups/api';
import { useT } from '../../shared/i18n';
import { Avatar } from '../../shared/ui/Avatar';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { CloseIcon, LinkIcon, PencilIcon, TrashIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface GroupInfoModalProps {
  chat: Chat;
  onClose: () => void;
  onOpenInvite: () => void;
  onOpenMedia: () => void;
  onLeft: () => void;
}

export function GroupInfoModal({
  chat,
  onClose,
  onOpenInvite,
  onOpenMedia,
  onLeft,
}: GroupInfoModalProps) {
  const t = useT();
  const me = useSessionStore((s) => s.user);
  const queryClient = useQueryClient();
  const [addingMembers, setAddingMembers] = useState(false);
  const [newMembers, setNewMembers] = useState('');
  const [editingInfo, setEditingInfo] = useState(false);
  const [title, setTitle] = useState(chat.title);
  const [description, setDescription] = useState(chat.description ?? '');

  const membersQuery = useQuery({
    queryKey: ['members', chat.chatPublicId],
    queryFn: () => listGroupMembers(chat.chatPublicId),
  });
  const members = membersQuery.data ?? [];
  const myMember = members.find((m) => m.userPublicId === me?.publicId);
  const isOwner = myMember?.role === 'owner';
  const canEditInfo = isOwner || myMember?.canEditInfo;
  const canInvite = isOwner || myMember?.canInvite;

  function invalidateMembers() {
    void queryClient.invalidateQueries({ queryKey: ['members', chat.chatPublicId] });
  }

  const addMembersMutation = useMutation({
    mutationFn: (usernames: string[]) => addGroupMembers(chat.chatPublicId, usernames),
    onSuccess: () => {
      invalidateMembers();
      setAddingMembers(false);
      setNewMembers('');
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userPublicId: string) => removeGroupMember(chat.chatPublicId, userPublicId),
    onSuccess: () => {
      invalidateMembers();
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
    },
  });

  const toggleAdminMutation = useMutation({
    mutationFn: ({ userPublicId, makeAdmin }: { userPublicId: string; makeAdmin: boolean }) =>
      updateGroupMember(chat.chatPublicId, userPublicId, {
        role: makeAdmin ? 'admin' : 'member',
        ...(makeAdmin
          ? {
              canDeleteMessages: true,
              canBan: true,
              canInvite: true,
              canPin: true,
              canEditInfo: true,
            }
          : {}),
      }),
    onSuccess: invalidateMembers,
  });

  const updateInfoMutation = useMutation({
    mutationFn: () =>
      updateGroupInfo(chat.chatPublicId, { title, description: description || null }),
    onSuccess: () => {
      setEditingInfo(false);
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
    },
  });

  const leaveMutation = useMutation({
    mutationFn: () => removeGroupMember(chat.chatPublicId, me!.publicId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['chats'] });
      onLeft();
    },
  });

  function roleLabel(role: string): string {
    if (role === 'owner') return t('group.info.owner');
    if (role === 'admin') return t('group.info.admin');
    return t('group.info.member');
  }

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{chat.title}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>

        <div className={styles.groupInfoBody}>
          <div className={styles.groupInfoHeaderRow}>
            <Avatar name={chat.title} src={chat.avatarUrl} size={56} />
            <div>
              <div className={styles.groupInfoTitle}>{chat.title}</div>
              <div className={styles.groupInfoSub}>
                {chat.memberCount} {t('group.membersCount')}
              </div>
            </div>
          </div>

          {editingInfo ? (
            <div className={styles.groupEditForm}>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} />
              <Input
                placeholder={t('group.info.description')}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              <Button size="md" onClick={() => updateInfoMutation.mutate()}>
                {t('common.save')}
              </Button>
            </div>
          ) : (
            <>
              {chat.description ? (
                <div className={styles.groupInfoDescription}>{chat.description}</div>
              ) : null}
              {canEditInfo ? (
                <button
                  type="button"
                  className={styles.pollAddOption}
                  onClick={() => setEditingInfo(true)}
                >
                  {t('group.info.editInfo')}
                </button>
              ) : null}
            </>
          )}

          <div className={styles.groupInfoActions}>
            {canInvite ? (
              <button type="button" className={styles.modalRow} onClick={onOpenInvite}>
                <LinkIcon size={20} />
                <span>{t('group.info.invite')}</span>
              </button>
            ) : null}
            <button type="button" className={styles.modalRow} onClick={onOpenMedia}>
              <span>{t('group.info.media')}</span>
            </button>
          </div>

          <div className={styles.groupInfoSectionTitle}>
            {t('group.info.members')} — {chat.memberCount ?? members.length}
          </div>

          {canInvite ? (
            addingMembers ? (
              <form
                className={styles.newGroupForm}
                onSubmit={(e) => {
                  e.preventDefault();
                  const usernames = newMembers
                    .split(',')
                    .map((m) => m.trim().replace(/^@/, ''))
                    .filter(Boolean);
                  if (usernames.length) addMembersMutation.mutate(usernames);
                }}
              >
                <Input
                  autoFocus
                  placeholder={t('group.newGroup.membersPlaceholder')}
                  value={newMembers}
                  onChange={(e) => setNewMembers(e.target.value)}
                />
                <Button type="submit" size="md">
                  {t('common.add')}
                </Button>
              </form>
            ) : (
              <button
                type="button"
                className={styles.pollAddOption}
                onClick={() => setAddingMembers(true)}
              >
                {t('group.info.addMembers')}
              </button>
            )
          ) : null}

          <div className={styles.modalList}>
            {members.map((member) => {
              const isSelf = member.userPublicId === me?.publicId;
              return (
                <div key={member.userPublicId} className={styles.modalRow}>
                  <Avatar
                    name={member.displayName}
                    src={member.avatarUrl}
                    size={36}
                    online={member.online}
                  />
                  <span className={styles.fileInfo}>
                    <span className={styles.fileName}>{member.displayName}</span>
                    <span className={styles.fileSize}>{roleLabel(member.role)}</span>
                  </span>
                  {isOwner && !isSelf && member.role !== 'owner' ? (
                    <>
                      <IconButton
                        label={
                          member.role === 'admin'
                            ? t('group.info.removeAdmin')
                            : t('group.info.makeAdmin')
                        }
                        onClick={() =>
                          toggleAdminMutation.mutate({
                            userPublicId: member.userPublicId,
                            makeAdmin: member.role !== 'admin',
                          })
                        }
                      >
                        <PencilIcon size={16} />
                      </IconButton>
                      <IconButton
                        label={t('group.info.remove')}
                        onClick={() => removeMemberMutation.mutate(member.userPublicId)}
                      >
                        <TrashIcon size={16} />
                      </IconButton>
                    </>
                  ) : null}
                </div>
              );
            })}
          </div>

          <button
            type="button"
            className={styles.pollAddOption}
            onClick={() => {
              if (confirm(t('group.info.leaveConfirm'))) leaveMutation.mutate();
            }}
          >
            {t('group.info.leave')}
          </button>
        </div>
      </div>
    </div>
  );
}

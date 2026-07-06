import { useState } from 'react';

import { useT } from '../../shared/i18n';
import { Button } from '../../shared/ui/Button';
import { IconButton } from '../../shared/ui/IconButton';
import { Input } from '../../shared/ui/Input';
import { CloseIcon, TrashIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';

interface PollCreatorProps {
  onClose: () => void;
  onSubmit: (poll: {
    question: string;
    options: string[];
    isAnonymous: boolean;
    multiChoice: boolean;
  }) => void;
}

const MAX_OPTIONS = 10;

export function PollCreator({ onClose, onSubmit }: PollCreatorProps) {
  const t = useT();
  const [question, setQuestion] = useState('');
  const [options, setOptions] = useState(['', '']);
  const [isAnonymous, setIsAnonymous] = useState(true);
  const [multiChoice, setMultiChoice] = useState(false);

  const trimmedOptions = options.map((o) => o.trim()).filter(Boolean);
  const canSubmit = question.trim().length > 0 && trimmedOptions.length >= 2;

  function updateOption(index: number, value: string) {
    setOptions((prev) => prev.map((o, i) => (i === index ? value : o)));
  }

  function removeOption(index: number) {
    setOptions((prev) => prev.filter((_, i) => i !== index));
  }

  function handleSubmit() {
    if (!canSubmit) return;
    onSubmit({ question: question.trim(), options: trimmedOptions, isAnonymous, multiChoice });
  }

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span>{t('poll.create')}</span>
          <IconButton label={t('common.cancel')} onClick={onClose}>
            <CloseIcon size={18} />
          </IconButton>
        </div>
        <div className={styles.pollCreatorBody}>
          <Input
            placeholder={t('poll.question')}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            autoFocus
          />
          {options.map((option, i) => (
            <div key={i} className={styles.pollOptionRow}>
              <Input
                placeholder={`${t('poll.option')} ${i + 1}`}
                value={option}
                onChange={(e) => updateOption(i, e.target.value)}
              />
              {options.length > 2 ? (
                <IconButton label={t('common.remove')} onClick={() => removeOption(i)}>
                  <TrashIcon size={16} />
                </IconButton>
              ) : null}
            </div>
          ))}
          {options.length < MAX_OPTIONS ? (
            <button
              type="button"
              className={styles.pollAddOption}
              onClick={() => setOptions((prev) => [...prev, ''])}
            >
              {t('poll.addOption')}
            </button>
          ) : null}

          <label className={styles.pollToggleRow}>
            <input
              type="checkbox"
              checked={multiChoice}
              onChange={(e) => setMultiChoice(e.target.checked)}
            />
            {t('poll.multiChoice')}
          </label>
          <label className={styles.pollToggleRow}>
            <input
              type="checkbox"
              checked={isAnonymous}
              onChange={(e) => setIsAnonymous(e.target.checked)}
            />
            {t('poll.anonymous')}
          </label>

          <Button size="lg" disabled={!canSubmit} onClick={handleSubmit}>
            {t('poll.create.submit')}
          </Button>
        </div>
      </div>
    </div>
  );
}

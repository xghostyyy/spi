import { useState } from 'react';

import type { Poll } from '../../entities/message/model';
import { useT } from '../../shared/i18n';
import styles from './ChatPage.module.css';

interface PollViewProps {
  poll: Poll;
  isOwn: boolean;
  onVote: (optionPositions: number[]) => void;
  onClose: () => void;
}

export function PollView({ poll, isOwn, onVote, onClose }: PollViewProps) {
  const t = useT();
  const [selected, setSelected] = useState<number[]>([]);
  const hasVoted = poll.options.some((o) => o.votedByMe);
  const isClosed = poll.closedAt !== null;
  const showResults = hasVoted || isClosed;

  function toggle(position: number) {
    if (poll.multiChoice) {
      setSelected((prev) =>
        prev.includes(position) ? prev.filter((p) => p !== position) : [...prev, position],
      );
    } else {
      onVote([position]);
    }
  }

  return (
    <div className={styles.pollCard}>
      <div className={styles.pollQuestion}>{poll.question}</div>
      <div className={styles.pollMeta}>
        {isClosed
          ? t('poll.closed')
          : poll.multiChoice
            ? t('poll.multiChoice')
            : t('poll.singleChoice')}
      </div>
      {poll.options.map((option) => {
        const pct = poll.totalVotes > 0 ? Math.round((option.votes / poll.totalVotes) * 100) : 0;
        return (
          <button
            key={option.position}
            type="button"
            className={styles.pollOption}
            disabled={isClosed}
            onClick={() => toggle(option.position)}
          >
            <div className={styles.pollOptionRowLine}>
              <span>
                {poll.multiChoice && !showResults ? (
                  <input
                    type="checkbox"
                    readOnly
                    checked={selected.includes(option.position)}
                    className={styles.pollCheckbox}
                  />
                ) : null}
                {option.text}
              </span>
              {showResults ? <span>{pct}%</span> : null}
            </div>
            {showResults ? (
              <div className={styles.pollBarTrack}>
                <div className={styles.pollBarFill} style={{ width: `${pct}%` }} />
              </div>
            ) : null}
          </button>
        );
      })}
      {poll.multiChoice && !showResults ? (
        <button
          type="button"
          className={styles.pollAddOption}
          disabled={selected.length === 0}
          onClick={() => onVote(selected)}
        >
          {t('poll.vote')}
        </button>
      ) : null}
      <div className={styles.pollMeta}>
        {poll.totalVotes} {t('poll.votes')}
      </div>
      {isOwn && !isClosed ? (
        <button type="button" className={styles.pollAddOption} onClick={onClose}>
          {t('poll.close')}
        </button>
      ) : null}
    </div>
  );
}

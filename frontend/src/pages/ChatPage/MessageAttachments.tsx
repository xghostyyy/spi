import type { FileAttachment } from '../../entities/message/model';
import { FileIcon } from '../../shared/ui/icons';
import styles from './ChatPage.module.css';
import { VoicePlayer } from './VoicePlayer';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface MessageAttachmentsProps {
  attachments: FileAttachment[];
  type: string;
  onImageClick: (url: string) => void;
}

export function MessageAttachments({ attachments, type, onImageClick }: MessageAttachmentsProps) {
  if (attachments.length === 0) return null;

  if (type === 'voice') {
    return <VoicePlayer file={attachments[0]!} />;
  }

  if (type === 'photo' || type === 'album') {
    return (
      <div className={styles.mediaGrid}>
        {attachments.map((file) => (
          <img
            key={file.publicId}
            src={file.thumbUrl ?? file.url}
            alt=""
            className={styles.mediaImage}
            onClick={() => onImageClick(file.url)}
          />
        ))}
      </div>
    );
  }

  if (type === 'video') {
    const file = attachments[0]!;
    return <video controls className={styles.mediaVideo} src={file.url} />;
  }

  const file = attachments[0]!;
  return (
    <a href={file.url} target="_blank" rel="noreferrer" className={styles.fileCard}>
      <FileIcon size={28} />
      <span className={styles.fileInfo}>
        <span className={styles.fileName}>{file.originalName ?? file.mimeType}</span>
        <span className={styles.fileSize}>{formatSize(file.sizeBytes)}</span>
      </span>
    </a>
  );
}

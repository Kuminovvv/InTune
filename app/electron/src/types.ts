export interface StatusMessage {
  type: 'status';
  state: 'ready' | 'listening' | 'thinking' | 'reindex' | 'error' | string;
  msg: string;
}

export interface PartialTranscriptMessage {
  type: 'partial_transcript';
  text: string;
}

export interface AnswerMessage {
  type: 'answer';
  question: string;
  hint: string;
}

export interface ErrorMessage {
  type: 'error';
  stage: string;
  msg: string;
}

export interface ReindexDoneMessage {
  type: 'reindex_done';
  docs: number;
}

export type ServerMessage =
  | StatusMessage
  | PartialTranscriptMessage
  | AnswerMessage
  | ErrorMessage
  | ReindexDoneMessage;

export interface OverlayState {
  status: StatusMessage | null;
  partial: string;
  answer: AnswerMessage | null;
  lastError: ErrorMessage | null;
  reindexedDocs: number | null;
}

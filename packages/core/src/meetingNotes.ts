import type {ManualNoteKind,ManualNoteEvidence} from './manualNoteContext';
export interface CompanionMeetingNote {
  id: string;
  text: string;
  kind?:ManualNoteKind;
  references?:ManualNoteEvidence[];
  bookmarkId?: string | null;
  image?: {file:string;name:string;bytes:number;sha256:string;preview:string;previewBytes:number;previewSha256:string}|null;
  createdAt: string;
  updatedAt: string;
}
export interface CompanionMeetingNoteRequest {
  sessionId: string;
  noteId: string;
  expectedRevision: number;
  action: 'add' | 'edit' | 'delete';
  text?: string;
  kind?:ManualNoteKind;
  references?:ManualNoteEvidence[];
  bookmarkId?: string | null;
}
export const normalizeCompanionNoteText = (value: string) => value.replace(/\r\n?/g, '\n').trim();
export type CompanionMeetingImageNoteRequest=Omit<CompanionMeetingNoteRequest,'action'|'text'>&{text:string};

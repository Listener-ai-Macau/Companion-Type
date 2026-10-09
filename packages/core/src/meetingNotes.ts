export interface CompanionMeetingNote {
  id: string;
  text: string;
  bookmarkId?: string | null;
  createdAt: string;
  updatedAt: string;
}
export interface CompanionMeetingNoteRequest {
  sessionId: string;
  noteId: string;
  expectedRevision: number;
  action: 'add' | 'edit' | 'delete';
  text?: string;
  bookmarkId?: string | null;
}
export const normalizeCompanionNoteText = (value: string) => value.replace(/\r\n?/g, '\n').trim();

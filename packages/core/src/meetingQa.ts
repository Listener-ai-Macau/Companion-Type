export interface MeetingQaCitation { sessionId: string; title: string; quote: string }
export interface MeetingQaItem { text: string; citation: MeetingQaCitation }
export interface MeetingQaResumePosition { identity: string; completed: number[] }
export interface MeetingQaResumeRequest extends MeetingQaResumePosition { items: MeetingQaItem[] }
export interface MeetingQaResult { items: MeetingQaItem[]; totalChunks: number; completedChunks: number; incomplete: boolean; cancelled: boolean; stopReason?: string; resume?: MeetingQaResumePosition }

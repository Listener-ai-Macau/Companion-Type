export interface MeetingQaCitation { sessionId: string; title: string; quote: string }
export interface MeetingQaItem { text: string; citation: MeetingQaCitation }
export interface MeetingQaResult { items: MeetingQaItem[]; totalChunks: number; completedChunks: number; incomplete: boolean; cancelled: boolean }

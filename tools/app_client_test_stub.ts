// Only bundled by the in-memory App test; never used by the production build.
const api = () => (globalThis as any).__companionAppTest;
export const isTauriRuntime = () => true;
export const getDesktopUpdateStatus = async () => ({phase:'idle',message:'fixture only',currentVersion:'0.1.0',downloadedBytes:0});
export const checkDesktopUpdate = getDesktopUpdateStatus;
export const downloadDesktopUpdate = getDesktopUpdateStatus;
export const cancelDesktopUpdate = async () => {};
export const installDesktopUpdate = async () => {};
export const getCompanionSnapshot = () => api().snapshot();
export const applyCompanionControl = (request: unknown) => api().control(request);
export const getRecordingSyncStatus = async () => api().syncStatus ? api().syncStatus() : ({ phase: 'idle', jobId: null, deviceId: null, recordingId: 0, receivedBytes: 0, totalBytes: 0, pauseRequested: false });
export const watchRecordingSync = async (listener: (status: unknown) => void) => api().watchSync ? api().watchSync(listener) : (() => {});
export const pauseRecordingSync = async (jobId: string) => api().pauseSync ? api().pauseSync(jobId) : false;
export const exportCompanionMeeting = async () => null;
export const exportCompanionAudio = async () => null;
export const exportCompanionDiagnostics = async () => null;
export const prepareCompanionAudioComponents = async () => {};
export const checkCompanionService = async (service: string) => ({ service, status: 'available', message: 'test only', elapsedMs: 1, checkedAtUnixMs: 1 });
export const prepareCompanionAudio = async (sessionId: string) => ({ sessionId, url: 'asset://test-only/recording.wav' });
export const saveCompanionMeetingEdit = async (request: unknown) => api().saveMeeting(request);
export const refineCompanionMeetingSpeakers = async (sessionId: string) => {
  if (!api().refineSpeakers) throw new Error('Speaker refinement is not configured in this App test');
  return api().refineSpeakers(sessionId);
};
export const saveCompanionMeetingNote = async (request: unknown) => {
  if (!api().saveNote) throw new Error('Meeting-note save is not configured in this App test');
  return api().saveNote(request);
};
export const saveCompanionBookmark = async (request: unknown) => {
  if (!api().saveBookmark) throw new Error('Bookmark save is not configured in this App test');
  return api().saveBookmark(request);
};
export const getProductSettings = async () => null;
export const getBoardOnlineLiveStatus = async () => api().boardStatus ? api().boardStatus() : ({ state: 'idle' });
export const saveProductSettings = async () => null;
export const startBoardOnlineLive = async () => ({ state: 'recording' });
export const stopBoardOnlineLive = async () => api().stopBoard ? api().stopBoard() : ({ state: 'completed' });
export const discardOldestDeviceRecording = async (requiredSeconds: number) => {
  if (!api().discardOldest) throw new Error('Recording discard is not configured in this App test');
  return api().discardOldest(requiredSeconds);
};
export const transferCompanionFirmwareOta = async () => ({});
export const validateCompanionOtaPackage = async () => ({});

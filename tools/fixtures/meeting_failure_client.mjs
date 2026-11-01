const state=()=>globalThis.__meetingFailureMock;
export const isTauriRuntime=()=>false;
export const getCompanionSnapshot=async()=>state().snapshot;
export const getProductSettings=async()=>null;
export const getBoardOnlineLiveStatus=async()=>null;
export const applyCompanionControl=async(request)=>{state().calls.push(request);if(state().fail)throw new Error('simulated stop failure');const next=structuredClone(state().snapshot);next.host.sessions[0].status='captured';next.meeting.active=false;state().snapshot=next;return next;};
export const getDesktopUpdateStatus=async()=>null,checkDesktopUpdate=async()=>null,downloadDesktopUpdate=async()=>null,cancelDesktopUpdate=async()=>null,installDesktopUpdate=async()=>null;
export const getRecordingSyncStatus=async()=>null,pauseRecordingSync=async()=>false,watchRecordingSync=async()=>()=>{},watchCompanionSnapshotUpdates=async()=>()=>{};
export const discardOldestDeviceRecording=async()=>null,exportCompanionMeeting=async()=>null,openCompanionSavedCalendar=async()=>{},previewCompanionMeetingExport=async()=>null;
export const exportCompanionAudio=async()=>null,exportCompanionLibrary=async()=>null,saveCompanionLibraryState=async()=>null,purgeCompanionLibrary=async()=>null;
export const exportCompanionDiagnostics=async()=>null,previewCompanionDiagnostics=async()=>null,prepareCompanionAudioComponents=async()=>{},prepareCompanionLocalAsr=async()=>{};
export const checkCompanionService=async()=>null,prepareCompanionAudio=async()=>null,saveCompanionMeetingEdit=async()=>null,saveCompanionBookmark=async()=>null,saveCompanionMeetingNote=async()=>null,saveCompanionLibraryOrganization=async()=>null;
export const saveProductSettings=async()=>null,startBoardOnlineLive=async()=>null,stopBoardOnlineLive=async()=>null,transferCompanionFirmwareOta=async()=>null,validateCompanionOtaPackage=async()=>null;
export const refineCompanionMeetingSpeakers=async()=>null,controlCompanionPetFind=async()=>null;

export const cancelCompanionMeetingProcessing=async()=>false,backupCompanionLibrary=async()=>null,restoreCompanionLibraryBackup=async()=>null;

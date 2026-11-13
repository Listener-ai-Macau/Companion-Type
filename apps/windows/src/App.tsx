import {WindowsIncomingFiles} from './WindowsIncomingFiles';
import {WindowsAudioEditor,WindowsAudioEditNotice} from './WindowsAudioEditing';
import {operationErrorText} from '../../../packages/ui/src/operationFailure';
import {transcriptionStoppedMessage,minutesStoppedMessage} from '../../../packages/ui/src/knownOperationErrors';
import { useEffect, useRef, useState } from 'react';
import {createCachedRefresh} from './cachedRefresh';

import {
  type CompanionV1ControlAction,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
} from '@companion-type/core';
import { CompanionDashboard } from '@companion-type/ui';
import {clearPlaybackMemory,clearSessionPlaybackMemory} from '../../../packages/ui/src/playbackMemory';
import { refineCompanionMeetingSpeakers,previewCompanionMeetingTranscription,previewCompanionMeetingGap,controlCompanionPetFind,askCompanionMeetings,cancelCompanionMeetingQuestion,companionDocumentAdapter } from './companionClient';
import { CompanionDesktopUpdate } from '../../../packages/ui/src/CompanionDesktopUpdate';
import { PetChat } from './PetChat';
import {CloseReview} from './CloseReview';
import {DesktopDictation} from './DesktopDictation';
import {DesktopPointer} from './DesktopPointer';
import {nativeCloseReview} from './closeReviewClient';
import type { RecordingSyncStatus } from '../../../packages/ui/src/CompanionRecordingSync';
import '../../../packages/ui/src/companionUi.css';
import '../../../packages/ui/src/companionDark.css';
import '../../../packages/ui/src/notebookFoundation.css';

import {
  getDesktopUpdateStatus, checkDesktopUpdate, downloadDesktopUpdate, cancelDesktopUpdate, installDesktopUpdate,
  applyCompanionControl,
  getRecordingSyncStatus, pauseRecordingSync, repairRecordingSyncSettings, watchRecordingSync, watchCompanionSnapshotUpdates, cancelCompanionMeetingProcessing,
  discardOldestDeviceRecording,listDeviceRecordings,syncDeviceRecording,deleteDeviceRecording,
  exportCompanionMeeting, openCompanionSavedCalendar, copyCompanionMeetingContent, shareCompanionMeetingContent,
  previewCompanionMeetingExport,
  exportCompanionAudio, shareCompanionAudio,
  importCompanionAudio,
  cancelCompanionAudioImport,
  exportCompanionLibrary,
  backupCompanionLibrary,
  restoreCompanionLibraryBackup,
  saveCompanionLibraryState,
  purgeCompanionLibrary,
  exportCompanionDiagnostics,
  previewCompanionDiagnostics,
  prepareCompanionAudioComponents,
  prepareCompanionLocalAsr,
  checkCompanionService,
  prepareCompanionAudio,
  saveCompanionMeetingEdit,
  saveCompanionBookmark,
  saveCompanionMeetingNote,checkCompanionNoteEvidence,
  addCompanionImageNote,
  previewCompanionNoteImage,
  saveCompanionLibraryOrganization,
  isTauriRuntime,
  getBoardOnlineLiveStatus,
  getCompanionSnapshot,
  getProductSettings,
  saveProductSettings,
  startBoardOnlineLive,
  stopBoardOnlineLive,
  transferCompanionFirmwareOta,
  validateCompanionOtaPackage,
  type CompanionProductSettingsPublic,
  type CompanionBoardOnlineLiveStatus,
} from './companionClient';

let meetingProcessingSequence=0;
export function App() {
  const [unsavedEdits, setUnsavedEdits] = useState(false);
  const [petUnsavedEdits,setPetUnsavedEdits]=useState(false);
  const hasUnsavedEdits=unsavedEdits||petUnsavedEdits;
  const [snapshot, setSnapshot] = useState<CompanionV1Snapshot | null>(null);
  const [busyAction, setBusyAction] = useState<CompanionV1ControlAction | 'refresh' | null>('refresh');
  const [error, setError] = useState<string | null>(null);
  const [productSettings, setProductSettings] = useState<CompanionProductSettingsPublic | null>(null);
  const [boardOnlineLive, setBoardOnlineLive] = useState<CompanionBoardOnlineLiveStatus | null>(null);
  const [boardOnlineBusy, setBoardOnlineBusy] = useState(false);
  const [recordingSync, setRecordingSync] = useState<RecordingSyncStatus | null>(null);
  const [pauseSyncBusy, setPauseSyncBusy] = useState(false);
  const [processingSessionId, setProcessingSessionId] = useState<string | null>(null);
  const [cancelProcessingPending, setCancelProcessingPending] = useState(false);
  const [processingNotice, setProcessingNotice] = useState<string | null>(null);
  const cancelProcessingActive = useRef(false);
  const processingTicket = useRef<{sessionId:string;jobId:string} | null>(null);
  const pauseSyncActive = useRef(false);
  const operationActive = useRef(false);
  const snapshotEpoch = useRef(0);
  const cachedReader = useRef<ReturnType<typeof createCachedRefresh> | null>(null);
  const readBoardCache = useRef(false);

  // Event handlers can run twice before React has rendered disabled buttons.
  // The epoch also prevents an older background read from undoing a new action.
  const exclusive = async <T,>(action: CompanionV1ControlAction | 'refresh', work: () => Promise<T>): Promise<T> => {
    if (operationActive.current) throw new Error('正在完成上一项操作，请稍候。');
    operationActive.current = true;
    snapshotEpoch.current += 1;
    setBusyAction(action);
    try { return await work(); }
    finally { operationActive.current = false; setBusyAction(null); void cachedReader.current?.resume(); }
  };

  const refresh = async () => {
    if (operationActive.current) return;
    setError(null);
    try {
      await exclusive('refresh', async () => {
        const [snap, settings, boardLive] = await Promise.all([
          getCompanionSnapshot(),
          getProductSettings().catch(() => null),
          getBoardOnlineLiveStatus().catch(() => null),
        ]);
        setSnapshot(snap);
        if (settings) setProductSettings(settings);
        if (boardLive) setBoardOnlineLive(boardLive);
      });
    } catch (err) {
      setError(operationErrorText(err,'general'));
    }
  };

  const runControl = async (request: CompanionV1ControlRequest) => {
    if (operationActive.current) return;
    const cleanupSessionId=request.sessionId??snapshot?.host.selectedSessionId;
    if (request.action === 'meetingTranscribeAudio' || request.action === 'meetingGenerateMinutes') {
      const jobId=`__meeting_job__${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${++meetingProcessingSequence}`}`;
      processingTicket.current=cleanupSessionId ? {sessionId:cleanupSessionId,jobId} : null;
      request={...request,promptId:jobId};
      setProcessingSessionId(cleanupSessionId ?? null);
      setCancelProcessingPending(false);
      setProcessingNotice(null);
    }
    setError(null);
    try {
      await exclusive(request.action, async () => {
        try {
          setSnapshot(await applyCompanionControl(request));
          if(request.action==='privacyEraseAll'&&!clearPlaybackMemory())
            setError('本机会议已清理，但回听位置尚未清除；请检查本机存储权限后重试清理。');
          if((request.action==='privacyEraseAudio'||request.action==='privacyDeleteSession')&&cleanupSessionId&&!clearSessionPlaybackMemory(cleanupSessionId))
            setError('录音清理已处理，但本机回听位置尚未清除，请检查本机存储权限。');
        } catch (controlError) {
          if (['meetingStart', 'meetingStop', 'meetingFinalize', 'meetingPause', 'meetingResume',
            'meetingRecoverControl', 'deviceSyncRecordings', 'meetingRestoreAudio',
            'meetingTranscribeAudio', 'meetingGenerateMinutes'].includes(request.action)) {
            // A stop or partial operation can commit state before returning
            // an error. Read that checkpoint without replaying the operation.
            try { setSnapshot(await getCompanionSnapshot()); }
            catch { /* Retain the last readable state and the original error. */ }
          }
          throw controlError;
        }
      });
    } catch (err) {
      const message=operationErrorText(err,'general');
      if ((request.action==='meetingTranscribeAudio' && message===transcriptionStoppedMessage) ||
          (request.action==='meetingGenerateMinutes' && message===minutesStoppedMessage)) setProcessingNotice(message);
      else setError(message);
    } finally {
      if (request.action === 'meetingTranscribeAudio' || request.action === 'meetingGenerateMinutes') {
        processingTicket.current=null;
        setProcessingSessionId(null); setCancelProcessingPending(false);
      }
    }
  };

  useEffect(() => {
    let stopped = false;
    let unlisten: (() => void) | undefined;
    const reader = createCachedRefresh({
      busy: () => operationActive.current,
      epoch: () => snapshotEpoch.current,
      read: () => Promise.allSettled([
        getCompanionSnapshot(),
        readBoardCache.current ? getBoardOnlineLiveStatus() : Promise.resolve(null),
      ]),
      apply: ([snap, live]) => {
        if (snap.status === 'fulfilled') setSnapshot(snap.value);
        if (live.status === 'fulfilled' && live.value) {
          setBoardOnlineLive(live.value);
          if (live.value.state === 'failed' && live.value.error)
            setError(operationErrorText(live.value.error, 'recording'));
        }
      },
    });
    cachedReader.current = reader;
    void (async () => {
      if (isTauriRuntime()) {
        try {
          const release = await watchCompanionSnapshotUpdates(() => { void reader.request(); });
          if (stopped) { release(); return; }
          unlisten = release;
        } catch { /* Initial/manual reads and active polling still work. */ }
      }
      // Subscribe before reading: a startup restore cannot fall between them.
      if (!stopped) await refresh();
    })();
    return () => {
      stopped = true; unlisten?.(); reader.dispose();
      if (cachedReader.current === reader) cachedReader.current = null;
    };
  }, []);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    let stopped = false;
    let unlisten: (() => void) | undefined;
    let revision = 0;
    void (async () => {
      try {
        const release = await watchRecordingSync((status) => {
          revision += 1;
          if (!stopped) setRecordingSync(status);
        });
        if (stopped) { release(); return; }
        unlisten = release;
        const readRevision = revision;
        const status = await getRecordingSyncStatus();
        if (!stopped && readRevision === revision) setRecordingSync(status);
      } catch { /* An unavailable progress stream must not hide the library. */ }
    })();
    return () => { stopped = true; unlisten?.(); };
  }, []);

  const pauseSync = async (jobId: string) => {
    if (pauseSyncActive.current) return;
    pauseSyncActive.current = true;
    setPauseSyncBusy(true);
    try {
      const accepted = await pauseRecordingSync(jobId);
      if (accepted) setRecordingSync((current) => current?.jobId === jobId
        ? { ...current, pauseRequested: true } : current);
    } catch (err) {
      setError(operationErrorText(err,'general'));
    } finally { pauseSyncActive.current = false; setPauseSyncBusy(false); }
  };

  const cancelMeetingProcessing = async (sessionId: string) => {
    if (cancelProcessingActive.current) return;
    const ticket=processingTicket.current;
    if (ticket?.sessionId!==sessionId) return;
    cancelProcessingActive.current = true;
    setCancelProcessingPending(true);
    try {
      // The click can precede the native worker's registration. Keep the
      // same unique ticket and deliver the stop as soon as it starts, without
      // asking the user to click again or stopping a later transcription.
      while (processingTicket.current===ticket && operationActive.current) {
        if (await cancelCompanionMeetingProcessing(sessionId,ticket.jobId)) return;
        await new Promise<void>(resolve=>window.setTimeout(resolve,300));
      }
    } catch (err) {
      if (processingTicket.current===ticket) {setCancelProcessingPending(false);setError(operationErrorText(err,'general'));}
    }
    finally { cancelProcessingActive.current = false; }
  };

  const liveMeeting = Boolean(snapshot?.host?.sessions?.some(
    (session) => session.status === 'recording' && session.meetingMode === 'onlineLive',
  ));
  const controlledMeeting = Boolean(snapshot?.host?.sessions?.some(
    (session) => session.status === 'recording' && session.recorderControl,
  ));
  const hostRecording = Boolean(snapshot?.host?.sessions?.some(
    (session) => session.status === 'recording' && session.source === 'hostMicrophone',
  ));
  const localMeeting = Boolean(snapshot?.host?.sessions?.some(
    (session) => session.status === 'recording' && session.source === 'hostMeeting',
  ));
  const failedLocalMeeting = snapshot?.host?.sessions?.find(session => session.status === 'recording'
    && session.source === 'hostMeeting' && session.meetingTracks?.issue);
  const stoppedOnFailure = useRef(new Set<string>());
  useEffect(() => {
    const session = failedLocalMeeting;
    if (!session || busyAction || operationActive.current || stoppedOnFailure.current.has(session.id)) return;
    // Capture has stopped accepting packets; finalize once so saved pieces can
    // be recovered. A failed finalization is shown and remains user-retryable.
    stoppedOnFailure.current.add(session.id);
    void runControl({action:'meetingStop',sessionId:session.id});
  }, [failedLocalMeeting?.id, failedLocalMeeting?.meetingTracks?.issue, busyAction]);
  const recoveringMeeting = Boolean(snapshot?.host?.sessions?.some((session) => (
    session.recovery?.intent === 'processMeeting'
    && !['idle', 'paused', 'complete'].includes(session.recovery.stage)
  )));
  const watchingDevice = Boolean(snapshot?.device.rememberedDeviceId
    && snapshot.device.autoReconnectEnabled && !snapshot.device.manualDisconnect);
  // Reading the host cache is separate from permission to reconnect. An
  // already connected device can change state even with auto-connect off.
  const observingConnectedDevice=Boolean(snapshot?.connected||snapshot?.device.connected);
  const boardActive = Boolean(boardOnlineLive
    && ['starting', 'recording', 'stopping', 'finalizing'].includes(boardOnlineLive.state));
  readBoardCache.current = liveMeeting || boardActive;
  // Active text/timing still ticks. Notifications and ticks share one reader;
  // slow native cache responses never accumulate an IPC queue.
  useEffect(() => {
    if (!liveMeeting && !controlledMeeting && !hostRecording && !localMeeting && !recoveringMeeting && !watchingDevice && !observingConnectedDevice && !boardActive) return;
    let cancelled = false;
    let timer: number;
    const delay = liveMeeting || controlledMeeting || boardActive ? 500 : localMeeting || recoveringMeeting ? 1000 : 3000;
    const poll = async () => {
      try { if (!operationActive.current) await cachedReader.current?.request(); }
      finally { if (!cancelled) timer = window.setTimeout(() => void poll(), delay); }
    };
    timer = window.setTimeout(() => void poll(), delay);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [liveMeeting, controlledMeeting, hostRecording, localMeeting, recoveringMeeting, watchingDevice, observingConnectedDevice, boardActive]);

  return (
    <div className="ct-window-shell">
    {isTauriRuntime()?<CloseReview unsaved={hasUnsavedEdits} client={nativeCloseReview}/>:null}
    <CompanionDashboard
      deviceExtra={isTauriRuntime()?<><DesktopDictation connected={Boolean(snapshot?.device.connected&&snapshot.device.mode==='windowsNative')}
        blocked={busyAction!==null||boardOnlineBusy||Boolean(snapshot?.device.recording||snapshot?.meeting.active)}/><DesktopPointer connected={Boolean(snapshot?.device.connected&&snapshot.device.mode==='windowsNative')}
        blocked={busyAction!==null||boardOnlineBusy||Boolean(snapshot?.device.recording||snapshot?.meeting.active)}/></>:null}
      petPanel={isTauriRuntime()?<PetChat onUnsavedChange={setPetUnsavedEdits} connected={Boolean(snapshot?.device.connected)} deviceUid={snapshot?.device.connected?snapshot.device.mcuUid:null}
        disabled={busyAction!==null||boardOnlineBusy||!!snapshot?.device.recording||!!snapshot?.meeting.active}/>:null}
      onAskMeetings={isTauriRuntime()?askCompanionMeetings:undefined}
      documentAdapter={isTauriRuntime()?companionDocumentAdapter:undefined}
      renderAudioEditor={isTauriRuntime()?props=><WindowsAudioEditor key={props.contextId} {...props}/>:undefined}
      renderIncomingFiles={isTauriRuntime()?onOpen=><WindowsIncomingFiles busy={busyAction!==null||boardOnlineBusy||hasUnsavedEdits||Boolean(snapshot?.device.recording||snapshot?.meeting.active)} onChanged={()=>void refresh()} onOpen={onOpen}/>:undefined}
      audioEditNotice={isTauriRuntime()?<WindowsAudioEditNotice onChanged={()=>void refresh()}/>:null}
      onCancelMeetingQuestion={isTauriRuntime()?cancelCompanionMeetingQuestion:undefined}
      onReadLicenses={() => Promise.all([import('../src-tauri/resources/licenses/ThirdPartyNotices.txt?raw'), import('../src-tauri/resources/licenses/OptionalSpeechModels.txt?raw'), import('../src-tauri/resources/licenses/ShadcnDashboardMIT.txt?raw'), import('../src-tauri/resources/licenses/AirCursorMIT.txt?raw'), import('../src-tauri/resources/licenses/WatchPointerMIT.txt?raw'), import('../src-tauri/resources/licenses/FusionMIT.txt?raw')]).then(([components, models, template, air, watch, fusion]) => `${components.default}\n\n${models.default}\n\nShadcn Dashboard — https://github.com/shadcndashboard/shadcndashboard\n${template.default}\n\nAirCursor — https://github.com/m-afham/AirCursor\n${air.default}\n\nWatchPointer — https://github.com/umarz317/WatchPointer\n${watch.default}\n\nFusion — https://github.com/xioTechnologies/Fusion\n${fusion.default}`)}
      onFindPet={isTauriRuntime()?(request)=>exclusive('refresh',()=>controlCompanionPetFind(request)):undefined}
      settingsFooter={isTauriRuntime() ? <CompanionDesktopUpdate blocked={busyAction!==null || boardOnlineBusy || Boolean(snapshot?.device.recording || snapshot?.meeting.active
        || snapshot?.host.sessions.some(session=>session.status==='recording') || (snapshot?.host.persistence && snapshot.host.persistence.status!=='ready'))}
        unsaved={hasUnsavedEdits} onStatus={getDesktopUpdateStatus} onCheck={checkDesktopUpdate}
        onDownload={() => exclusive('refresh', downloadDesktopUpdate)} onCancel={cancelDesktopUpdate}
        onInstall={() => exclusive('refresh', installDesktopUpdate)} /> : null}
      onUnsavedChange={setUnsavedEdits}
      snapshot={snapshot}
      busyAction={busyAction}
      error={error}
      surface="windows"
      productSettings={productSettings}
      boardOnlineLive={boardOnlineLive}
      boardOnlineBusy={boardOnlineBusy}
      recordingSync={recordingSync}
      pauseSyncBusy={pauseSyncBusy}
      onPauseSync={isTauriRuntime() ? (jobId) => void pauseSync(jobId) : undefined}
      onRepairSync={isTauriRuntime() ? async () => {setRecordingSync(await repairRecordingSyncSettings());} : undefined}
      processingSessionId={processingSessionId}
      cancelProcessingPending={cancelProcessingPending}
      processingNotice={processingNotice}
      onCancelMeetingProcessing={isTauriRuntime() ? (sessionId) => void cancelMeetingProcessing(sessionId) : undefined}
      onRefresh={() => void refresh()}
      onControl={(request) => void runControl(request)}
      onExportMeeting={(request) => exclusive('refresh', async () => {
        const result=await exportCompanionMeeting(request);
        if(result && request.format.startsWith('calendar')) {
          // Cached host snapshot only: never probe the board to show a local receipt.
          try {setSnapshot(await getCompanionSnapshot());}
          catch {result.warning=[result.warning,'文件已保存；请重新打开记录核对本机副本说明。'].filter(Boolean).join(' ');}
        }
        return result;
      })}
      onCopyMeetingContent={isTauriRuntime()?copyCompanionMeetingContent:undefined}
      onShareMeetingContent={isTauriRuntime()?(request,destination)=>exclusive('refresh',()=>shareCompanionMeetingContent(request,destination)):undefined}
      onOpenSavedCalendar={isTauriRuntime()?openCompanionSavedCalendar:undefined}
      onPreviewMeetingExport={(request)=>previewCompanionMeetingExport(request)}
      onExportDiagnostics={isTauriRuntime() ? (includeDevice) => exclusive('refresh', () => exportCompanionDiagnostics(includeDevice)) : undefined}
      onPreviewDiagnostics={isTauriRuntime() ? () => exclusive('refresh',previewCompanionDiagnostics) : undefined}
      onPrepareAudioComponents={isTauriRuntime() ? () => exclusive('refresh', prepareCompanionAudioComponents) : undefined}
      onPrepareLocalAsr={isTauriRuntime() ? () => exclusive('refresh', async () => { await prepareCompanionLocalAsr(); setProductSettings(await getProductSettings()); }) : undefined}
      onCheckService={isTauriRuntime() ? (service) => exclusive('refresh', () => checkCompanionService(service)) : undefined}
      onCancelImportAudio={isTauriRuntime() ? cancelCompanionAudioImport : undefined}
      onImportAudio={isTauriRuntime() ? async () => { const epoch=snapshotEpoch.current; const next=await importCompanionAudio(); if(next) { if(!operationActive.current && snapshotEpoch.current===epoch) { snapshotEpoch.current+=1; setSnapshot(next); } else void cachedReader.current?.request(); } return next; } : undefined}
      onPrepareAudio={isTauriRuntime() ? (sessionId) => exclusive('refresh', () => prepareCompanionAudio(sessionId)) : undefined}
      onExportAudio={isTauriRuntime() ? (sessionId,format) => exclusive('refresh', () => exportCompanionAudio(sessionId,format)) : undefined}
      onShareAudio={isTauriRuntime() ? (sessionId,format,destination) => exclusive('refresh',()=>shareCompanionAudio(sessionId,format,destination)):undefined}
      onExportLibrary={isTauriRuntime()?(request)=>exclusive('refresh',()=>exportCompanionLibrary(request)):undefined}
      onBackupLibrary={isTauriRuntime()?(draft)=>exclusive('refresh',()=>backupCompanionLibrary(draft)):undefined}
      onRestoreLibrary={isTauriRuntime()?()=>exclusive('refresh',async()=>{
        const next=await restoreCompanionLibraryBackup();if(next)setSnapshot(next);return next;
      }):undefined}
      onSaveLibraryLifecycle={isTauriRuntime()?(request)=>exclusive('refresh',async()=>{
        const next=await saveCompanionLibraryState(request);setSnapshot(next);return next;
      }):undefined}
      onPurgeLibrary={isTauriRuntime()?(request)=>exclusive('refresh',async()=>{
        const result=await purgeCompanionLibrary(request);setSnapshot(result.snapshot);
        let memoryFailed=false;for(const id of result.deleted)if(!clearSessionPlaybackMemory(id))memoryFailed=true;
        if(memoryFailed)result.warning='部分回听位置未清除，请检查本机存储权限。';
        return result;
      }):undefined}
      deviceRecordingActions={isTauriRuntime()?{
        list:()=>exclusive('refresh',listDeviceRecordings),
        sync:(key)=>exclusive('refresh',async()=>{setSnapshot(await syncDeviceRecording(key));}),
        delete:(key)=>exclusive('refresh',()=>deleteDeviceRecording(key)),
      }:undefined}
      onDiscardOldestRecording={isTauriRuntime() ? (seconds) => exclusive('refresh', async () => {
        const result = await discardOldestDeviceRecording(seconds);
        if (result.status === 'deleted') {
          try { setSnapshot(await applyCompanionControl({ action: 'oobeRunChecks' })); }
          catch { return { ...result, message: `${result.message} 容量重读未完成，请手动重新读取。` }; }
        }
        return result;
      }) : undefined}
      onSaveMeeting={isTauriRuntime() ? (request) => exclusive('refresh', async () => {
        const saved = await saveCompanionMeetingEdit(request);
        setSnapshot(saved);
        return saved;
      }) : undefined}
      onRefineSpeakers={isTauriRuntime() ? (sessionId) => exclusive('refresh',async()=>{
        const saved=await refineCompanionMeetingSpeakers(sessionId);setSnapshot(saved);return saved;
      }):undefined}
      onPreviewRetranscription={isTauriRuntime() ? async (sessionId) => {
        if (operationActive.current) throw new Error('正在完成上一项操作，请稍候。');
        const jobId=`__meeting_job__${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${++meetingProcessingSequence}`}`;
        processingTicket.current={sessionId,jobId}; setProcessingSessionId(sessionId);
        setCancelProcessingPending(false); setProcessingNotice(null);
        try { return await exclusive('meetingTranscribeAudio',()=>previewCompanionMeetingTranscription(sessionId,jobId)); }
        finally { processingTicket.current=null; setProcessingSessionId(null); setCancelProcessingPending(false); }
      }:undefined}
      onPreviewGap={isTauriRuntime() ? async (sessionId,range) => {
        if (operationActive.current) throw new Error('正在完成上一项操作，请稍候。');
        const jobId=`__meeting_job__${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${++meetingProcessingSequence}`}`;
        processingTicket.current={sessionId,jobId}; setProcessingSessionId(sessionId);
        setCancelProcessingPending(false); setProcessingNotice(null);
        try { return await exclusive('meetingTranscribeAudio',()=>previewCompanionMeetingGap(sessionId,jobId,range)); }
        finally { processingTicket.current=null; setProcessingSessionId(null); setCancelProcessingPending(false); }
      }:undefined}
      onSaveBookmark={isTauriRuntime() ? (request) => exclusive('refresh',async()=>{
        try { const saved=await saveCompanionBookmark(request);setSnapshot(saved);return saved; }
        catch (error) { try {setSnapshot(await getCompanionSnapshot());}catch { /* keep the last readable library */ } throw error; }
      }):undefined}
      onAddImageNote={isTauriRuntime()?(request)=>exclusive('refresh',async()=>{try{const saved=await addCompanionImageNote(request);if(saved)setSnapshot(saved);return saved;}catch(error){try{setSnapshot(await getCompanionSnapshot());}catch{}throw error;}}):undefined}
      onCheckNoteEvidence={isTauriRuntime()?checkCompanionNoteEvidence:undefined}
      onPreviewNoteImage={isTauriRuntime()?previewCompanionNoteImage:undefined}
      onSaveNote={isTauriRuntime() ? (request) => exclusive('refresh',async()=>{
        try { const saved=await saveCompanionMeetingNote(request);setSnapshot(saved);return saved; }
        catch (error) { try {setSnapshot(await getCompanionSnapshot());}catch { /* retain the last readable library */ } throw error; }
      }):undefined}
      onSaveLibraryOrganization={isTauriRuntime()?(request)=>exclusive('refresh',async()=>{
        try{const saved=await saveCompanionLibraryOrganization(request);setSnapshot(saved);return saved;}
        catch(error){try{setSnapshot(await getCompanionSnapshot());}catch{/* retain last readable library */}throw error;}
      }):undefined}
      onStartBoardOnlineLive={async (request) => {
        if (operationActive.current) return;
        setBoardOnlineBusy(true);
        setError(null);
        try {
          await exclusive('meetingStart', async () => {
            setBoardOnlineLive(await startBoardOnlineLive(request));
            setSnapshot(await getCompanionSnapshot());
          });
        } catch (err) {
          setError(operationErrorText(err,'general'));
        } finally {
          setBoardOnlineBusy(false);
        }
      }}
      onStopBoardOnlineLive={async () => {
        if (operationActive.current) return;
        setBoardOnlineBusy(true);
        setError(null);
        try {
          await exclusive('meetingStop', async () => setBoardOnlineLive(await stopBoardOnlineLive()));
        } catch (err) {
          setError(operationErrorText(err,'general'));
        } finally {
          setBoardOnlineBusy(false);
        }
      }}
      onSaveProductSettings={async (patch) => {
        await exclusive('refresh', async () => {
          const saved = await saveProductSettings(patch);
          setProductSettings(saved);
        });
      }}
      onValidateOtaPackage={async (paths) =>
        validateCompanionOtaPackage({
          manifestPath: paths.manifestPath,
          firmwarePath: paths.firmwarePath,
        })
      }
      onTransferOtaPackage={async (paths) =>
        exclusive('refresh', () => transferCompanionFirmwareOta({
          manifestPath: paths.manifestPath,
          firmwarePath: paths.firmwarePath,
          deviceId: paths.deviceId,
        }))
      }
    />
    </div>
  );
}

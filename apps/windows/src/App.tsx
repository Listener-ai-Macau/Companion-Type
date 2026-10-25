import {operationErrorText} from '../../../packages/ui/src/operationFailure';
import { useEffect, useRef, useState } from 'react';
import {createCachedRefresh} from './cachedRefresh';

import {
  type CompanionV1ControlAction,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
} from '@companion-type/core';
import { CompanionDashboard } from '@companion-type/ui';
import {clearPlaybackMemory,clearSessionPlaybackMemory} from '../../../packages/ui/src/playbackMemory';
import { refineCompanionMeetingSpeakers,controlCompanionPetFind } from './companionClient';
import { CompanionDesktopUpdate } from '../../../packages/ui/src/CompanionDesktopUpdate';
import { PetChat } from './PetChat';
import {CloseReview} from './CloseReview';
import {nativeCloseReview} from './closeReviewClient';
import type { RecordingSyncStatus } from '../../../packages/ui/src/CompanionRecordingSync';
import '../../../packages/ui/src/companionUi.css';

import {
  getDesktopUpdateStatus, checkDesktopUpdate, downloadDesktopUpdate, cancelDesktopUpdate, installDesktopUpdate,
  applyCompanionControl,
  getRecordingSyncStatus, pauseRecordingSync, watchRecordingSync, watchCompanionSnapshotUpdates,
  discardOldestDeviceRecording,
  exportCompanionMeeting,
  exportCompanionAudio,
  exportCompanionLibrary,
  saveCompanionLibraryState,
  purgeCompanionLibrary,
  exportCompanionDiagnostics,
  previewCompanionDiagnostics,
  prepareCompanionAudioComponents,
  checkCompanionService,
  prepareCompanionAudio,
  saveCompanionMeetingEdit,
  saveCompanionBookmark,
  saveCompanionMeetingNote,
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
            'meetingTranscribeAudio'].includes(request.action)) {
            // STOP or a partial sync can commit real state before its transfer
            // fails. Read that checkpoint while this operation still owns the
            // UI gate; never infer a STOP or replay a recording command.
            try { setSnapshot(await getCompanionSnapshot()); }
            catch { /* Retain the last readable state and the original error. */ }
          }
          throw controlError;
        }
      });
    } catch (err) {
      setError(operationErrorText(err,'general'));
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

  const liveMeeting = Boolean(snapshot?.host?.sessions?.some(
    (session) => session.status === 'recording' && session.meetingMode === 'onlineLive',
  ));
  const controlledMeeting = Boolean(snapshot?.host?.sessions?.some(
    (session) => session.status === 'recording' && session.recorderControl,
  ));
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
    if (!liveMeeting && !controlledMeeting && !recoveringMeeting && !watchingDevice && !observingConnectedDevice && !boardActive) return;
    let cancelled = false;
    let timer: ReturnType<typeof window.setTimeout>;
    const delay = liveMeeting || controlledMeeting || boardActive ? 500 : recoveringMeeting ? 1000 : 3000;
    const poll = async () => {
      try { if (!operationActive.current) await cachedReader.current?.request(); }
      finally { if (!cancelled) timer = window.setTimeout(() => void poll(), delay); }
    };
    timer = window.setTimeout(() => void poll(), delay);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [liveMeeting, controlledMeeting, recoveringMeeting, watchingDevice, observingConnectedDevice, boardActive]);

  return (
    <div className="ct-window-shell">
    {isTauriRuntime()?<CloseReview unsaved={hasUnsavedEdits} client={nativeCloseReview}/>:null}
    {isTauriRuntime()?<details className="ct-pet-chat-disclosure">
      <summary>我的宠物</summary>
      <PetChat onUnsavedChange={setPetUnsavedEdits} deviceUid={snapshot?.device.connected?snapshot.device.mcuUid:null}
        disabled={busyAction!==null||boardOnlineBusy||!!snapshot?.device.recording||!!snapshot?.meeting.active}/>
    </details>:null}
    <CompanionDashboard
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
      onRefresh={() => void refresh()}
      onControl={(request) => void runControl(request)}
      onExportMeeting={(request) => exclusive('refresh', () => exportCompanionMeeting(request))}
      onExportDiagnostics={isTauriRuntime() ? (includeDevice) => exclusive('refresh', () => exportCompanionDiagnostics(includeDevice)) : undefined}
      onPreviewDiagnostics={isTauriRuntime() ? () => exclusive('refresh',previewCompanionDiagnostics) : undefined}
      onPrepareAudioComponents={isTauriRuntime() ? () => exclusive('refresh', prepareCompanionAudioComponents) : undefined}
      onCheckService={isTauriRuntime() ? (service) => exclusive('refresh', () => checkCompanionService(service)) : undefined}
      onPrepareAudio={isTauriRuntime() ? (sessionId) => exclusive('refresh', () => prepareCompanionAudio(sessionId)) : undefined}
      onExportAudio={isTauriRuntime() ? (sessionId) => exclusive('refresh', () => exportCompanionAudio(sessionId)) : undefined}
      onExportLibrary={isTauriRuntime()?(request)=>exclusive('refresh',()=>exportCompanionLibrary(request)):undefined}
      onSaveLibraryLifecycle={isTauriRuntime()?(request)=>exclusive('refresh',async()=>{
        const next=await saveCompanionLibraryState(request);setSnapshot(next);return next;
      }):undefined}
      onPurgeLibrary={isTauriRuntime()?(request)=>exclusive('refresh',async()=>{
        const result=await purgeCompanionLibrary(request);setSnapshot(result.snapshot);
        let memoryFailed=false;for(const id of result.deleted)if(!clearSessionPlaybackMemory(id))memoryFailed=true;
        if(memoryFailed)result.warning='部分回听位置未清除，请检查本机存储权限。';
        return result;
      }):undefined}
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
      onSaveBookmark={isTauriRuntime() ? (request) => exclusive('refresh',async()=>{
        try { const saved=await saveCompanionBookmark(request);setSnapshot(saved);return saved; }
        catch (error) { try {setSnapshot(await getCompanionSnapshot());}catch { /* keep the last readable library */ } throw error; }
      }):undefined}
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

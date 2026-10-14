/** Async preparation can outlive a selected meeting. Check the session/audio
 * binding at every wait and before seeking; never start speaker playback here. */
export async function seekBookmarkAudio(positionMs:number, prepare:()=>Promise<void>,
  player:()=>HTMLAudioElement|null, stillCurrent:()=>boolean, beforeSeek?:()=>void):Promise<void> {
  if (!Number.isSafeInteger(positionMs)||positionMs<0||!stillCurrent()) throw new Error('重点或原音身份已变化，请重新核对。');
  await prepare();
  const deadline=Date.now()+4000;
  while (stillCurrent() && (!player() || player()!.readyState<1) && Date.now()<deadline) {
    await new Promise((resolve)=>setTimeout(resolve,40));
  }
  const audio=player();
  if (!stillCurrent()) throw new Error('已切换会议，未定位其他会议的原音。');
  if (!audio||audio.readyState<1||!Number.isFinite(audio.duration)) throw new Error('原音尚未准备完成，请重试回听。');
  const seconds=positionMs/1000;
  if (seconds>audio.duration) throw new Error('这个重点超出原音范围，未跳转到其他位置。');
  beforeSeek?.(); audio.pause(); audio.currentTime=seconds;
}

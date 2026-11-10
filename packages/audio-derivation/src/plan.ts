/** Sample-accurate, non-destructive edits over verified canonical PCM sources.
 * No filenames or mutable UI playback times are accepted as source identity.
 * Native adapters must revalidate these snapshots before reading or publishing.
 */
export const DERIVATION_RATE=16000;
export type SourceIdentity={key:string;identity:string;frames:number;sampleRate:16000};
export type SourceSlice={sourceKey:string;sourceIdentity:string;startFrame:number;endFrame:number};
export type MappedSlice=SourceSlice&{outputStartFrame:number;outputEndFrame:number};
export type DerivationPlan={schema:1;sampleRate:16000;frames:number;slices:MappedSlice[]};
export type SourcePosition={sourceKey:string;sourceIdentity:string;sourceFrame:number;outputFrame:number};
export class AudioPlanError extends Error {constructor(message:string){super(message);this.name='AudioPlanError';}}
function integer(n:unknown):n is number{return typeof n==='number'&&Number.isSafeInteger(n)&&n>=0;}
function identity(value:unknown):value is string{return typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);}
function key(value:unknown):value is string{return typeof value==='string'&&value.length>0&&value.length<=1200&&!/[\u0000-\u001f\u007f]/.test(value);}
function fail(message:string):never{throw new AudioPlanError(message);}

/** Preserve caller order, including deliberate repetition and nonadjacent clips.
 * Half-open integer sample ranges keep all boundary decisions deterministic.
 */
export function createDerivationPlan(sources:readonly SourceIdentity[],slices:readonly SourceSlice[]):DerivationPlan{
 if(!Array.isArray(sources)||!Array.isArray(slices)||!slices.length)fail('请选择至少一段音频。');
 if(sources.length>128||slices.length>512)fail('本次编辑片段过多，请分批保存。');
 const known=new Map<string,SourceIdentity>();
 for(const source of sources){
  if(!source||!key(source.key)||!identity(source.identity)||!integer(source.frames)||source.frames===0||source.sampleRate!==DERIVATION_RATE)fail('原音身份或完整长度尚未确认，请重新读取。');
  if(known.has(source.key))fail('原音身份重复，请重新读取所选录音。');
  known.set(source.key,source);
 }
 let total=0;const mapped:MappedSlice[]=[];
 for(const slice of slices){
  const source=slice&&known.get(slice.sourceKey);
  if(!source||!identity(slice.sourceIdentity)||slice.sourceIdentity!==source.identity)fail('原音已变化，请重新选择编辑范围。');
  if(!integer(slice.startFrame)||!integer(slice.endFrame)||slice.endFrame<=slice.startFrame||slice.endFrame>source.frames)fail('编辑区间超出原音范围，请重新选择。');
  const count=slice.endFrame-slice.startFrame,end=total+count;
  if(!Number.isSafeInteger(end))fail('合并后的音频长度超出当前处理范围。');
  mapped.push({sourceKey:source.key,sourceIdentity:source.identity,startFrame:slice.startFrame,endFrame:slice.endFrame,outputStartFrame:total,outputEndFrame:end});total=end;
 }
 return {schema:1,sampleRate:DERIVATION_RATE,frames:total,slices:mapped};
}

/** Never trust persisted/IPC output offsets. Rebuild and compare the full map. */
export function validateDerivationPlan(value:unknown,sources:readonly SourceIdentity[]):DerivationPlan{
 if(!value||typeof value!=='object'||Array.isArray(value))fail('派生音频来源无法读取。');
 const plan=value as Partial<DerivationPlan>;
 if(plan.schema!==1||plan.sampleRate!==DERIVATION_RATE||!Array.isArray(plan.slices)||!integer(plan.frames))fail('派生音频来源版本或长度无效。');
 const expected=createDerivationPlan(sources,plan.slices);
 if(plan.frames!==expected.frames||plan.slices.some((slice,i)=>slice.outputStartFrame!==expected.slices[i].outputStartFrame||slice.outputEndFrame!==expected.slices[i].outputEndFrame))fail('派生音频时间对应已损坏，请保留原件后重新生成。');
 return expected;
}

/** The exact end is outside playable samples; it must not map to a false word. */
export function locateOriginal(plan:DerivationPlan,outputFrame:number):SourcePosition|null{
 if(!integer(outputFrame)||outputFrame>=plan.frames)return null;
 const slice=plan.slices.find(s=>outputFrame>=s.outputStartFrame&&outputFrame<s.outputEndFrame);
 return slice?{sourceKey:slice.sourceKey,sourceIdentity:slice.sourceIdentity,sourceFrame:slice.startFrame+outputFrame-slice.outputStartFrame,outputFrame}:null;
}

/** Return one source range per intersection, rather than claiming a continuous
 * original meeting across gaps, repetitions or two different recordings.
 */
export function originalRanges(plan:DerivationPlan,startFrame:number,endFrame:number):MappedSlice[]{
 if(!integer(startFrame)||!integer(endFrame)||endFrame<=startFrame||endFrame>plan.frames)fail('回找区间超出派生音频范围。');
 const ranges:MappedSlice[]=[];
 for(const slice of plan.slices){
  const start=Math.max(startFrame,slice.outputStartFrame),end=Math.min(endFrame,slice.outputEndFrame);
  if(start<end)ranges.push({sourceKey:slice.sourceKey,sourceIdentity:slice.sourceIdentity,startFrame:slice.startFrame+start-slice.outputStartFrame,endFrame:slice.startFrame+end-slice.outputStartFrame,outputStartFrame:start,outputEndFrame:end});
 }
 return ranges;
}

/** UI milliseconds are converted only at the final boundary. Selecting the
 * complete source retains its last partial millisecond instead of truncating.
 */
export function rangeFromMilliseconds(source:SourceIdentity,startMs:number,endMs:number,throughEnd=false):SourceSlice{
 if(!Number.isFinite(startMs)||!Number.isFinite(endMs)||startMs<0||endMs<=startMs)fail('请选择有效的音频开始与结束位置。');
 const startFrame=Math.floor(startMs*DERIVATION_RATE/1000),endFrame=throughEnd?source.frames:Math.floor(endMs*DERIVATION_RATE/1000);
 const slice={sourceKey:source.key,sourceIdentity:source.identity,startFrame,endFrame};createDerivationPlan([source],[slice]);return slice;
}

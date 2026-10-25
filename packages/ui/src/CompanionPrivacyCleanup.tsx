import type { CompanionV1PrivacyCleanup } from '@companion-type/core';

/** A host result, not a device/cloud erase receipt or a whole-history guarantee. */
export function CompanionPrivacyCleanup({ result }: { result?: CompanionV1PrivacyCleanup }) {
  if (!result) return null;
  const scope = { audio: '本机原音', text: '本机文字、纪要与备注', session: '所选本机会议', allMeetings: '全部本机会议' }[result.operation];
  if (!scope) return null;
  const kept = result.skippedFiles > 0 || result.sharedFiles > 0 || result.unverifiedCacheFiles > 0;
  const time = new Date(result.completedAt);
  return <section className="ct-step-meta" aria-label="最近一次本机清理结果">
    <p role={result.indexSaved ? 'status' : 'alert'}>
      {result.indexSaved ? `已处理${scope}，删除 ${result.deletedFiles} 个受管文件。`
        : '文件处理结果已返回，会议索引尚未确认保存。请先保留当前状态，处理页面上的保存提示后再核对。'}
      {kept ? ' 有保留项待核对。' : ''}
    </p>
    <details>
      <summary>查看本次清理明细{kept ? ' · 有保留项' : ''}</summary>
      {kept ? <p>保留项：共享文件 {result.sharedFiles} 项，未纳入本次清理 {result.skippedFiles} 项，无法确认归属的旧缓存 {result.unverifiedCacheFiles} 项。保留项尚未删除，请核对后单独处理。</p> : null}
      {Number.isFinite(time.getTime()) ? <p>本次打开软件内的操作时间：<time dateTime={result.completedAt}>{time.toLocaleString()}</time></p> : null}
      <p>这里只记录最近一次返回的本机结果；设备、其它副本和远端资料需分别核对。</p>
    </details>
  </section>;
}

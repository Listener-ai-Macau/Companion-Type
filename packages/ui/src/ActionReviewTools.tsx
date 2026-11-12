import {useRef,useState} from 'react';
import {Copy,Filter,Search} from 'lucide-react';
import {actionFollowupText,actionReviewActive,actionReviewMatches,emptyActionReviewFilter,type ActionReviewFilter,type ReviewAction} from './actionReview';
import './actionReviewTools.css';

export function useActionReview(items:readonly ReviewAction[],contextKey:string){
 const [state,setState]=useState({contextKey,filter:{...emptyActionReviewFilter}});
 const filter=state.contextKey===contextKey?state.filter:emptyActionReviewFilter;
 const change=(patch:Partial<ActionReviewFilter>)=>setState({contextKey,filter:{...filter,...patch}});
 const visible=items.filter(item=>actionReviewMatches(item,filter));
 return {items,visible,filter,change,clear:()=>setState({contextKey,filter:{...emptyActionReviewFilter}})};
}
type Review=ReturnType<typeof useActionReview>;
export function ActionReviewTools({review,title='',blocked=false,onCopy}:{review:Review;title?:string;blocked?:boolean;onCopy?:(text:string)=>Promise<void>}){
 const [draftOpen,setDraftOpen]=useState(false),[feedback,setFeedback]=useState({source:'',notice:'',error:''}),[copying,setCopying]=useState(false);
 const {items,visible,filter,change}=review;
 const identity=JSON.stringify([title,items,filter]);const current=useRef(identity);current.current=identity;
 const notice=feedback.source===identity?feedback.notice:'',error=feedback.source===identity?feedback.error:'';
 const owners=[...new Set(items.map(item=>item.owner?.trim()).filter((owner):owner is string=>!!owner))];
 const body=actionFollowupText(visible,title),active=actionReviewActive(filter);
 async function copy(){if(copying||blocked||!body)return;const source=identity;setCopying(true);setFeedback({source,notice:'',error:''});try{
  if(onCopy)await onCopy(body);else if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(body);else throw Error('当前无法直接复制，可在下方选择跟进文字复制。');
  if(current.current===source)setFeedback({source,notice:'当前筛选事项的跟进文字已复制，尚未发送。',error:''});
 }catch(e){if(current.current===source)setFeedback({source,notice:'',error:e instanceof Error?e.message:String(e)});}finally{setCopying(false);}}
 return <div className="action-review-tools" aria-label="事项筛选与跟进">
  <details className="action-review-filters"><summary><Filter size={14} aria-hidden="true"/><span>筛选与跟进工具</span><small>显示 {visible.length} / {items.length} 项{!active&&items.some(item=>item.needsReview)?` · ${items.filter(item=>item.needsReview).length} 项待核对`:''}</small></summary>
   <div className="action-review-fields"><label className="action-review-search"><Search size={14} aria-hidden="true"/><input aria-label="查找事项" placeholder="查找事项、负责人或时间" value={filter.query} onChange={event=>change({query:event.target.value})}/></label>
    <label>负责人<select aria-label="筛选负责人" value={filter.owner} onChange={event=>change({owner:event.target.value})}><option value="">全部负责人</option>{filter.owner&&!owners.includes(filter.owner)&&<option value={filter.owner}>{filter.owner}（当前无事项）</option>}{owners.map(owner=><option key={owner} value={owner}>{owner}</option>)}</select></label>
    <label>完成状态<select aria-label="筛选完成状态" value={filter.status} onChange={event=>change({status:event.target.value as ActionReviewFilter['status']})}><option value="all">全部状态</option><option value="open">未完成</option><option value="done">已标记完成</option></select></label>
    <label>待补信息<select aria-label="筛选待补信息" value={filter.missing} onChange={event=>change({missing:event.target.value as ActionReviewFilter['missing']})}><option value="all">全部事项</option><option value="review">待核对内容</option><option value="owner">负责人未明确</option><option value="time">未单独填写时间</option></select></label>
   </div>
  <div className="action-review-result"><span role="status">{active?`当前显示 ${visible.length} 项，全部 ${items.length} 项仍保留。`:'可筛选后整理跟进文字；原事项和原话保持不变。'}</span>{active&&<button type="button" onClick={()=>{review.clear();setFeedback({source:'',notice:'',error:''});}}>清除筛选</button>}</div>
  {!visible.length&&<p className="action-review-empty">没有符合当前条件的事项，可清除筛选查看全部。</p>}
  <button type="button" className="action-review-draft-button" disabled={!visible.length||blocked} onClick={()=>{setDraftOpen(v=>!v);setFeedback({source:'',notice:'',error:''});}}>{draftOpen?'收起跟进草稿':'整理当前事项为跟进草稿'}</button>
  {draftOpen&&<section className="action-review-draft" aria-label="当前筛选事项的跟进草稿"><h4>跟进草稿</h4><p>仅使用当前筛选的已保存事项。要修改内容、负责人或时间，请先修改并保存原事项；此处会随之更新。</p><textarea aria-label="当前筛选事项的跟进文字" readOnly value={body} onFocus={event=>event.currentTarget.select()}/><button type="button" disabled={blocked||copying||!body} onClick={()=>void copy()}><Copy size={14} aria-hidden="true"/>{copying?'正在复制…':'复制跟进文字'}</button>{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}</section>}
  </details>
 </div>;
}

import assert from 'node:assert/strict';
import React from 'react';
import {act,create,type ReactTestRenderer} from 'react-test-renderer';
import {ActionReviewTools,useActionReview} from '../packages/ui/src/ActionReviewTools';
import {savedActionReview} from '../packages/ui/src/actionReview';
import {MobileActionCards} from '../apps/mobile/src/MobileActionCards';
import {MinutesDocument} from '../apps/mobile/src/MinutesDocument';
import {savedActions,markSavedAction} from '../packages/ui/src/savedActions';
import publicActions from './qa/actions_followup20261110/public-phone-actions.json';

const text=(node:any):string=>typeof node==='string'?node:Array.isArray(node)?node.map(text).join(''):(node?.children??[]).map(text).join('');
const initial='## Action Items\n- 保留条件：如果客户确认，再发报价 (owner: 小王, due: 周五)\n- 待核对：准备样品 (owner: 小陈)\n- [x] 保存旧资料 (owner: 小王, due: 2026-11-12)\n- 小王说希望再讨论\n- 归档 (owner: 甲, owner: 乙)';
let markdown=initial,context='meeting-one',tree:ReactTestRenderer,copied:string[]=[],copyFail=false;
const toggle=(lineIndex:number,completed:boolean)=>{const changed=markSavedAction(markdown,lineIndex,completed);assert.ok(changed);markdown=changed;};
function View(){
 const actions=savedActions(markdown),review=useActionReview(actions.map(a=>savedActionReview(String(a.lineIndex),a.text,a.completed)),context);
 const visible=new Set(review.visible.map(a=>a.id));
 return <><ActionReviewTools key={context} review={review} title="公开会议" onCopy={async value=>{if(copyFail)throw Error('test clipboard failure');copied.push(value);}}/>
  {actions.filter(a=>visible.has(String(a.lineIndex))).map(a=><button type="button" data-row={a.lineIndex} key={a.lineIndex} onClick={()=>toggle(a.lineIndex,!a.completed)}>{a.text}</button>)}</>;
}
const button=(label:string)=>tree.root.findAllByType('button').find(n=>text(n)===label)!;
const select=(label:string,value:string)=>act(()=>tree.root.findAllByType('select').find(n=>n.props['aria-label']===label)!.props.onChange({target:{value}}));
const update=()=>act(()=>tree.update(<View/>));
act(()=>{tree=create(<View/>);});
assert.match(text(tree.toJSON()),/显示 5 \/ 5 项/);
select('筛选负责人','小王');assert.deepEqual(tree.root.findAllByProps({'data-row':1}).map(n=>n.props['data-row']),[1]);
assert.equal(tree.root.findAll(n=>n.type==='button'&&n.props['data-row']!==undefined).length,2);
select('筛选完成状态','open');assert.equal(tree.root.findAll(n=>n.type==='button'&&n.props['data-row']!==undefined).length,1);
act(()=>button('整理当前事项为跟进草稿').props.onClick());
let draft=tree.root.findByType('textarea').props.value as string;
assert.match(draft,/保留条件：如果客户确认，再发报价/);assert.match(draft,/负责人：小王；时间：周五/);
assert.ok(!draft.includes('保存旧资料')&&!draft.includes('准备样品'));
await act(async()=>{await button('复制跟进文字').props.onClick();});assert.equal(copied[0],draft);
assert.match(text(tree.toJSON()),/尚未发送/);assert.equal(markdown,initial,'filter and draft are read-only');
select('筛选负责人','');select('筛选待补信息','owner');
assert.equal(tree.root.findAll(n=>n.type==='button'&&n.props['data-row']!==undefined).length,2,'prose and duplicate/unknown metadata never invent an owner');
assert.ok(!text(tree.toJSON()).includes('当前筛选事项的跟进文字已复制'),'old clipboard success is bound to its source selection');
act(()=>button('清除筛选').props.onClick());select('筛选待补信息','review');
draft=tree.root.findByType('textarea').props.value;
assert.match(draft,/待核对事项/);assert.match(draft,/准备样品/);assert.match(draft,/时间：未明确/);assert.ok(!draft.includes('保留条件：'));
const pending=savedActions(markdown)[1];act(()=>tree.root.findByProps({'data-row':pending.lineIndex}).props.onClick());update();
assert.ok(markdown.includes('- [x] 待核对：准备样品 (owner: 小陈)'));
assert.equal(savedActions(markdown)[1].lineIndex,pending.lineIndex,'saved identity survives filtering');
draft=tree.root.findByType('textarea').props.value;assert.match(draft,/已标记完成/);assert.match(draft,/此项仍保留待核对标记/);
select('筛选完成状态','open');assert.equal(tree.root.findAll(n=>n.type==='button'&&n.props['data-row']!==undefined).length,0);
assert.equal(button('复制跟进文字').props.disabled,true);assert.match(text(tree.toJSON()),/全部 5 项仍保留/);
context='meeting-two';markdown='## Action Items\n- 新会议的一项';update();assert.match(text(tree.toJSON()),/显示 1 \/ 1 项/);
act(()=>button('整理当前事项为跟进草稿').props.onClick());copyFail=true;
await act(async()=>{await button('复制跟进文字').props.onClick();});assert.match(text(tree.toJSON()),/test clipboard failure/);assert.equal(copied.length,1);
act(()=>tree.unmount());

const targets:any[]=[],finds:any[]=[];const mobileText='- 第一项 (owner: 甲)\n- 待核对：第二项\n- 第三项 (owner: 乙, due: 明天下午)';
function Mobile(){return <MobileActionCards contextKey={context} text={mobileText} fallback="fallback" itemOffset={7} sectionOccurrence={2} onToggle={(target,completed)=>targets.push({target,completed})} onFind={(target,body)=>finds.push({target,body})}/>;}
act(()=>{tree=create(<Mobile/>);});select('筛选负责人','乙');
assert.equal(tree.root.findAll(n=>n.props.className==='mobile-action-card').length,1);
act(()=>tree.root.findAllByType('input').find(node=>node.props.type==='checkbox')!.props.onChange({target:{checked:true}}));
assert.deepEqual(targets[0],{target:{sectionTitle:'Action Items',sectionOccurrence:2,itemIndex:9,original:'第三项 (owner: 乙, due: 明天下午)'},completed:true});
act(()=>button('查找原文核对').props.onClick());assert.equal(finds[0].target.itemIndex,9);assert.equal(finds[0].body,'第三项');
assert.equal(mobileText,'- 第一项 (owner: 甲)\n- 待核对：第二项\n- 第三项 (owner: 乙, due: 明天下午)');
act(()=>tree.unmount());

const publicSource=publicActions.actionItems.map(item=>'- '+item.text).join('\n');
act(()=>{tree=create(<MinutesDocument markdown={'## Action Items\n'+publicSource} renderText={(value,section,position)=>section==='Action Items'?<MobileActionCards contextKey="actual-public-phone" recordingTitle="S_R004S03C01" text={value} itemOffset={position?.itemOffset} fallback="fallback"/>:value}/>);});
assert.equal(tree.root.findAllByProps({'aria-label':'事项筛选与跟进'}).length,1,'A long saved list must share one complete filter scope across its folded cards');
assert.equal(tree.root.findAll(n=>n.type==='details'&&n.props.className==='minutes-more mobile-action-more').length,1,'Default reading remains folded without splitting action identity or filter scope');
assert.match(text(tree.toJSON()),/显示 21 \/ 21 项 · 20 项待核对/);
select('筛选待补信息','review');act(()=>button('整理当前事项为跟进草稿').props.onClick());
draft=tree.root.findByType('textarea').props.value;assert.ok(draft.includes('待核对事项')&&!draft.includes('\n\n待跟进\n'));
assert.equal(tree.root.findAll(n=>n.props.className==='mobile-action-card').length,20);
assert.equal(tree.root.findAll(n=>n.type==='details'&&n.props.className==='minutes-more mobile-action-more').length,0,'All filtered matches must be visible, including the original folded remainder');
assert.deepEqual(publicActions.actionItems.map(item=>item.text),publicSource.split('\n').map(line=>line.slice(2)));
act(()=>tree.unmount());
console.log('PASS saved-action filters and followup: exact identities after hidden rows, completion persistence roundtrip, owner/missing/date/review scope, source-bound copy success/failure, record switch reset, native mobile target preservation and all21actual public phone items. No model, external send or source mutation.');

import assert from 'node:assert/strict';
import React from 'react';
import {act,create,type ReactTestRenderer} from 'react-test-renderer';
import {readingOrder,notePreview,noteTimestamp} from '../packages/ui/src/noteReading';
import {ReadableNoteBody} from '../packages/ui/src/ReadableNoteBody';

const notes=[{id:'earlier',createdAt:'2026-11-01T00:00:00Z',updatedAt:'2026-11-02T00:00:00Z'},{id:'edited',createdAt:1,updatedAt:'2026-11-11T00:00:00Z'},{id:'unknown',createdAt:'unknown',updatedAt:'unknown'}],before=JSON.stringify(notes);
assert.deepEqual(readingOrder(notes).map(n=>n.id),['edited','earlier','unknown']);assert.deepEqual(readingOrder(notes,'created').map(n=>n.id),['edited','earlier','unknown']);assert.equal(JSON.stringify(notes),before);
assert.equal(noteTimestamp('1794331000000'),1794331000000,'Windows persists Unix milliseconds as decimal strings');assert.equal(noteTimestamp('1'),1);assert.equal(noteTimestamp('-1'),0);assert.equal(noteTimestamp('1.5'),0);
assert.deepEqual(readingOrder([{id:'native-old',createdAt:'1794330000000',updatedAt:'1794331000000'},{id:'native-new',createdAt:'1794332000000',updatedAt:'1794332000000'}]).map(n=>n.id),['native-new','native-old']);
const tied=[{id:'z',createdAt:1},{id:'a',createdAt:1}];assert.deepEqual(readingOrder(tied).map(n=>n.id),['z','a'],'Equal and unknown timestamps keep stable source order');
assert.equal(notePreview('一\n二\n三\n四\n五'),'一\n二\n三\n四');assert.equal(Array.from(notePreview('🙂'.repeat(300))).length,260);assert(!notePreview('🙂'.repeat(300)).includes('\ufffd'));
const body='人工安排\n'+('仅作为人工补充，不代表会议决定。'.repeat(35))+'\n原文末尾：必须完整保留';
let tree:ReactTestRenderer;const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
act(()=>{tree=create(<ReadableNoteBody text={body} className="fixture-body"/>);});assert(!text(tree!.toJSON()).includes('必须完整保留'));assert.equal(tree!.root.findByType('button').props['aria-expanded'],false);
act(()=>tree!.root.findByType('button').props.onClick());assert.equal(text(tree!.root.findByType('p')),body);assert.equal(tree!.root.findByType('button').props['aria-expanded'],true);
act(()=>tree!.root.findByType('button').props.onClick());assert(!text(tree!.toJSON()).includes('必须完整保留'));
act(()=>tree!.update(<ReadableNoteBody text={body} className="fixture-body" forceExpanded/>));assert.equal(text(tree!.root.findByType('p')),body);assert.equal(tree!.root.findAllByType('button').length,0,'Search matches cannot be hidden by an earlier collapse choice');assert(text(tree!.toJSON()).includes('搜索命中'));
act(()=>tree!.unmount());console.log('PASS stable source-preserving recent/created views, Unicode and paragraph preview, reversible full text and forced complete search targets.');

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {DocumentArchive,resolvePart} from '../packages/document-context/src/archive';
import {parseDocumentXml,attribute} from '../packages/document-context/src/xml';
import {DocumentReadError} from '../packages/document-context/src/types';
const root=process.argv[2];assert(root);const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
const input=new Uint8Array(fs.readFileSync(path.join(root,manifest.valid))),original=Buffer.from(input),archive=new DocumentArchive(input);
assert(archive.has('word/document.xml'));assert(!archive.has('word/'));assert.equal(new TextDecoder().decode(archive.read('word/document.xml')),manifest.text);assert.deepEqual(Buffer.from(input),original,'Reader altered original source bytes');
let text='',inside=false;parseDocumentXml(archive.read('word/document.xml'),{open:tag=>{if(tag.local==='t')inside=true;},close:tag=>{if(tag.local==='t')inside=false;},text:value=>{if(inside)text+=value;}});assert.equal(text,'公开资料：周二核对12000元预算。');
for(const name of manifest.invalid){assert.throws(()=>{const bad=new DocumentArchive(new Uint8Array(fs.readFileSync(path.join(root,name+'.zip'))));if(bad.has('word/document.xml'))bad.read('word/document.xml');},DocumentReadError,name+' must reject without partial extracted text');}
assert.equal(resolvePart('ppt/presentation.xml','slides/slide2.xml'),'ppt/slides/slide2.xml');assert.equal(resolvePart('xl/workbook.xml','/xl/worksheets/sheet1.xml'),'xl/worksheets/sheet1.xml');assert.throws(()=>resolvePart('word/document.xml','../../outside.xml'),DocumentReadError);
assert.throws(()=>parseDocumentXml(new TextEncoder().encode('<!DOCTYPE a [<!ENTITY b "x">]><a>&b;</a>'),{}),DocumentReadError);
assert.throws(()=>parseDocumentXml(new TextEncoder().encode('<a><b></a>'),{}),DocumentReadError);
let id='';parseDocumentXml(new TextEncoder().encode('<r:root xmlns:r="urn:root" xmlns:q="urn:id" q:id="public"/>'),{open:tag=>{id=attribute(tag,'id','urn:id')||'';}});assert.equal(id,'public');
console.log('PASS independent ZIP directory/CRC/false-size/traversal/alias fixtures, namespace XML, entity rejection and unchanged originals. Parser source only; no app delivery claimed.');

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {extractDocument} from '../packages/document-context/src/extract';
import {documentHtmlText} from '../packages/document-context/src/htmlText';
import {DocumentReadError} from '../packages/document-context/src/types';
const root=process.argv[2];assert(root);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
async function read(name:string,encoding?:'gb18030'){
 const bytes=fs.readFileSync(path.join(root,name)),original=Buffer.from(bytes);
 const result=await extractDocument(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),name,manifest[name].sha256,{encoding});
 assert.deepEqual(bytes,original);assert.equal(result.sourceSha256,manifest[name].sha256);return result;
}
const word=await read('material.docx'),wordText=word.sections.map(s=>s.text).join('\n');
for(const text of ['公开采购讨论补充材料','12000元','工程需求','待收集','虚构材料页眉','附注：人工提供，不是会议结论。'])assert(wordText.includes(text),'Word missing '+text);
fs.writeFileSync(path.join(root,'material.docx.extraction.json'),JSON.stringify(word));
const sheet=await read('material.xlsx'),sheetText=sheet.sections.map(s=>s.text).join('\n');
for(const text of ['12,000.00','FALSE','0','2026-11-10','公式没有已保存结果','XFD1048576: 稀疏末尾单元格'])assert(sheetText.includes(text),'Sheet missing '+text);
assert(!sheetText.includes('隐藏内容不能悄悄使用'));assert(sheet.warnings.some(w=>w.includes('隐藏')));
const slides=await read('material.pptx');assert.equal(slides.sections.length,2);assert(slides.sections[0].text.includes('第一张'));assert(slides.sections[1].text.includes('第二张'));assert(!JSON.stringify(slides.sections).includes('隐藏幻灯片内容'));assert(!JSON.stringify(slides.sections).includes('演讲者备注不属于正文'));
const plain=await read('material.txt');assert.equal(plain.sections[0].text,'  人工材料，保留空白。\n不是会议转写。\n');
assert.deepEqual((await read('material-utf16.txt')).sections,plain.sections);assert.deepEqual((await read('material-gb.txt','gb18030')).sections,plain.sections);
await assert.rejects(()=>extractDocument(new TextEncoder().encode('wrong').buffer,'wrong.txt','0'.repeat(64)),DocumentReadError);
assert.match(documentHtmlText('<p>正文<script>bad()</script><style>bad</style></p><table><tr><td>甲</td><td>乙</td></tr></table>'),/^正文\n+甲\t乙\n+$/);
console.log('PASS independently produced DOCX notes/header/table, sparse XLSX format/formula/hidden, ordered PPTX, text encodings, source identity, safe text projection.');

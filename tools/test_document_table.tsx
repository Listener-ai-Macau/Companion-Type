import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import React from 'react';
import {act,create,type ReactTestRenderer} from 'react-test-renderer';
import * as XLSX from 'xlsx';
import {strFromU8,strToU8,unzipSync,zipSync} from 'fflate';
import {DocumentArchive} from '../packages/document-context/src/archive';
import {readSpreadsheet} from '../packages/document-context/src/spreadsheet';
import {SectionCollector,type DocumentSection} from '../packages/document-context/src/types';
import {DocumentTable,verifiedDocumentTable} from '../packages/ui/src/DocumentTable';

const sheet:XLSX.WorkSheet={A1:{t:'s',v:'议题'},B1:{t:'s',v:'已确认？'},A2:{t:'s',v:'原文\tB2: 保留\n第二行 <img onerror=bad()>'},B2:{t:'b',v:false},C3:{t:'n',f:'SUM(C1:C2)'},'!ref':'A1:C3'};
const book=XLSX.utils.book_new();XLSX.utils.book_append_sheet(book,sheet,'讨论');
// The sparse OOXML leaf is real input. Do not ask a general fixture writer to
// visit every cell of Excel's entire coordinate range just to create it.
const parts=unzipSync(new Uint8Array(XLSX.write(book,{type:'array',bookType:'xlsx'})));
parts['xl/worksheets/sheet1.xml']=strToU8(strFromU8(parts['xl/worksheets/sheet1.xml']).replace('ref="A1:C3"','ref="A1:XFD1048576"').replace('</sheetData>','<row r="1048576"><c r="XFD1048576" t="inlineStr"><is><t>边界单元格</t></is></c></row></sheetData>'));
const original=zipSync(parts),collector=new SectionCollector();
readSpreadsheet(new DocumentArchive(original),collector,{});
const saved=JSON.parse(JSON.stringify(collector.finish('xlsx',createHash('sha256').update(original).digest('hex')))),section=saved.sections[0] as DocumentSection;
if(process.argv[2]){mkdirSync(process.argv[2],{recursive:true});writeFileSync(join(process.argv[2],'table.xlsx'),original);writeFileSync(join(process.argv[2],'table.extraction.json'),JSON.stringify(saved));}
const rows=verifiedDocumentTable(section)!;assert(rows);assert.equal(rows.length,4);assert.equal(rows[1].cells[0].text,sheet.A2.v);
assert.equal(rows[1].cells[1].text,'FALSE','Never turn saved false into an empty/true value');
assert.equal(rows[2].cells[0].text,'[公式没有已保存结果]');assert.equal(rows[3].row,1048576);assert.equal(rows[3].cells[0].column,'XFD');
assert.equal(verifiedDocumentTable({...section,tableRows:undefined}),null,'Legacy text is not reinterpreted as table cells');
assert.equal(verifiedDocumentTable({...section,tableRows:[{row:1,cells:[{column:'A',text:'changed'}]}]}),null);
assert.equal(verifiedDocumentTable({...section,tableRows:[rows[0],rows[0]]}),null,'Duplicate or reordered source positions are refused');
const large=new SectionCollector(),longCell='中'.repeat(270000);large.add('大表','A1: '+longCell);large.sections[0].tableRows=[{row:1,cells:[{column:'A',text:longCell}]}];
const bounded=large.finish('xlsx','b'.repeat(64));assert.equal(bounded.sections[0].text,'A1: '+longCell);assert.equal(bounded.sections[0].tableRows,undefined,'Optional layout must not block saving all source text');assert(bounded.warnings.some(w=>w.includes('布局')));
let tree:ReactTestRenderer;const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
act(()=>{tree=create(<DocumentTable section={section} query="" highlight={v=>v}/>);});
assert.equal(tree!.root.findAllByType('td').length,16,'Sparse last-column data must not allocate every intervening cell');
assert.equal(tree!.root.findAllByType('img').length,0);assert(text(tree!.toJSON()).includes(sheet.A2.v));
act(()=>tree!.update(<DocumentTable section={section} query="边界" highlight={v=>v}/>));assert.equal(tree!.root.findAllByType('td').length,1);assert(text(tree!.toJSON()).includes('1048576'));
const many:DocumentSection={id:'part-2',label:'长表',text:'',tableRows:Array.from({length:61},(_,i)=>({row:i+1,cells:[{column:'A',text:'value'+(i+1)}]}))};many.text=many.tableRows!.map(row=>'A'+row.row+': '+row.cells[0].text).join('\n');
act(()=>tree!.update(<DocumentTable section={many} query="" highlight={v=>v}/>));assert.equal(tree!.root.findAllByType('td').length,25);
const button=(label:string)=>tree!.root.findAllByType('button').find(n=>text(n)===label)!;
act(()=>button('下一组行').props.onClick());assert.equal(tree!.root.findAllByType('td').length,25);assert(text(tree!.toJSON()).includes('value26'));assert(!text(tree!.toJSON()).includes('value1'));
act(()=>button('原始文字').props.onClick());assert.equal(tree!.root.findByType('pre').children.join(''),many.text);
act(()=>tree!.unmount());
console.log('PASS real XLSX saved layout, multiline/tab/false/formula preservation, sparse maximum coordinates, legacy/corrupt fallback, literal rendering, search, bounded paging and exact original text.');

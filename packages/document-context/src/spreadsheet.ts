import * as XLSX from 'xlsx';
import {DocumentArchive} from './archive';
import {checkedOfficeInput,mainPart} from './officePackage';
import {SectionCollector,DOCUMENT_LIMITS,capacity,checkpoint,type DocumentReadOptions} from './types';

export function readSpreadsheet(archive:DocumentArchive,collector:SectionCollector,options:DocumentReadOptions){
 mainPart(archive,'xlsx');const input=checkedOfficeInput(archive);checkpoint(options);
 // SheetJS otherwise drops formulas whose saved result is absent. A stub's
 // synthetic v=0 is not a cached formula result and must never become a fact.
 const book=XLSX.read(input,{type:'array',dense:false,sheetStubs:true,cellText:true,cellFormula:true,cellNF:true,cellHTML:false,cellStyles:true,bookVBA:false,bookDeps:false,WTF:true});let cells=0,uncalculated=0;
 for(let sheetIndex=0;sheetIndex<book.SheetNames.length;sheetIndex++){
  checkpoint(options);if(book.Workbook?.Sheets?.[sheetIndex]?.Hidden){collector.warnings.add('隐藏工作表没有纳入提取文字。');continue;}
  const name=book.SheetNames[sheetIndex],sheet=book.Sheets[name],rows=new Map<number,Array<{column:number;address:string;cell:XLSX.CellObject}>>();
  for(const [address,cell] of Object.entries(sheet)){
   if(address.startsWith('!'))continue;if(!/^[A-Z]{1,3}[1-9][0-9]{0,6}$/.test(address))continue;
   if(++cells>DOCUMENT_LIMITS.spreadsheetCells)capacity();const location=XLSX.utils.decode_cell(address);if(location.r>1048575||location.c>16383)capacity();
   const values=rows.get(location.r)??[];values.push({column:location.c,address,cell});rows.set(location.r,values);if(rows.size>DOCUMENT_LIMITS.spreadsheetRows)capacity();
  }
  const lines:string[]=[];let characters=0;
  for(const row of [...rows.keys()].sort((a,b)=>a-b)){
   checkpoint(options);const values:string[]=[];
   for(const {address,cell} of rows.get(row)!.sort((a,b)=>a.column-b.column)){
    let value:string;
    if(cell.f&&(cell.t==='z'||cell.v===undefined||cell.v===null)){uncalculated++;value='[公式没有已保存结果]';}else value=String(cell.w??XLSX.utils.format_cell(cell)??'');
    if(value){const text=address+': '+value;characters+=text.length;if(collector.characters+characters>DOCUMENT_LIMITS.textCharacters)capacity();values.push(text);}
   }
   if(values.length)lines.push(values.join('\t'));
  }
  collector.add('工作表：'+name,lines.join('\n'));
 }
 if(uncalculated)collector.warnings.add('有 '+uncalculated+' 处公式没有已保存结果；本次没有运行或重算公式。');
 if(archive.names().some(name=>/\/(?:drawings|charts|media)\//.test(name)))collector.warnings.add('图片和图表仍在原件中，文字提取不包含其视觉内容。');
 collector.warnings.add('单元格使用原件保存的值和显示格式；公式、外部链接与宏不会运行。');
}

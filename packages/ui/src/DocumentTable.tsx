import {useEffect,useMemo,useState,type ReactNode} from 'react';
import type {DocumentSection,DocumentTableRow} from '../../document-context/src/types';

function columnNumber(name:string){let n=0;for(const c of name)n=n*26+c.charCodeAt(0)-64;return n;}

/** Saved layouts must exactly reproduce the preserved, cited cell text. Older
 * extractions keep their plain text; coordinates are never guessed from it. */
export function verifiedDocumentTable(section:DocumentSection):DocumentTableRow[]|null{
 const rows=section.tableRows;if(!Array.isArray(rows)||!rows.length||rows.length>10000)return null;
 let previousRow=0,cells=0;const lines:string[]=[];
 for(const row of rows){
  if(!row||!Number.isSafeInteger(row.row)||row.row<=previousRow||row.row>1048576||!Array.isArray(row.cells)||!row.cells.length)return null;
  previousRow=row.row;let previousColumn=0;const values:string[]=[];
  for(const cell of row.cells){
   if(!cell||typeof cell.column!=='string'||!(/^[A-Z]{1,3}$/).test(cell.column)||typeof cell.text!=='string'||!cell.text)return null;
   const column=columnNumber(cell.column);if(column<=previousColumn||column>16384||++cells>100000)return null;
   previousColumn=column;values.push(cell.column+row.row+': '+cell.text);
  }
  lines.push(values.join('\t'));
 }
 return lines.join('\n')===section.text?rows:null;
}

export function DocumentTable({section,query,highlight,onQuoteRow,quoteDisabled=false}:{section:DocumentSection;query:string;highlight:(text:string)=>ReactNode;onQuoteRow?:(row:DocumentTableRow)=>void;quoteDisabled?:boolean}){
 const rows=useMemo(()=>verifiedDocumentTable(section),[section]);
 const term=query.trim().toLocaleLowerCase();
 const matches=useMemo(()=>rows?.filter(row=>row.cells.some(cell=>(cell.column+row.row+': '+cell.text).toLocaleLowerCase().includes(term)))??[],[rows,term]);
 const visibleRows=term&&matches.length?matches:rows??[];
 const columns=useMemo(()=>[...new Set(visibleRows.flatMap(row=>row.cells.map(cell=>cell.column)))].sort((a,b)=>columnNumber(a)-columnNumber(b)),[visibleRows]);
 const [rowPage,setRowPage]=useState(0),[columnPage,setColumnPage]=useState(0),[plain,setPlain]=useState(false);
 useEffect(()=>{setRowPage(0);setColumnPage(0);},[section,term]);
 const rowPages=Math.max(1,Math.ceil(visibleRows.length/25)),columnPages=Math.max(1,Math.ceil(columns.length/8));
 const currentRowPage=Math.min(rowPage,rowPages-1),currentColumnPage=Math.min(columnPage,columnPages-1);
 const shownRows=visibleRows.slice(currentRowPage*25,(currentRowPage+1)*25),shownColumns=columns.slice(currentColumnPage*8,(currentColumnPage+1)*8);
 if(!rows)return <><p className="document-table-help">这份已保存文字没有表格布局；重新提取后可按行列阅读。原文字和原件仍可查看。</p><pre>{highlight(section.text)}</pre></>;
 return <div className="document-table-reader">
  <div className="document-table-toolbar"><p>{term&&matches.length?'找到 '+matches.length+' 行':'共 '+rows.length+' 行'} · 按原单元格位置阅读</p><button type="button" aria-pressed={plain} onClick={()=>setPlain(value=>!value)}>{plain?'表格阅读':'原始文字'}</button></div>
  {plain?<pre>{highlight(section.text)}</pre>:<>
   <p className="document-table-help">只显示已提取内容的行列，行号和列名保持原位置；公式不会重新计算。</p>{shownColumns.length>2&&<p className="document-table-pan-hint">左右滑动可查看其余列</p>}<div className="document-table-scroll" tabIndex={0} aria-label={section.label+'表格，可横向滚动'}><table><caption>{section.label} · 原件保存的内容</caption><thead><tr><th scope="col">行</th>{shownColumns.map(column=><th scope="col" key={column}>{column}</th>)}</tr></thead><tbody>{shownRows.map(row=><tr key={row.row}><th scope="row">{row.row}{onQuoteRow&&<button className="manual-quote-action" type="button" disabled={quoteDisabled} aria-label={"引用第"+row.row+"行到备注"} onClick={()=>onQuoteRow(row)}>引用此行</button>}</th>{shownColumns.map(column=>{const cell=row.cells.find(cell=>cell.column===column);return <td key={column} title={column+row.row}>{cell?highlight(cell.text):<span className="document-table-empty" aria-label="没有提取文字">—</span>}</td>;})}</tr>)}</tbody></table></div>
   <div className="document-table-paging"><div><button type="button" disabled={currentRowPage===0} onClick={()=>setRowPage(currentRowPage-1)}>上一组行</button><span>行页 {currentRowPage+1} / {rowPages}</span><button type="button" disabled={currentRowPage+1>=rowPages} onClick={()=>setRowPage(currentRowPage+1)}>下一组行</button></div>{columnPages>1&&<div><button type="button" disabled={currentColumnPage===0} onClick={()=>setColumnPage(currentColumnPage-1)}>前面列</button><span>列页 {currentColumnPage+1} / {columnPages}</span><button type="button" disabled={currentColumnPage+1>=columnPages} onClick={()=>setColumnPage(currentColumnPage+1)}>后面列</button></div>}</div>
  </>}
 </div>;
}

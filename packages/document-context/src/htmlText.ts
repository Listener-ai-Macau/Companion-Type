import {Parser} from 'htmlparser2';
import {DOCUMENT_LIMITS,capacity} from './types';

/** Semantic HTML is projected to plain text without ever inserting a DOM or
 * following links/images. Table rows retain explicit cell separators.
 */
export function documentHtmlText(html:string):string {
 let output='',nodes=0,characters=0,hidden=0;const tables:Array<{rows:string[];row:string[];cell:string|null}>=[];
 const add=(text:string)=>{characters+=text.length;if(characters>DOCUMENT_LIMITS.textCharacters)capacity();const table=tables[tables.length-1];if(table?.cell!==null&&table?.cell!==undefined)table.cell+=text;else output+=text;};
 const parser=new Parser({
  onopentag(name){if(++nodes>DOCUMENT_LIMITS.xmlNodes)capacity();if(name==='script'||name==='style'){hidden++;return;}if(hidden)return;if(name==='table')tables.push({rows:[],row:[],cell:null});else if(name==='tr'&&tables.length)tables[tables.length-1].row=[];else if((name==='td'||name==='th')&&tables.length)tables[tables.length-1].cell='';else if(name==='br')add('\n');else if(name==='li')add('• ');},
  ontext(text){if(!hidden)add(text);},
  onclosetag(name){
   if(name==='script'||name==='style'){hidden=Math.max(0,hidden-1);return;}if(hidden)return;
   const table=tables[tables.length-1];
   if((name==='td'||name==='th')&&table){table.row.push((table.cell??'').replace(/\n+$/,''));table.cell=null;}
   else if(name==='tr'&&table)table.rows.push(table.row.join('\t'));
   else if(name==='table'&&table){tables.pop();const text=table.rows.join('\n')+'\n\n';const parent=tables[tables.length-1];if(parent&&parent.cell!==null)parent.cell+=text;else output+=text;}
   else if(/^(p|h[1-6]|li|blockquote)$/.test(name))add('\n\n');
  }
 },{decodeEntities:true});parser.end(html);return output;
}

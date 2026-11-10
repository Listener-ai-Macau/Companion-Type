import {Inflate} from 'fflate';
import {DOCUMENT_LIMITS,capacity,invalid} from './types';

const table=Uint32Array.from({length:256},(_,value)=>{for(let bit=0;bit<8;bit++)value=(value&1)?0xedb88320^(value>>>1):value>>>1;return value>>>0;});
function crc32(bytes:Uint8Array){let crc=0xffffffff;for(const byte of bytes)crc=table[(crc^byte)&255]^(crc>>>8);return (crc^0xffffffff)>>>0;}
type Entry={name:string;method:number;flags:number;crc:number;compressed:number;bytes:number;local:number;start:number;directory:boolean};

/** Read selected bounded ZIP members in memory. No paths are extracted to disk.
 * Check both directories, sizes, overlap and CRC. Inflate in small input chunks
 * so a false advertised size cannot allocate an unbounded complete output.
 */
export class DocumentArchive {
 private readonly entries=new Map<string,Entry>();private readonly view:DataView;
 constructor(private readonly source:Uint8Array){
  if(source.length<22||source.length>DOCUMENT_LIMITS.fileBytes)invalid('这不是可读取的现代Office文件，或文件容量过大。');
  this.view=new DataView(source.buffer,source.byteOffset,source.byteLength);let end=-1;
  for(let offset=source.length-22;offset>=Math.max(0,source.length-65557);offset--){if(this.u32(offset)===0x06054b50&&offset+22+this.u16(offset+20)===source.length){end=offset;break;}}
  if(end<0)invalid('文件目录不完整，请重新保存原件后导入。');
  const count=this.u16(end+10),directoryBytes=this.u32(end+12),directoryAt=this.u32(end+16);
  if(this.u16(end+4)!==0||this.u16(end+6)!==0||this.u16(end+8)!==count||count===65535)invalid('暂不支持分卷或ZIP64文档，请另存为普通Office文件。');
  if(!count||count>DOCUMENT_LIMITS.zipEntries)capacity();
  if(directoryAt+directoryBytes>end||directoryAt>=end)invalid();
  let cursor=directoryAt,total=0;const intervals:Array<[number,number]>=[];
  for(let index=0;index<count;index++){
   if(cursor+46>directoryAt+directoryBytes||this.u32(cursor)!==0x02014b50)invalid();
   const flags=this.u16(cursor+8),method=this.u16(cursor+10),crc=this.u32(cursor+16),compressed=this.u32(cursor+20),bytes=this.u32(cursor+24),nameBytes=this.u16(cursor+28),extra=this.u16(cursor+30),comment=this.u16(cursor+32),local=this.u32(cursor+42),attributes=this.u32(cursor+38);
   if(cursor+46+nameBytes+extra+comment>directoryAt+directoryBytes||this.u16(cursor+34)!==0)invalid();
   let name:string;try{name=new TextDecoder('utf-8',{fatal:true}).decode(source.subarray(cursor+46,cursor+46+nameBytes));}catch{invalid('文档内部名称编码无法确认，请另存后导入。');}
   const directory=name.endsWith('/'),parts=(directory?name.slice(0,-1):name).split('/');
   if(!name||name.length>512||/[\x00-\x1f\x7f\\:]/.test(name)||parts.some(part=>!part||part==='.'||part==='..')||this.entries.has(name))invalid('文档内部目录重复或无效，原件仍保留。');
   const fileType=(attributes>>>16)&0xf000;if(fileType!==0&&fileType!==0x8000&&!(directory&&fileType===0x4000))invalid('文档包含非常规文件，原件仍保留。');
   if(flags&1)invalid('文档内容已加密，请使用有权读取的未加密副本。');
   if(method!==0&&method!==8)invalid('文档使用了暂不支持的压缩方式，请另存后导入。');
   total+=bytes;if(bytes>DOCUMENT_LIMITS.partBytes||total>DOCUMENT_LIMITS.archiveBytes||compressed===0xffffffff||bytes===0xffffffff)capacity();
   if(local+30>directoryAt||this.u32(local)!==0x04034b50||this.u16(local+6)!==flags||this.u16(local+8)!==method)invalid();
   const localNameBytes=this.u16(local+26),localExtra=this.u16(local+28),start=local+30+localNameBytes+localExtra;
   if(localNameBytes!==nameBytes||start+compressed>directoryAt||start<local)invalid();
   const localName=source.subarray(local+30,local+30+localNameBytes),centralName=source.subarray(cursor+46,cursor+46+nameBytes);if(localName.some((value,i)=>value!==centralName[i]))invalid();
   if(!(flags&8)&&(this.u32(local+14)!==crc||this.u32(local+18)!==compressed||this.u32(local+22)!==bytes))invalid();
   if(directory&&bytes!==0)invalid();
   intervals.push([local,start+compressed]);this.entries.set(name,{name,method,flags,crc,compressed,bytes,local,start,directory});cursor+=46+nameBytes+extra+comment;
  }
  if(cursor!==directoryAt+directoryBytes)invalid();
  intervals.sort((a,b)=>a[0]-b[0]);for(let index=1;index<intervals.length;index++)if(intervals[index][0]<intervals[index-1][1])invalid('文档内部数据重叠，请检查原件。');
 }
 private u16(offset:number){if(offset<0||offset+2>this.source.length)invalid();return this.view.getUint16(offset,true);}
 private u32(offset:number){if(offset<0||offset+4>this.source.length)invalid();return this.view.getUint32(offset,true);}
 has(name:string){return this.entries.has(name)&&!this.entries.get(name)!.directory;}
 names(){return [...this.entries.values()].filter(entry=>!entry.directory).map(entry=>entry.name);}
 read(name:string):Uint8Array {
  const entry=this.entries.get(name);if(!entry||entry.directory)invalid('文档缺少必要内容，请检查原件。');
  const result=new Uint8Array(entry.bytes);let offset=0;
  if(entry.method===0){if(entry.compressed!==entry.bytes)invalid();result.set(this.source.subarray(entry.start,entry.start+entry.compressed));offset=entry.bytes;}
  else{
   try{const stream=new Inflate((chunk)=>{if(offset+chunk.length>entry.bytes)invalid('文档解压容量与目录不符，已停止读取。');result.set(chunk,offset);offset+=chunk.length;});
    if(!entry.compressed)stream.push(new Uint8Array(),true);
    for(let at=0;at<entry.compressed;at+=1024){const stop=Math.min(entry.compressed,at+1024);stream.push(this.source.subarray(entry.start+at,entry.start+stop),stop===entry.compressed);}
   }catch(error){if(error instanceof Error&&error.name==='DocumentReadError')throw error;invalid('文档压缩内容不完整，请检查原件。');}
  }
  if(offset!==entry.bytes||crc32(result)!==entry.crc)invalid('文档内容校验失败，原件仍保留。');return result;
 }
}

export function resolvePart(base:string,target:string):string {
 if(!target||/[\x00-\x1f\\:?#]/.test(target))invalid('文档引用的内部资料位置无效。');
 const parts=target.startsWith('/')?[]:base.split('/').slice(0,-1);
 for(const part of target.split('/')){if(!part||part==='.')continue;if(part==='..'){if(!parts.length)invalid('文档引用越界，已停止读取。');parts.pop();}else parts.push(part);}
 return parts.join('/');
}

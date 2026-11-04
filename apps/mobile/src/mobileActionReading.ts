import {nativeActionParts} from '../../../packages/ui/src/actionMetadata';
export function mobileActionCards(text:string){
 const lines=text.split(/\r?\n/).filter(line=>line.trim());
 if(lines.some(line=>!/^[-*+]\s+\S/.test(line)))return null;
 return lines.flatMap(line=>{
  const original=line.replace(/^[-*+]\s+/,'');
  if(/^None captured[.。]?$/i.test(original))return [];
  const checked=/^\[x\]\s+/i.test(original);const value=original.replace(/^\[[ xX]\]\s+/,'');
  const parsed=nativeActionParts(value);const pending=/^待核对[：:]\s*/.test(parsed.body);
  return [{original,body:pending?parsed.body.replace(/^待核对[：:]\s*/,''):parsed.body,
   owner:parsed.metadata.find(field=>field.key==='owner')?.value??null,
   due:parsed.metadata.find(field=>field.key==='due')?.value??null,checked,pending}];
 });
}

export type ActionMetadata = {key:'owner'|'due';value:string};

// Only a complete, known native suffix is metadata. Unknown/duplicate keys
// remain literal prose, shared by reading, editing and source navigation.
export function nativeActionParts(value:string):{body:string;metadata:ActionMetadata[]}{
  const suffix=value.match(/\s+\(([^()\r\n]+)\)$/);
  if(suffix&&suffix.index!=null){
    const fields=suffix[1].split(/,\s*(?=[A-Za-z_][A-Za-z_ -]*:\s*)/);
    const parsed=fields.map(field=>field.match(/^(owner|due):\s*(\S[\s\S]*)$/));
    if(parsed.every(Boolean)&&new Set(parsed.map(field=>field![1])).size===fields.length){
      return {body:value.slice(0,suffix.index),metadata:parsed.map(field=>({
        key:field![1] as ActionMetadata['key'],value:field![2]}))};
    }
  }
  return {body:value,metadata:[]};
}

// An exact duplicate leading time can be shown in its own field. No calendar
// inference or fuzzy date matching; unchanged rows still serialize verbatim.
export function actionTaskBody(body:string,metadata:readonly ActionMetadata[]):string{
  const due=metadata.find(field=>field.key==='due')?.value.trim();
  if(!due||!body.startsWith(due))return body;
  const rest=body.slice(due.length).trimStart();
  // Keep temporal qualifiers/ranges attached to their original sentence.
  if(!rest||/^(?:前|后|之|以|左右|起|内|至|到|[—\-～~\/])/u.test(rest))return body;
  return rest;
}

export function actionReadingParts(value:string){
  const {body,metadata}=nativeActionParts(value),title=actionTaskBody(body,metadata);
  return {title,metadata:metadata.filter(field=>title!==body||!body.includes(field.value))};
}

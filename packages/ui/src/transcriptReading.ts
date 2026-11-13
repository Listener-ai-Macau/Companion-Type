/** Reversible reading projection. Never changes recognition, edits or source anchors. */
export function cleanHesitations(text:string):{text:string;removed:number} {
 // Quoted words, short answers and questions are evidence too. Only long
 // spoken clauses are cleaned; discourse words such as “就是/那个/然后”
 // are not stop words and must never be deleted wholesale.
 const pieces=text.split(/(“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*")/u);
 const clean=pieces.map(piece=>{
  if(/^[“「『"]/.test(piece))return piece;
  return (piece.match(/[^。！？!?\n]+[。！？!?\n]?|[。！？!?\n]/gu)??[]).map(clause=>{
   if(clause.replace(/[\s，,、。！？!?：:；;]/g,'').length<=4)return clause;
   return clause
   .replace(/[呃]+[，,、]?\s*/gu,'')
   .replace(/嗯+[，,、]?\s*(?=[\p{Script=Han}A-Za-z0-9])/gu,'')
   .replace(/(?:这个){2,}|(?:那个){2,}|(?:就是){2,}|(?:然后){2,}/gu,word=>word.slice(0,2))
   .replace(/(^|[，,：:；;\s])([我你他她它])\2+(?=\p{Script=Han})/gu,'$1$2')
   .replace(/([，,、])(?:[，,、]\s*)+/gu,'$1');
  }).join('');
 }).join('');
 return {text:clean,removed:Array.from(text).length-Array.from(clean).length};
}

/** Add paragraph boundaries only after complete sentences, never inside a quote. */
export function transcriptParagraphs(text:string):string[] {
 const paragraphs:string[]=[];let current='',quoted=false;
 for(const char of text){
  current+=char;
  if('“「『'.includes(char))quoted=true;
  if('”」』'.includes(char))quoted=false;
  if(char==='\n'||(!quoted&&/[。！？!?]/u.test(char)&&current.length>=120)){
   if(current.trim())paragraphs.push(current.trim());current='';
  }
 }
 if(current.trim())paragraphs.push(current.trim());
 return paragraphs;
}

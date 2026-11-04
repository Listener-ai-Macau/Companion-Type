/** Display-only cleanup: never alters the saved recognition or user edits. */
export function cleanHesitations(text:string):{text:string;removed:number} {
 let removed=0;
 const clean=text.replace(/[嗯呃]+/g,match=>{removed+=Array.from(match).length;return '';});
 return {text:clean,removed};
}

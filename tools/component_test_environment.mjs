// Minimal non-visual DOM hooks for React component contracts. Source code,
// callbacks and state are real; this does not claim focus/layout/browser QA.
// Tests needing real DOM interaction use the installed/browser entry instead.
globalThis.document??={activeElement:null,querySelector:()=>null,getElementById:()=>null};
globalThis.window??={};
globalThis.window.matchMedia??=(media)=>({media,matches:false,onchange:null,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent(){return true;}});
globalThis.window.requestAnimationFrame??=(callback)=>{callback(0);return 0;};
globalThis.window.cancelAnimationFrame??=()=>{};
globalThis.window.setTimeout??=globalThis.setTimeout;
globalThis.window.clearTimeout??=globalThis.clearTimeout;
globalThis.HTMLButtonElement??=class HTMLButtonElement {};
globalThis.HTMLElement??=class HTMLElement {};

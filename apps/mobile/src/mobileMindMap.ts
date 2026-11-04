/** A local outline of the saved minutes; no content is generated or sent. */
export type MindMapNode={title:string;body:string[];children:MindMapNode[]};
export function minutesOutline(markdown:string):MindMapNode {
 const root:MindMapNode={title:'',body:[],children:[]};
 const stack:{level:number;node:MindMapNode}[]=[{level:0,node:root}];
 let fence:string|null=null;
 for(const line of markdown.split(/\r?\n/)){
  const marker=/^\s*(`{3,}|~{3,})/.exec(line);
  if(marker){const c=marker[1][0];if(!fence)fence=c;else if(fence===c)fence=null;stack[stack.length-1].node.body.push(line);continue;}
  const heading=!fence?/^\s{0,3}(#{1,6})\s+(.+?)\s*$/.exec(line):null;
  if(!heading){stack[stack.length-1].node.body.push(line);continue;}
  const level=heading[1].length;
  while(stack.length>1&&stack[stack.length-1].level>=level)stack.pop();
  const node:MindMapNode={title:heading[2],body:[],children:[]};
  stack[stack.length-1].node.children.push(node);stack.push({level,node});
 }
 return root;
}

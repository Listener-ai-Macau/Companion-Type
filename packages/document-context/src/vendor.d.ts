declare module 'mammoth/mammoth.browser.js' {
 const mammoth:{convertToHtml(input:{arrayBuffer:ArrayBuffer},options?:{externalFileAccess?:boolean;includeEmbeddedStyleMap?:boolean;includeDefaultStyleMap?:boolean;convertImage?:unknown}):Promise<{value:string;messages:Array<{type:string;message:string}>}>;images:{imgElement(callback:()=>Promise<{src:string}>):unknown}};
 export default mammoth;
}

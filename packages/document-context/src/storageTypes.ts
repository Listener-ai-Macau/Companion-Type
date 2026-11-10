import type {DocumentExtraction,DocumentFormat} from './types';
export type ContextDocument={id:string;name:string;format:DocumentFormat;bytes:number;sourceSha256:string;createdAt:number;extraction?:{characters:number;readerVersion:string;sha256:string;bytes:number}};
export type ContextDocuments={contextId:string;revision:number;libraryToken?:string;rows:ContextDocument[]};
export type DocumentContextAdapter={
 load:()=>Promise<ContextDocuments>;
 import:(value:ContextDocuments,id:string)=>Promise<ContextDocuments|{cancelled:true}>;
 chunk:(value:ContextDocuments,id:string,offset:number)=>Promise<{offset:number;base64:string;sourceSha256:string}>;
 read:(value:ContextDocuments,id:string)=>Promise<DocumentExtraction>;
 commit:(value:ContextDocuments,id:string,extraction:DocumentExtraction)=>Promise<ContextDocuments>;
 remove:(value:ContextDocuments,id:string)=>Promise<ContextDocuments>;
 saveOriginal:(value:ContextDocuments,id:string)=>Promise<boolean>;
};

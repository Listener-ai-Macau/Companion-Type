export interface CompanionLibraryOrganization {revision:number;folder:string;tags:string[];favorite:boolean}
export interface CompanionLibraryOrganizationRequest {
  targets:Array<{sessionId:string;expectedRevision:number}>;
  folder?:string;tags?:string[];tagAction?:'add'|'remove'|'replace';favorite?:boolean;
}
export const emptyLibraryOrganization=():CompanionLibraryOrganization=>({revision:0,folder:'',tags:[],favorite:false});
export interface CompanionLibraryExportRequest {
 targets:Array<{sessionId:string;expectedRevision:number}>;
 format:'audio'|'txt'|'json'|'markdown'|'srt';
 meetingMode?:'recorded'|'offlineStore'|'onlineLive';
}
export interface CompanionLibraryExportResult {path:string;sessions:number;files:number;bytes:number}

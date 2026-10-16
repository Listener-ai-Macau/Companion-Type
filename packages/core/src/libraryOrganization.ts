export interface CompanionLibraryOrganization {revision:number;folder:string;tags:string[];favorite:boolean}
export interface CompanionLibraryOrganizationRequest {
  targets:Array<{sessionId:string;expectedRevision:number}>;
  folder?:string;tags?:string[];tagAction?:'add'|'remove'|'replace';favorite?:boolean;
}
export const emptyLibraryOrganization=():CompanionLibraryOrganization=>({revision:0,folder:'',tags:[],favorite:false});

export type ShareDestination = 'system' | 'folder';
export type ShareHandoffResult = {status:string;fileName?:string|null;bytes:number};

/** The host confirms a request to Windows, never delivery to a recipient. */
export function shareHandoffMessage(result:ShareHandoffResult,destination:ShareDestination='system'):string {
  const name=result.fileName?`：${result.fileName}`:'';
  if(destination==='folder'){
    if(result.status!=='folderOpened')throw Error('分享文件夹未打开，请改用保存后分享。');
    return `分享副本已准备${name}。已请求Windows打开文件夹并选中文件；请点资源管理器中的“共享”，再选择接收应用。文件尚未发送。长期保留请使用“保存”。`;
  }
  if(result.status!=='opened')throw Error('分享面板未打开，请改用文件夹分享或保存。');
  return `已请求Windows打开分享面板${name}。请选择接收应用；是否发送以接收应用为准。若面板无法显示接收方式，可改用文件夹分享。`;
}

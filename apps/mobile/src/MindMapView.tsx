import {CircleAlert} from 'lucide-react';
import {MeetingMapView} from '../../../packages/ui/src/MeetingMapView';
type Props={title:string;markdown:string;stale:boolean;onExport:()=>void;busy:boolean};
export function MobileMindMap({title,markdown,stale,onExport,busy}:Props){
 return <div className="mindmap-view"><div className="mindmap-intro"><h2>思维导图</h2><button className="secondary" disabled={busy} onClick={onExport}>导出导图</button></div>{stale&&<p className="source-stale" role="status"><CircleAlert size={16} aria-hidden="true"/><span>转写已更改，导图依据较早的纪要，请核对内容。</span></p>}<MeetingMapView markdown={markdown} title={title}/></div>;
}

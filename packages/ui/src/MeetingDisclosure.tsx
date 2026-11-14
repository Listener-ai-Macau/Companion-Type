import type {ReactNode} from 'react';
import {ChevronDown} from 'lucide-react';
import './meetingDisclosure.css';

/** Native disclosure keeps the complete saved content mounted and keyboard-accessible. */
export function MeetingDisclosure({title,description,heading,className='',children}:{
 title:string;description?:string;heading?:string;className?:string;children:ReactNode;
}){
 return <details className={`meeting-disclosure ${className}`}>
  <summary data-meeting-heading={heading}>
   <span className="meeting-disclosure-label"><strong>{title}</strong>{description&&<small>{description}</small>}</span>
   <span className="meeting-disclosure-toggle" aria-hidden="true"><span className="meeting-disclosure-closed">展开</span><span className="meeting-disclosure-open">收起</span><ChevronDown size={15}/></span>
  </summary>
  <div className="meeting-disclosure-content">{children}</div>
 </details>;
}

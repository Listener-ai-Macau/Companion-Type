import type {ReactNode} from 'react';
import {AlignLeft,CheckCheck,ListChecks,MessageCircleQuestion,Users} from 'lucide-react';

/** A reading landmark only: the source title and its heading level stay intact. */
export function MeetingSectionHeading({as:Tag='h4',sourceTitle,children,className=''}:{as?:'h3'|'h4';sourceTitle:string;children:ReactNode;className?:string}){
 const Icon=/^(Decisions|决定|决策|结论|已定事项)$/.test(sourceTitle)?CheckCheck:
  /^(Action Items|行动事项|待办|后续行动)$/.test(sourceTitle)?ListChecks:
  /^(Questions|会中问题|待确认|待解问题)$/.test(sourceTitle)?MessageCircleQuestion:
  /发言|说话人/.test(sourceTitle)?Users:AlignLeft;
 return <Tag data-meeting-heading={sourceTitle} className={`meeting-section-heading ${className}`.trim()}><span className="meeting-section-icon" aria-hidden="true"><Icon size={17} strokeWidth={1.7}/></span><span>{children}</span></Tag>;
}

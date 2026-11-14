import type {ReactNode} from 'react';
import './overviewTopics.css';

/** An exact source prefix becomes a heading; no topic names or facts are generated. */
export function topicReadingParts(text:string):{title:string|null;body:string} {
 const match=/^(.{2,36}?)([：:，,；;（(])/u.exec(text);
 if(!match)return {title:null,body:text};
 const separator=/[：:，,；;]/u.test(match[2]);
 return {title:match[1],body:text.slice(match[1].length+(separator?1:0)).trim()};
}

/** Granola/Notta document pattern: visible topic heading and its actual notes. */
export function MeetingTopic({text,children}:{text:string;children?:ReactNode}) {
 const parts=topicReadingParts(text);
 return <section className="ct-overview-topic" data-meeting-topic={text}>
  {parts.title&&<h5 className="ct-overview-topic-title">{parts.title}</h5>}
  <div className="ct-overview-topic-body"><p>{parts.body}{children}</p></div>
 </section>;
}

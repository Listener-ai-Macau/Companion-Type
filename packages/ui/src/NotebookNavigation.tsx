import {Bluetooth,Headphones,Heart,Settings,Star} from 'lucide-react';

/** App navigation stays separate from a recording's reading and editing tools. */
export function NotebookNavigation({page,favorites,hasPet,onLibrary,onFavorites,onDevice,onPet,onSettings}:{
 page:string;favorites:boolean;hasPet:boolean;onLibrary:()=>void;onFavorites:()=>void;onDevice:()=>void;onPet:()=>void;onSettings:()=>void;
}){
 return <nav className="ct-app-navigation" aria-label="主要功能">
  <div className="ct-app-navigation-main">
   <button type="button" aria-current={page==='library'&&!favorites?'page':undefined} onClick={onLibrary}><Headphones size={17}/><span>录音</span></button>
   <button type="button" aria-current={page==='library'&&favorites?'page':undefined} onClick={onFavorites}><Star size={17}/><span>收藏</span></button>
   <button type="button" aria-current={page==='device'?'page':undefined} onClick={onDevice}><Bluetooth size={17}/><span>录音卡</span></button>
  </div>
  <div className="ct-app-navigation-other">
   {hasPet&&<button type="button" aria-current={page==='pet'?'page':undefined} onClick={onPet}><Heart size={17}/><span>宠物</span></button>}
   <button type="button" aria-current={page==='settings'?'page':undefined} onClick={onSettings}><Settings size={17}/><span>设置</span></button>
  </div>
 </nav>;
}

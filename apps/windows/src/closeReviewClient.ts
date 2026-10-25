import {invoke} from '@tauri-apps/api/core';
import {listen} from '@tauri-apps/api/event';
import type {CloseClient,CloseRequest} from './CloseReview';

export const nativeCloseReview:CloseClient={
  listen:receive=>listen<CloseRequest>('companion-close-review',event=>receive(event.payload)),
  register:()=>invoke('register_companion_close_review'),
  unregister:owner=>invoke('unregister_companion_close_review',{owner}),
  respond:(review,discard)=>invoke('respond_companion_close_review',{...review,discard}),
};

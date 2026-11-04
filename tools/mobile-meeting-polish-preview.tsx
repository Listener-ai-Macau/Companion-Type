// Mobile CSS is isolated from the desktop preview, just as in the real bundles.
import React from 'react';
import {createRoot} from 'react-dom/client';
import {App} from '../apps/mobile/src/App';
createRoot(document.getElementById('root')!).render(<App/>);

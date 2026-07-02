import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './app/App';
import './shared/styles/tokens.css';
import './shared/styles/global.css';

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('#root element is missing in index.html');
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// src/web/react/index.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import ChessBoard from './components/Chess/ChessBoard';

// Mount the React components when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Find all chess board mount points
  const mountPoints = document.querySelectorAll('#chess-mount-point');
  
  mountPoints.forEach(mountPoint => {
    try {
      // Get data from attributes
      const fen = mountPoint.getAttribute('data-fen');
      const pgn = mountPoint.getAttribute('data-pgn');
      const flip = mountPoint.getAttribute('data-flip') === 'true';
      
      // Create root and render component
      const root = createRoot(mountPoint);
      root.render(
        <ChessBoard fen={fen} pgn={pgn} flip={flip} />
      );
      
      console.log('Chess board mounted with FEN:', fen);
    } catch (error) {
      console.error('Error mounting chess board:', error);
      mountPoint.innerHTML = `<div class="error">Error mounting chess board: ${error.message}</div>`;
    }
  });
});

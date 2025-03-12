import React, { useState, useEffect } from 'react';

const ChessBoard = ({ fen, pgn, flip = false }) => {
  const [boardState, setBoardState] = useState({
    board: [], 
    turn: 'w'
  });
  const [showFEN, setShowFEN] = useState(false);
  
  // Parse FEN string and set up board
  useEffect(() => {
    if (fen) {
      try {
        const parsedBoard = parseFEN(fen);
        setBoardState(parsedBoard);
      } catch (error) {
        console.error('Error parsing FEN:', error);
        // Set up a default empty board as fallback
        setBoardState({
          board: Array(8).fill().map(() => Array(8).fill(null)),
          turn: 'w'
        });
      }
    }
  }, [fen]);
  
  // FEN parser function
  const parseFEN = (fenString) => {
    try {
      // FEN parts: position, active color, castling, en passant, halfmove, fullmove
      const parts = fenString.split(' ');
      const position = parts[0];
      const turn = parts.length > 1 ? parts[1] : 'w';
      
      // Parse position into 2D array
      const rows = position.split('/');
      const board = [];
      
      for (let i = 0; i < 8; i++) {
        const row = [];
        let j = 0;
        
        for (let c = 0; c < rows[i].length; c++) {
          const char = rows[i][c];
          if ('12345678'.includes(char)) {
            // Empty squares
            const emptyCount = parseInt(char, 10);
            for (let k = 0; k < emptyCount; k++) {
              row.push(null);
              j++;
            }
          } else {
            // Piece
            const color = char === char.toUpperCase() ? 'w' : 'b';
            const type = char.toLowerCase();
            row.push({ type, color });
            j++;
          }
        }
        
        board.push(row);
      }
      
      return { board, turn };
    } catch (error) {
      console.error('FEN parsing error:', error);
      throw error;
    }
  };
  
  // Helper to get Unicode chess piece
  const getPieceSymbol = (type) => {
    const symbols = {
      'p': '♟', // pawn
      'r': '♜', // rook
      'n': '♞', // knight
      'b': '♝', // bishop
      'q': '♛', // queen
      'k': '♚', // king
    };
    return symbols[type.toLowerCase()] || '';
  };
  
  // Render files (a-h) labels
  const renderFiles = () => {
    const files = flip ? 'hgfedcba' : 'abcdefgh';
    return (
      <div className="chess-labels">
        {files.split('').map((file, i) => (
          <div key={`file-${i}`} className="chess-label">{file}</div>
        ))}
      </div>
    );
  };
  
  // If board isn't ready yet, show loading state
  if (!boardState.board.length) {
    return <div className="chess-board">Loading board...</div>;
  }
  
  // Determine board orientation based on flip prop
  const ranks = flip ? [0, 1, 2, 3, 4, 5, 6, 7] : [7, 6, 5, 4, 3, 2, 1, 0];
  const files = flip ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
  const rankLabels = flip ? '12345678' : '87654321';
  
  return (
    <div className="chess-board">
      {renderFiles()}
      
      {ranks.map((rankIndex, i) => (
        <div key={`rank-${rankIndex}`} className="chess-rank">
          {/* Rank label */}
          <div className="chess-label">{rankLabels[i]}</div>
          
          {/* Squares in this rank */}
          {files.map((fileIndex) => {
            const piece = boardState.board[rankIndex][fileIndex];
            const isLight = (rankIndex + fileIndex) % 2 === 1;
            
            return (
              <div 
                key={`cell-${rankIndex}-${fileIndex}`} 
                className={`chess-cell ${isLight ? 'light' : 'dark'}`}
              >
                {piece && (
                  <span className={`chess-piece ${piece.color === 'w' ? 'white-piece' : 'black-piece'}`}>
                    {getPieceSymbol(piece.type)}
                  </span>
                )}
              </div>
            );
          })}
          
          {/* Rank label on right side */}
          <div className="chess-label">{rankLabels[i]}</div>
        </div>
      ))}
      
      {renderFiles()}
      
      {/* Turn indicator */}
      <div className={`chess-turn-indicator ${boardState.turn === 'w' ? 'white-to-move' : 'black-to-move'}`}>
        <span className="turn-symbol">♟</span>
        <span>{boardState.turn === 'w' ? 'White to move' : 'Black to move'}</span>
      </div>
      
      {/* FEN display */}
      <div className="chess-fen">
        <button 
          className="fen-toggle" 
          onClick={() => setShowFEN(!showFEN)}
        >
          {showFEN ? 'Hide position (FEN)' : 'Show position (FEN)'}
        </button>
        
        {showFEN && (
          <div className="fen-text">{fen}</div>
        )}
      </div>
    </div>
  );
};

export default ChessBoard;

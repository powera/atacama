import React, { useState, useEffect, useRef } from 'react';
import { useFullscreen } from './useFullscreen';
import { useGlobalSettings } from './useGlobalSettings';
import { LucidePlay, LucideRefreshCw, LucideCheck, LucideX, LucideClock } from 'lucide-react';

const BasketballGame = () => {
  // Refs and hooks for fullscreen and settings
  const { isFullscreen, toggleFullscreen, containerRef } = useFullscreen();
  const { settings, SettingsToggle, SettingsModal } = useGlobalSettings();

  // Game states
  const [playerPoints, setPlayerPoints] = useState(0);
  const [opponentPoints, setOpponentPoints] = useState(0);
  const [playerShots, setPlayerShots] = useState(0);
  const [playerMadeShots, setPlayerMadeShots] = useState(0);
  const [gameTime, setGameTime] = useState(600); // 10 minutes in seconds
  const [currentPossession, setCurrentPossession] = useState('player'); // 'player' or 'opponent'
  const [shotType, setShotType] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [outcomeMessage, setOutcomeMessage] = useState('');
  const [timer, setTimer] = useState(0);
  const [showResults, setShowResults] = useState(false);

  const timerRef = useRef(null);
  const possessionTimeoutRef = useRef(null);

  // Shot options
  const shotOptions = [
    { label: 'Drive', points: [0, 2, 3], successProb: 0.6 },
    { label: 'Jumper', points: [0, 2, 3], successProb: 0.5 },
    { label: '3-Pointer', points: [0, 3], successProb: 0.4 },
    { label: 'Layup', points: [0, 2], successProb: 0.7 },
  ];

  // Start game
  const startGame = () => {
    setPlayerPoints(0);
    setOpponentPoints(0);
    setPlayerShots(0);
    setPlayerMadeShots(0);
    setGameTime(600);
    setCurrentPossession('player');
    setOutcomeMessage('');
    setShowResults(false);
    setIsPlaying(true);
  };

  // Handle game timer
  useEffect(() => {
    if (isPlaying && gameTime > 0) {
      timerRef.current = setInterval(() => {
        setGameTime((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [isPlaying, gameTime]);

  // Handle end of game
  useEffect(() => {
    if (gameTime === 0) {
      setIsPlaying(false);
      setShowResults(true);
    }
  }, [gameTime]);

  // Handle possession switch
  const switchPossession = () => {
    setCurrentPossession((prev) => (prev === 'player' ? 'opponent' : 'player'));
  };

  // Simulate opponent possession
  const runOpponentPossession = () => {
    // Opponent takes ~20 seconds
    possessionTimeoutRef.current = setTimeout(() => {
      // Opponent scores randomly
      const opponentScore = Math.random() < 0.5 ? 2 : 3;
      setOpponentPoints((prev) => prev + opponentScore);
      switchPossession();
    }, 20000);
  };

  // Handle shot selection
  const handleShot = (shot) => {
    if (!isPlaying || currentPossession !== 'player') return;

    setShotType(shot.label);
    setPlayerShots((prev) => prev + 1);

    // Determine outcome
    const success = Math.random() < shot.successProb;
    const pointsScored = success ? shot.points[Math.floor(Math.random() * shot.points.length)] : 0;

    if (pointsScored > 0) {
      setPlayerMadeShots((prev) => prev + 1);
      setPlayerPoints((prev) => prev + pointsScored);
      setOutcomeMessage(`Nice! You scored ${pointsScored} points with a ${shot.label}.`);
    } else {
      setOutcomeMessage(`Missed your ${shot.label}.`);
    }

    // Run opponent possession after a short delay (~2 seconds)
    setTimeout(() => {
      switchPossession();
      runOpponentPossession();
    }, 2000);
  };

  // Initialize first opponent possession when game starts
  useEffect(() => {
    if (isPlaying && currentPossession === 'opponent') {
      runOpponentPossession();
    }
    // Cleanup on unmount or game end
    return () => clearTimeout(possessionTimeoutRef.current);
  }, [isPlaying, currentPossession]);

  // Handle game end
  const handleReset = () => {
    setIsPlaying(false);
    setShowResults(false);
    setOutcomeMessage('');
    clearTimeout(possessionTimeoutRef.current);
  };

  // Format time
  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60)
      .toString()
      .padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div ref={containerRef} className={isFullscreen ? 'w-fullscreen' : 'w-container'}>
      {/* Header */}
      <div className="w-game-header">
        <h1>Basketball Game</h1>
        <div className="header-actions">
          <SettingsToggle />
          <button className="w-button" onClick={startGame}>
            <LucidePlay className="w-5" /> Start Game
          </button>
        </div>
      </div>

      {/* Main Content */}
      {!isPlaying && !showResults && (
        <div className="widget-mount-point">
          <h2 className="w-question">Ready to Play?</h2>
          <p className="w-text-center">Click "Start Game" to begin a 10-minute basketball shootout!</p>
        </div>
      )}

      {isPlaying && (
        <div className="w-card">
          {/* Timer and Score */}
          <div className="w-stats">
            <div className="w-stat-item">
              <div className="w-stat-value">{playerPoints}</div>
              <div className="w-stat-label">Your Points</div>
            </div>
            <div className="w-stat-item">
              <div className="w-stat-value">{opponentPoints}</div>
              <div className="w-stat-label">Opponent Points</div>
            </div>
            <div className="w-stat-item">
              <div className="w-stat-value">{formatTime(gameTime)}</div>
              <div className="w-stat-label">
                <LucideClock className="w-4 inline" /> Time
              </div>
            </div>
          </div>

          {/* Possession Indicator */}
          <div className="w-feedback w-text-center">
            {currentPossession === 'player' ? 'Your Turn! Choose a shot.' : "Opponent's turn..."}
          </div>

          {/* Shot Options for Player */}
          {currentPossession === 'player' && (
            <div className="w-multiple-choice">
              {shotOptions.map((shot) => (
                <button
                  key={shot.label}
                  className="w-choice-option"
                  onClick={() => handleShot(shot)}
                >
                  {shot.label}
                </button>
              ))}
            </div>
          )}

          {/* Outcome Message */}
          {outcomeMessage && (
            <div className="w-feedback w-success">{outcomeMessage}</div>
          )}
        </div>
      )}

      {/* End of Game Results */}
      {showResults && (
        <div className="widget-error">
          <h2>Game Over!</h2>
          <p>
            Final Score: You {playerPoints} - Opponent {opponentPoints}
          </p>
          <p>
            Shots Taken: {playerShots} | Made Shots: {playerMadeShots}
          </p>
          <button className="w-button" onClick={startGame}>
            <LucideRefreshCw className="w-5" /> Play Again
          </button>
        </div>
      )}

      {/* Fullscreen toggle button */}
      <button className="w-fullscreen-toggle" onClick={toggleFullscreen}>
        {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
      </button>

      {/* Settings modal toggle */}
      <SettingsModal />
    </div>
  );
};

export default BasketballGame;

import React, { useState, useEffect } from 'react';
import useGlobalSettings from './useGlobalSettings';

const MathPracticeWidget = () => {
  const [problem, setProblem] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [feedback, setFeedback] = useState('');
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [showCorrectAnswer, setShowCorrectAnswer] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);

  const { 
     settings, 
     updateSetting, 
     showGlobalSettings, 
     toggleGlobalSettings,
     SettingsModal,
     SettingsToggle
   } = useGlobalSettings();

  // Generate a new math problem with answer choices
  const generateProblem = () => {
    const operation = Math.random() < 0.5 ? '+' : '-';
    let num1 = Math.floor(Math.random() * 16);
    let num2 = Math.floor(Math.random() * 16);
    if (operation === '-' && num1 < num2) {
      [num1, num2] = [num2, num1];
    }
    const correctAnswer = operation === '+' ? num1 + num2 : num1 - num2;

    const answerChoices = new Set([correctAnswer]);
    while (answerChoices.size < 4) {
      let wrongAnswer;
      if (operation === '+') {
        wrongAnswer = Math.floor(Math.random() * 31);
      } else {
        wrongAnswer = Math.floor(Math.random() * 16);
      }
      answerChoices.add(wrongAnswer);
    }
    const answersArray = Array.from(answerChoices).sort(() => Math.random() - 0.5);
    setProblem({ num1, num2, operation, correctAnswer });
    setAnswers(answersArray);
    setFeedback('');
    setSelectedAnswer(null);
    setShowCorrectAnswer(false);
  };

  // Initialize first problem
  useEffect(() => {
    generateProblem();
  }, []);

  // Handle answer selection
  const handleAnswer = (answer) => {
    setSelectedAnswer(answer);
    if (answer === problem.correctAnswer) {
      setFeedback('Great job! That\'s correct! 🌟');
      setScore((prev) => prev + 1);
      setStreak((prev) => prev + 1);
      setShowCorrectAnswer(true);
      setTimeout(() => {
        generateProblem();
      }, 2000);
    } else {
      setFeedback('Not quite. Try again! 💪');
      setStreak(0);
      setTimeout(() => {
        setSelectedAnswer(null);
      }, 800);
    }
  };

  // Generate encouragement message based on streak
  const getEncouragement = () => {
    if (streak >= 5) return 'Amazing streak! 🔥';
    if (streak >= 3) return 'You\'re on fire! 🎯';
    if (streak >= 1) return 'Keep going! 👍';
    return '';
  };

  // Determine button class based on answer state
  const getButtonClass = (answer) => {
    if (selectedAnswer === null) {
      return 'bg-yellow-400 hover:bg-yellow-500 text-gray-800';
    }
    if (answer === selectedAnswer) {
      if (answer === problem.correctAnswer) {
        return 'bg-green-500 text-white animate-pulse';
      } else {
        return 'bg-red-400 text-white animate-shake';
      }
    }
    if (showCorrectAnswer && answer === problem.correctAnswer) {
      return 'bg-green-500 text-white';
    }
    return 'bg-gray-300 text-gray-600';
  };

  // Toggle full-screen mode
  const toggleFullScreen = () => {
    setIsFullScreen((prev) => !prev);
  };

  if (!problem) return null;

  return (
    <div
      className={`w-container ${isFullScreen ? 'w-fullscreen' : ''}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: isFullScreen ? '100vh' : 'auto',
        overflow: isFullScreen ? 'auto' : 'visible',
        padding: 'var(--spacing-base)',
        backgroundColor: 'var(--color-background)',
        position: isFullScreen ? 'fixed' : 'relative',
        top: 0,
        left: 0,
        width: '100%',
        zIndex: isFullScreen ? 1000 : 'auto',
      }}
    >
      {/* Fullscreen toggle button */}
      <button
        onClick={toggleFullScreen}
        className="w-fullscreen-toggle"
        style={{
          alignSelf: 'flex-end',
          marginBottom: 'var(--spacing-small)',
        }}
      >
        {isFullScreen ? 'Exit Full Screen' : 'Full Screen'}
      </button>

      {/* Header */}
      <div className="site-banner" style={{ marginBottom: 'var(--spacing-large)' }}>
        <div className="banner-content">
          <h2 className="site-title">Math Practice</h2>
          <div className="flex justify-around text-sm">
            <div className="bg-green-100 px-3 py-1 rounded">
              <span className="text-green-700 font-semibold">Score: {score}</span>
            </div>
            <div className="bg-purple-100 px-3 py-1 rounded">
              <span className="text-purple-700 font-semibold">Streak: {streak}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Problem Display */}
      <div className="bg-white p-6 rounded-lg shadow mb-6" style={{ flex: '0 0 auto' }}>
        <div
          className="text-4xl font-bold text-center text-gray-800 transition-all duration-300"
          style={{ fontSize: 'clamp(2rem, 4vw, 3rem)' }}
        >
          {problem.num1} {problem.operation} {problem.num2} = {showCorrectAnswer ? problem.correctAnswer : '?'}
        </div>
      </div>

    <div>
      {/* Add the toggle button somewhere in your UI */}
      <SettingsToggle />
     
      
      {/* Add the modal at the end of your component */}
      <SettingsModal />
    </div>


      {/* Answer Buttons */}
      <div
        className="grid grid-cols-2 gap-4 mb-4"
        style={{ flex: '0 0 auto' }}
      >
        {answers.map((answer, index) => (
          <button
            key={index}
            onClick={() => handleAnswer(answer)}
            disabled={selectedAnswer !== null}
            className={`${getButtonClass(answer)} text-2xl font-bold py-4 px-6 rounded-lg shadow-md transform transition-all duration-300 ${
              selectedAnswer === null ? 'hover:scale-105' : ''
            }`}
            style={{
              minHeight: '60px',
            }}
          >
            {answer}
          </button>
        ))}
      </div>

      {/* Feedback */}
      <div className="text-center h-12" style={{ flex: '0 0 auto' }}>
        {feedback && (
          <div
            className={`text-lg font-bold ${
              feedback.includes('correct') ? 'text-green-600' : 'text-orange-600'
            }`}
          >
            {feedback}
          </div>
        )}
        {streak > 0 && (
          <div className="text-purple-600 font-bold mt-1">{getEncouragement()}</div>
        )}
      </div>

      {/* New Problem Button */}
      <div className="text-center mt-4" style={{ flex: '0 0 auto' }}>
        <button
          onClick={generateProblem}
          className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg shadow"
        >
          New Problem
        </button>
      </div>

    </div>
  );
};

export default MathPracticeWidget;

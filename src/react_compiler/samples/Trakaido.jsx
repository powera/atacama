import React, { useState, useEffect } from 'react';
import { useGlobalSettings } from './useGlobalSettings';  // This is the correct syntax for now; it is awkward and possibly should be updated.
import { useFullscreen } from './useFullscreen';

// API configuration
const API_BASE = '/api/lithuanian';

// API helper functions
const fetchCorpora = async () => {
  const response = await fetch(`${API_BASE}/wordlists`);
  if (!response.ok) throw new Error('Failed to fetch corpora');
  const data = await response.json();
  return data.corpora;
};

const fetchCorpusStructure = async (corpus) => {
  const response = await fetch(`${API_BASE}/wordlists/${encodeURIComponent(corpus)}`);
  if (!response.ok) throw new Error(`Failed to fetch structure for corpus: ${corpus}`);
  const data = await response.json();
  return data;
};

const fetchAvailableVoices = async () => {
  try {
    const response = await fetch(`${API_BASE}/audio/voices`);
    if (!response.ok) throw new Error('Failed to fetch voices');
    const data = await response.json();
    return data.voices;
  } catch (error) {
    console.warn('Failed to fetch available voices:', error);
    return [];
  }
};

const fetchConjugations = async () => {
  try {
    const response = await fetch(`${API_BASE}/conjugations`);
    if (!response.ok) throw new Error('Failed to fetch conjugations');
    const data = await response.json();
    return data;
  } catch (error) {
    console.warn('Failed to fetch conjugations:', error);
    return { conjugations: {}, verbs: [] };
  }
};

const FlashCardApp = () => {
  // Global settings integration
  const { 
    settings, 
    SettingsModal, 
    SettingsToggle 
  } = useGlobalSettings({
    usedSettings: ['audioEnabled', 'soundVolume', 'autoAdvance', 'defaultDelay', 'difficulty']
  });

  // Fullscreen functionality
  const { isFullscreen, toggleFullscreen, containerRef } = useFullscreen();

  const [corporaData, setCorporaData] = useState({}); // Cache for corpus structures
  const [currentCard, setCurrentCard] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [availableCorpora, setAvailableCorpora] = useState([]);
  const [selectedGroups, setSelectedGroups] = useState({}); // {corpus: [group1, group2]}
  const [studyMode, setStudyMode] = useState('english-to-lithuanian');
  const [stats, setStats] = useState({ correct: 0, incorrect: 0, total: 0 });
  const [shuffled, setShuffled] = useState(true);
  const [showCorpora, setShowCorpora] = useState(false);
  const [quizMode, setQuizMode] = useState('flashcard');
  const [multipleChoiceOptions, setMultipleChoiceOptions] = useState([]);
  const [selectedAnswer, setSelectedAnswer] = useState(null);

  const [audioCache, setAudioCache] = useState({});
  const [hoverTimeout, setHoverTimeout] = useState(null);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingWords, setLoadingWords] = useState(false);
  const [allWords, setAllWords] = useState([]);
  const [conjugations, setConjugations] = useState({});
  const [availableVerbs, setAvailableVerbs] = useState([]);
  const [selectedVerb, setSelectedVerb] = useState(null);
  const [loadingConjugations, setLoadingConjugations] = useState(false);
  const [autoAdvanceTimer, setAutoAdvanceTimer] = useState(null);

  // Use global settings for audio and auto-advance
  const audioEnabled = settings.audioEnabled;
  const autoAdvance = settings.autoAdvance;
  const defaultDelay = settings.defaultDelay;

  // Load initial data
  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [corpora, voices, conjugationData] = await Promise.all([
          fetchCorpora(),
          fetchAvailableVoices(),
          fetchConjugations()
        ]);
        setAvailableCorpora(corpora);
        setAvailableVoices(voices);
        setConjugations(conjugationData.conjugations);
        setAvailableVerbs(conjugationData.verbs);
        if (voices.length > 0) {
          setSelectedVoice(voices[0]);
        }
        const corporaStructures = {};
        const defaultSelectedGroups = {};
        for (const corpus of corpora) {
          try {
            const structure = await fetchCorpusStructure(corpus);
            corporaStructures[corpus] = structure;
            const groups = Object.keys(structure.groups);
            defaultSelectedGroups[corpus] = groups;
          } catch (err) {
            console.warn(`Failed to load structure for corpus: ${corpus}`, err);
          }
        }
        setCorporaData(corporaStructures);
        setSelectedGroups(defaultSelectedGroups);
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError('Failed to load vocabulary data. Please try refreshing the page.');
      } finally {
        setLoading(false);
      }
    };
    loadInitialData();
  }, []);

  // Generate words list when selected groups change
  useEffect(() => {
    const generateWordsList = () => {
      if (Object.keys(corporaData).length === 0) {
        setAllWords([]);
        return;
      }
      let words = [];
      Object.entries(selectedGroups).forEach(([corpus, groups]) => {
        if (corporaData[corpus] && groups.length > 0) {
          groups.forEach(group => {
            if (corporaData[corpus].groups[group]) {
              const groupWords = corporaData[corpus].groups[group].map(word => ({
                ...word,
                corpus,
                group
              }));
              words.push(...groupWords);
            }
          });
        }
      });
      if (shuffled) {
        words = words.sort(() => Math.random() - 0.5);
      }
      setAllWords(words);
      setCurrentCard(0);
      setShowAnswer(false);
      setSelectedAnswer(null);
    };
    if (!loading) {
      generateWordsList();
    }
  }, [selectedGroups, shuffled, loading, corporaData]);

  // Generate multiple choice options when card changes or mode changes
  useEffect(() => {
    if (quizMode === 'multiple-choice' && allWords.length > 0) {
      generateMultipleChoiceOptions();
    }
  }, [currentCard, quizMode, allWords, studyMode, settings.difficulty]);

  // Pre-load audio for multiple choice options when audio is enabled
  useEffect(() => {
    if (audioEnabled && quizMode === 'multiple-choice' && multipleChoiceOptions.length > 0) {
      preloadMultipleChoiceAudio();
    }
  }, [audioEnabled, quizMode, studyMode, multipleChoiceOptions, selectedVoice]);

  const generateMultipleChoiceOptions = () => {
    const currentWord = allWords[currentCard];
    if (!currentWord) return;
    const correctAnswer = studyMode === 'english-to-lithuanian' ? currentWord.lithuanian : currentWord.english;

    // Determine number of options based on difficulty
    const numOptions = settings.difficulty === 'easy' ? 4 : settings.difficulty === 'medium' ? 6 : 8;
    const numWrongAnswers = numOptions - 1;

    const sameCorpusWords = allWords.filter(word => 
      word.corpus === currentWord.corpus && 
      (studyMode === 'english-to-lithuanian' ? word.lithuanian : word.english) !== correctAnswer
    );
    const wrongAnswersSet = new Set();
    const wrongAnswers = [];
    // Gather wrong answers from same corpus - shuffle first to get random decoys
    const shuffledSameCorpusWords = [...sameCorpusWords].sort(() => Math.random() - 0.5);
    for (const word of shuffledSameCorpusWords) {
      const answer = studyMode === 'english-to-lithuanian' ? word.lithuanian : word.english;
      if (answer !== correctAnswer && !wrongAnswersSet.has(answer)) {
        wrongAnswersSet.add(answer);
        wrongAnswers.push(answer);
        if (wrongAnswers.length >= numWrongAnswers) break;
      }
    }
    // Pad with any other words if needed
    if (wrongAnswers.length < numWrongAnswers) {
      const fallbackWords = allWords
        .map(w => (studyMode === 'english-to-lithuanian' ? w.lithuanian : w.english))
        .filter(ans => ans !== correctAnswer && !wrongAnswersSet.has(ans))
        .sort(() => Math.random() - 0.5); // Shuffle fallback words too
      while (wrongAnswers.length < numWrongAnswers && fallbackWords.length > 0) {
        const randIdx = Math.floor(Math.random() * fallbackWords.length);
        const fallback = fallbackWords.splice(randIdx, 1)[0];
        wrongAnswers.push(fallback);
      }
    }

    let options = [correctAnswer, ...wrongAnswers];

    // Sort alphabetically for medium and hard difficulty, otherwise shuffle
    if (settings.difficulty === 'medium' || settings.difficulty === 'hard') {
      options = options.sort();
      // Rearrange to fill columns first (left column, then right column)
      const rearranged = [];
      const half = Math.ceil(options.length / 2);
      for (let i = 0; i < half; i++) {
        rearranged.push(options[i]);
        if (i + half < options.length) {
          rearranged.push(options[i + half]);
        }
      }
      options = rearranged;
    } else {
      options = options.sort(() => Math.random() - 0.5);
    }

    setMultipleChoiceOptions(options);
  };

  const preloadMultipleChoiceAudio = async () => {
    if (!selectedVoice) return;
    const promises = multipleChoiceOptions.map(async (option) => {
      try {
        const cacheKey = `${option}-${selectedVoice}`;
        if (!audioCache[cacheKey]) {
          const audioUrl = `${API_BASE}/audio/${encodeURIComponent(option)}?voice=${encodeURIComponent(selectedVoice)}`;
          const audio = new Audio(audioUrl);
          await new Promise((resolve, reject) => {
            audio.addEventListener('canplaythrough', resolve);
            audio.addEventListener('error', reject);
            audio.load();
          });
          setAudioCache(prev => ({ ...prev, [cacheKey]: audio }));
        }
      } catch (error) {
        console.warn(`Failed to preload audio for: ${option}`, error);
      }
    });
    await Promise.allSettled(promises);
  };

  const shuffleCards = () => {
    setShuffled(prev => !prev);
  };

  const resetCards = () => {
    setCurrentCard(0);
    setShowAnswer(false);
    setStats({ correct: 0, incorrect: 0, total: 0 });
    setSelectedAnswer(null);
  };

  const nextCard = () => {
    // Cancel any existing auto-advance timer
    if (autoAdvanceTimer) {
      clearTimeout(autoAdvanceTimer);
      setAutoAdvanceTimer(null);
    }
    setCurrentCard(prev => (prev + 1) % allWords.length);
    setShowAnswer(false);
    setSelectedAnswer(null);
  };

  const prevCard = () => {
    // Cancel any existing auto-advance timer
    if (autoAdvanceTimer) {
      clearTimeout(autoAdvanceTimer);
      setAutoAdvanceTimer(null);
    }
    setCurrentCard(prev => (prev - 1 + allWords.length) % allWords.length);
    setShowAnswer(false);
    setSelectedAnswer(null);
  };

  const markCorrect = () => {
    setStats(prev => ({ ...prev, correct: prev.correct + 1, total: prev.total + 1 }));
    if (autoAdvance) {
      const timerId = setTimeout(() => {
        setCurrentCard(prev => (prev + 1) % allWords.length);
        setShowAnswer(false);
        setSelectedAnswer(null);
        setAutoAdvanceTimer(null);
      }, defaultDelay * 1000);
      setAutoAdvanceTimer(timerId);
    } else {
      setCurrentCard(prev => (prev + 1) % allWords.length);
      setShowAnswer(false);
      setSelectedAnswer(null);
    }
  };

  const markIncorrect = () => {
    setStats(prev => ({ ...prev, incorrect: prev.incorrect + 1, total: prev.total + 1 }));
    if (autoAdvance) {
      const timerId = setTimeout(() => {
        setCurrentCard(prev => (prev + 1) % allWords.length);
        setShowAnswer(false);
        setSelectedAnswer(null);
        setAutoAdvanceTimer(null);
      }, defaultDelay * 1000);
      setAutoAdvanceTimer(timerId);
    } else {
      setCurrentCard(prev => (prev + 1) % allWords.length);
      setShowAnswer(false);
      setSelectedAnswer(null);
    }
  };

  const handleMultipleChoiceAnswer = (selectedOption) => {
    const currentWord = allWords[currentCard];
    const correctAnswer = studyMode === 'english-to-lithuanian' ? currentWord.lithuanian : currentWord.english;
    setSelectedAnswer(selectedOption);
    setShowAnswer(true);
    const isCorrect = selectedOption === correctAnswer;

    if (isCorrect) {
      setStats(prev => ({ ...prev, correct: prev.correct + 1, total: prev.total + 1 }));
    } else {
      setStats(prev => ({ ...prev, incorrect: prev.incorrect + 1, total: prev.total + 1 }));
    }

    if (autoAdvance) {
      const timerId = setTimeout(() => {
        setCurrentCard(prev => (prev + 1) % allWords.length);
        setShowAnswer(false);
        setSelectedAnswer(null);
        setAutoAdvanceTimer(null);
      }, defaultDelay * 1000);
      setAutoAdvanceTimer(timerId);
    }
  };

  const playAudio = async (word) => {
    if (!audioEnabled) return;
    try {
      const cacheKey = `${word}-${selectedVoice}`;
      if (audioCache[cacheKey]) {
        const audio = audioCache[cacheKey].cloneNode();
        await audio.play();
        return;
      }
      const audioUrl = `${API_BASE}/audio/${encodeURIComponent(word)}${selectedVoice ? `?voice=${encodeURIComponent(selectedVoice)}` : ''}`;
      const audio = new Audio(audioUrl);
      setAudioCache(prev => ({ ...prev, [cacheKey]: audio }));
      await audio.play();
    } catch (error) {
      console.warn('Audio playback failed:', error);
    }
  };

  const handleHoverStart = (word) => {
    if (!audioEnabled || !selectedVoice) return;
    const timeout = setTimeout(() => {
      const cacheKey = `${word}-${selectedVoice}`;
      if (audioCache[cacheKey]) {
        playAudio(word);
      }
    }, 900);
    setHoverTimeout(timeout);
  };

  const handleHoverEnd = () => {
    if (hoverTimeout) {
      clearTimeout(hoverTimeout);
      setHoverTimeout(null);
    }
  };

  const toggleGroup = (corpus, group) => {
    setSelectedGroups(prev => {
      const currentGroups = prev[corpus] || [];
      const newGroups = currentGroups.includes(group)
        ? currentGroups.filter(g => g !== group)
        : [...currentGroups, g];
      return { ...prev, [corpus]: newGroups };
    });
  };

  const toggleCorpus = (corpus) => {
    setSelectedGroups(prev => {
      const allGroups = Object.keys(corporaData[corpus]?.groups || {});
      const currentGroups = prev[corpus] || [];
      const allSelected = allGroups.length > 0 && allGroups.every(g => currentGroups.includes(g));
      return {
        ...prev,
        [corpus]: allSelected ? [] : allGroups
      };
    });
  };

  const currentWord = allWords[currentCard];

  // Count total selected words
  const totalSelectedWords = allWords.length;

  // Render conjugation table
  const renderConjugationTable = (verb) => {
    const conjugationList = conjugations[verb];
    if (!conjugationList) return null;

    // Create a 3x3 grid for conjugations
    const conjugationGrid = {
      'I': null, 'you(s.)': null, 'he': null,
      'she': null, 'it': null, 'we': null,
      'you(pl.)': null, 'they(m.)': null, 'they(f.)': null
    };

    conjugationList.forEach(conj => {
      const pronoun = conj.english.split(' ')[0];
      conjugationGrid[pronoun] = conj;
    });

    return (
      <div style={{ marginTop: 'var(--spacing-base)' }}>
        <h4>Conjugation Table for "{verb}"</h4>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          border: '1px solid var(--color-border)',
          marginTop: 'var(--spacing-small)'
        }}>
          <thead>
            <tr style={{ background: 'var(--color-annotation-bg)' }}>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Person</th>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>English</th>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Lithuanian</th>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Audio</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(conjugationGrid).map(([pronoun, conj]) => {
              if (!conj) return null;
              return (
                <tr key={pronoun}>
                  <td style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)', fontWeight: 'bold' }}>
                    {pronoun}
                  </td>
                  <td style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>
                    {conj.english}
                  </td>
                  <td style={{ 
                    padding: 'var(--spacing-small)', 
                    border: '1px solid var(--color-border)',
                    cursor: audioEnabled ? 'pointer' : 'default'
                  }}
                  onMouseEnter={() => audioEnabled && handleHoverStart(conj.lithuanian)}
                  onMouseLeave={handleHoverEnd}
                  >
                    {conj.lithuanian}
                  </td>
                  <td style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)', textAlign: 'center' }}>
                    {audioEnabled && (
                      <button 
                        className="w-audio-button"
                        onClick={() => playAudio(conj.lithuanian)}
                        title="Play pronunciation"
                        style={{ fontSize: '0.9rem' }}
                      >
                        🔊
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  // Loading state
  if (loading) {
    return (
      <div className="w-container">
        <h1>🇱🇹 Lithuanian Vocabulary Flash Cards</h1>
        <div className="w-card">
          <div style={{ textAlign: 'center', padding: 'var(--spacing-large)' }}>
            <div style={{ fontSize: '1.2rem', marginBottom: 'var(--spacing-base)' }}>Loading vocabulary data...</div>
            <div style={{ color: 'var(--color-text-secondary)' }}>This may take a moment</div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-container">
        <h1>🇱🇹 Lithuanian Vocabulary Flash Cards</h1>
        <div className="w-card">
          <div style={{ textAlign: 'center', padding: 'var(--spacing-large)' }}>
            <div style={{ fontSize: '1.2rem', marginBottom: 'var(--spacing-base)', color: 'var(--color-error)' }}>⚠️ Error</div>
            <div style={{ marginBottom: 'var(--spacing-base)' }}>{error}</div>
            <button className="w-button" onClick={() => window.location.reload()}>🔄 Retry</button>
          </div>
        </div>
      </div>
    );
  }

  // Show "no groups selected" message but keep the Study Materials section visible
  // Don't show this message in conjugations mode since it doesn't need word lists
  const showNoGroupsMessage = !currentWord && totalSelectedWords === 0 && quizMode !== 'conjugations';

  const question = currentWord ? (studyMode === 'english-to-lithuanian' ? currentWord.english : currentWord.lithuanian) : '';
  const answer = currentWord ? (studyMode === 'english-to-lithuanian' ? currentWord.lithuanian : currentWord.english) : '';

  return (
    <div ref={containerRef} className={`w-container ${isFullscreen ? 'w-fullscreen' : ''}`}>
      <style>{`
        .answer-text {
          font-size: 1.5rem;
          color: var(--color-text-secondary);
          margin-top: var(--spacing-base);
          display: flex;
          align-items: center;
          gap: var(--spacing-small);
          justify-content: center;
        }
        .choice-content {
          display: flex;
          align-items: center;
          gap: var(--spacing-small);
          justify-content: center;
        }
        .corpus-section {
          margin-bottom: var(--spacing-base);
          border: 1px solid var(--color-border);
          border-radius: var(--border-radius);
          padding: var(--spacing-base);
        }
        .corpus-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--spacing-small);
          cursor: pointer;
          font-weight: bold;
          color: var(--color-primary);
        }
        .group-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: var(--spacing-small);
          margin-top: var(--spacing-small);
        }
        .group-item {
          display: flex;
          align-items: center;
          gap: var(--spacing-small);
          padding: var(--spacing-small);
          background: var(--color-annotation-bg);
          border-radius: var(--border-radius);
        }
        .corpus-toggle {
          background: none;
          border: 1px solid var(--color-border);
          border-radius: var(--border-radius);
          padding: var(--spacing-small) var(--spacing-base);
          cursor: pointer;
          color: var(--color-text);
          font-size: 0.8rem;
        }
        .corpus-toggle:hover {
          background: var(--color-annotation-bg);
        }
      `}</style>

      <button className="w-fullscreen-toggle" onClick={toggleFullscreen}>
        {isFullscreen ? '🗗' : '⛶'}
      </button>

      {!isFullscreen && <h1>🇱🇹 Lithuanian Vocabulary Flash Cards</h1>}

      {!isFullscreen && (
        <div className="w-card">
          <div 
            style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              cursor: 'pointer', 
              marginBottom: showCorpora ? 'var(--spacing-base)' : '0'
            }}
            onClick={() => setShowCorpora(!showCorpora)}
          >
            <h3>Study Materials ({totalSelectedWords} words selected)</h3>
            <button className="w-button-secondary" style={{ padding: 'var(--spacing-small)' }}>
              {showCorpora ? '▼' : '▶'}
            </button>
          </div>
          {showCorpora && (
            <div>
              {availableCorpora.map(corpus => {
                const corporaStructure = corporaData[corpus];
                if (!corporaStructure) return null;
                const groups = Object.keys(corporaStructure.groups);
                const selectedCorpusGroups = selectedGroups[corpus] || [];
                const allSelected = groups.length > 0 && groups.every(g => selectedCorpusGroups.includes(g));
                const wordCount = selectedCorpusGroups.reduce((total, g) => {
                  return total + (corporaStructure.groups[g]?.length || 0);
                }, 0);
                return (
                  <div key={corpus} className="corpus-section">
                    <div className="corpus-header" onClick={() => toggleCorpus(corpus)}>
                      <div>
                        📚 {corpus} ({wordCount} words from {selectedCorpusGroups.length}/{groups.length} groups)
                      </div>
                      <button className="corpus-toggle">
                        {allSelected ? 'Deselect All' : 'Select All'}
                      </button>
                    </div>
                    <div className="group-grid">
                      {groups.map(group => {
                        const groupWordCount = corporaStructure.groups[group]?.length || 0;
                        const isSelected = selectedCorpusGroups.includes(group);
                        return (
                          <div key={group} className="group-item">
                            <input
                              type="checkbox"
                              id={`${corpus}-${group}`}
                              checked={isSelected}
                              onChange={() => toggleGroup(corpus, group)}
                            />
                            <label htmlFor={`${corpus}-${group}`} style={{ fontSize: '0.9rem' }}>
                              {group} ({groupWordCount} words)
                            </label>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="w-mode-selector">
        {!fullScreen && <h3>Study Options:</h3>}
        <button
          className={`w-mode-option ${studyMode === 'english-to-lithuanian' ? 'w-active' : ''}`}
          onClick={() => setStudyMode('english-to-lithuanian')}
        >
          English → Lithuanian
        </button>
        <button
          className={`w-mode-option ${studyMode === 'lithuanian-to-english' ? 'w-active' : ''}`}
          onClick={() => setStudyMode('lithuanian-to-english')}
        >
          Lithuanian → English
        </button>
        <button
          className={`w-mode-option ${quizMode === 'flashcard' ? 'w-active' : ''}`}
          onClick={() => setQuizMode('flashcard')}
        >
          Flash Cards
        </button>
        <button
          className={`w-mode-option ${quizMode === 'multiple-choice' ? 'w-active' : ''}`}
          onClick={() => setQuizMode('multiple-choice')}
        >
          Multiple Choice
        </button>
        <button
          className={`w-mode-option ${quizMode === 'conjugations' ? 'w-active' : ''}`}
          onClick={() => setQuizMode('conjugations')}
        >
          📖 Conjugations
        </button>
        <button
          className={`w-mode-option ${shuffled ? 'w-active' : ''}`}
          onClick={shuffleCards}
        >
          🔀 {shuffled ? 'Shuffled' : 'Ordered'}
        </button>
        <SettingsToggle className="w-mode-option">
          ⚙️ Settings
        </SettingsToggle>
        {audioEnabled && availableVoices.length > 0 && (
          <select 
            value={selectedVoice || ''} 
            onChange={(e) => setSelectedVoice(e.target.value)}
            style={{
              padding: 'var(--spacing-small) var(--spacing-base)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--border-radius)',
              background: 'var(--color-background)',
              color: 'var(--color-text)',
              fontSize: '0.9rem'
            }}
          >
            {availableVoices.map(voice => (
              <option key={voice} value={voice}>
                🎤 {voice}
              </option>
            ))}
          </select>
        )}
      </div>

      {!showNoGroupsMessage && (
        <div className="w-progress">
          Card {currentCard + 1} of {allWords.length}
          {shuffled && " (shuffled)"}
        </div>
      )}

      {showNoGroupsMessage ? (
        <div className="w-card">
          <div style={{ textAlign: 'center', padding: 'var(--spacing-large)' }}>
            <div style={{ fontSize: '1.2rem', marginBottom: 'var(--spacing-base)' }}>📭 No Words Available</div>
            <div>No vocabulary words found for the selected groups. Please try selecting different groups.</div>
          </div>
        </div>
      ) : quizMode === 'conjugations' ? (
        <div className="w-card">
          <h3>Lithuanian Verb Conjugations</h3>
          <div style={{ marginBottom: 'var(--spacing-base)' }}>
            <label htmlFor="verb-select" style={{ marginRight: 'var(--spacing-small)' }}>
              Select a verb:
            </label>
            <select 
              id="verb-select"
              value={selectedVerb || ''} 
              onChange={(e) => setSelectedVerb(e.target.value)}
              style={{
                padding: 'var(--spacing-small) var(--spacing-base)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--border-radius)',
                background: 'var(--color-background)',
                color: 'var(--color-text)',
                fontSize: '0.9rem',
                minWidth: '150px'
              }}
            >
              <option value="">Choose a verb...</option>
              {availableVerbs.map(verb => (
                <option key={verb} value={verb}>
                  {verb}
                </option>
              ))}
            </select>
          </div>
          {selectedVerb && renderConjugationTable(selectedVerb)}
        </div>
      ) : quizMode === 'flashcard' ? (
        <div className="w-card w-card-interactive" onClick={() => setShowAnswer(!showAnswer)}>
          <div className="w-badge">{currentWord.corpus} → {currentWord.group}</div>
          <div 
            className="w-question"
            onMouseEnter={() => audioEnabled && studyMode === 'lithuanian-to-english' && handleHoverStart(question)}
            onMouseLeave={handleHoverEnd}
            style={{ cursor: audioEnabled && studyMode === 'lithuanian-to-english' ? 'pointer' : 'default' }}
          >
            {question}
          </div>
          {showAnswer && (
            <div className="answer-text">
              <span>{answer}</span>
              {audioEnabled && (
                <button 
                  className="w-audio-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    playAudio(currentWord.lithuanian);
                  }}
                  title="Play pronunciation"
                >
                  🔊
                </button>
              )}
            </div>
          )}
          {!showAnswer && (
            <div style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: 'var(--spacing-base)' }}>
              Click to reveal answer
              {audioEnabled && studyMode === 'lithuanian-to-english' && (
                <div style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                  (Hover over Lithuanian word to hear pronunciation)
                </div>
              )}
            </div>
          )}
        </div>
      ) : currentWord ? (
        <div>
          <div className="w-card">
            <div className="w-badge">{currentWord.corpus} → {currentWord.group}</div>
            <div 
              className="w-question"
              onMouseEnter={() => audioEnabled && studyMode === 'lithuanian-to-english' && handleHoverStart(question)}
              onMouseLeave={handleHoverEnd}
              style={{ cursor: audioEnabled && studyMode === 'lithuanian-to-english' ? 'pointer' : 'default' }}
            >
              {question}
            </div>
            <div style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: 'var(--spacing-base)' }}>
              Choose the correct answer:
              {audioEnabled && (
                <div style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                  {studyMode === 'lithuanian-to-english' 
                    ? '(Hover over Lithuanian words for 0.9 seconds to hear pronunciation)'
                    : '(Hover over answer choices for 0.9 seconds to hear pronunciation)'}
                </div>
              )}
            </div>
          </div>
          <div className="w-multiple-choice">
            {multipleChoiceOptions.map((option, index) => {
              const currentWord = allWords[currentCard];
              if (!currentWord) return null;
              const correctAnswer = studyMode === 'english-to-lithuanian' ? currentWord.lithuanian : currentWord.english;
              const isCorrect = option === correctAnswer;
              const isSelected = option === selectedAnswer;
              let className = 'w-choice-option';
              if (showAnswer) {
                if (isCorrect) {
                  className += ' w-correct';
                } else if (isSelected && !isCorrect) {
                  className += ' w-incorrect';
                } else if (!isSelected) {
                  className += ' w-unselected';
                }
              }
              const shouldShowAudioOnHover = audioEnabled && studyMode === 'english-to-lithuanian';
              const audioWord = option; // In EN->LT mode, options are Lithuanian words

              // Find the translation for incorrect selected answer
              let incorrectTranslation = null;
              if (showAnswer && isSelected && !isCorrect) {
                const wrongWord = allWords.find(w => 
                  (studyMode === 'english-to-lithuanian' ? w.lithuanian : w.english) === option
                );
                if (wrongWord) {
                  incorrectTranslation = studyMode === 'english-to-lithuanian' ? wrongWord.english : wrongWord.lithuanian;
                }
              }

              return (
                <button
                  key={index}
                  className={className}
                  onClick={() => !showAnswer && handleMultipleChoiceAnswer(option)}
                  onMouseEnter={() => shouldShowAudioOnHover && handleHoverStart(audioWord)}
                  onMouseLeave={handleHoverEnd}
                  disabled={showAnswer}
                >
                  <div className="choice-content">
                    <div style={{ textAlign: 'center' }}>
                      <span>{option}</span>
                      {incorrectTranslation && (
                        <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.8)', marginTop: '4px' }}>
                          ({incorrectTranslation})
                        </div>
                      )}
                    </div>
                    {audioEnabled && showAnswer && isCorrect && (
                      <span 
                        className="w-audio-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const correctLithuanianWord = studyMode === 'english-to-lithuanian' ? option : currentWord.lithuanian;
                          playAudio(correctLithuanianWord);
                        }}
                        title="Play pronunciation"
                        style={{ 
                          fontSize: '1rem',
                          cursor: 'pointer',
                          display: 'inline-block',
                          padding: '4px',
                          borderRadius: '4px'
                        }}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            e.stopPropagation();
                            const correctLithuanianWord = studyMode === 'english-to-lithuanian' ? option : currentWord.lithuanian;
                            playAudio(correctLithuanianWord);
                          }
                        }}
                      >
                        🔊
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="w-card">
          <div style={{ textAlign: 'center', padding: 'var(--spacing-large)' }}>
            <div>Loading word...</div>
          </div>
        </div>
      )}

      {/* Navigation controls */}
      {!showNoGroupsMessage && quizMode !== 'conjugations' && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'var(--spacing-large)', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 'var(--spacing-small)', alignItems: 'center' }}>
            <button className="w-button" onClick={prevCard}>← Previous</button>
          </div>
          <div style={{ display: 'flex', gap: 'var(--spacing-small)', alignItems: 'center' }}>
            <button className="w-button" onClick={nextCard}>Next →</button>
          </div>
        </div>
      )}

      {/* Stats with Reset button */}
      {!showNoGroupsMessage && quizMode !== 'conjugations' && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '2rem', marginTop: 'var(--spacing-large)', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div className="w-stat-item" style={{ margin: 0 }}>
              <div className="w-stat-value" style={{ color: 'var(--color-success)' }}>
                {stats.correct}
              </div>
              <div className="w-stat-label">Correct</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div className="w-stat-item" style={{ margin: 0 }}>
              <div className="w-stat-value" style={{ color: 'var(--color-error)' }}>
                {stats.incorrect}
              </div>
              <div className="w-stat-label">Incorrect</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div className="w-stat-item" style={{ margin: 0 }}>
              <div className="w-stat-value" style={{ color: 'var(--color-primary)' }}>
                {stats.total > 0 ? Math.round((stats.correct / stats.total) * 100) : 0}%
              </div>
              <div className="w-stat-label">Accuracy</div>
            </div>
          </div>
          <button 
            className="w-button-secondary" 
            onClick={resetCards}
            style={{ fontSize: '0.8rem', padding: 'var(--spacing-small) var(--spacing-base)' }}
          >
            🔄 Reset
          </button>
        </div>
      )}

      <SettingsModal />
    </div>
  );
};

export default FlashCardApp;
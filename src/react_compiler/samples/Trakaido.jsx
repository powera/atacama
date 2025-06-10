import React, { useState, useEffect } from 'react';
import { useGlobalSettings } from './useGlobalSettings';  // This is the correct syntax for now; it is awkward and possibly should be updated.
import { useFullscreen } from './useFullscreen';

// Use the namespaced lithuanianApi from window
// These are provided by the script tag in widget.html: <script src="/js/lithuanianApi.js"></script>
const { 
  fetchCorpora, 
  fetchCorpusStructure, 
  fetchAvailableVoices, 
  fetchVerbCorpuses, 
  fetchConjugations, 
  fetchDeclensions,
  AudioManager
} = window.lithuanianApi;

// The CSS classes available are primarily in widget_tools.css .

// Helper function to safely access localStorage
const safeStorage = {
  getItem: (key, defaultValue = null) => {
    try {
      return localStorage.getItem(key) || defaultValue;
    } catch (error) {
      console.error(`Error reading ${key} from localStorage:`, error);
      return defaultValue;
    }
  },
  setItem: (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      console.error(`Error saving ${key} to localStorage:`, error);
    }
  },
  removeItem: (key) => {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.error(`Error removing ${key} from localStorage:`, error);
    }
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
  // Initialize selectedGroups from localStorage if available
  const [selectedGroups, setSelectedGroups] = useState(() => {
    const savedGroups = safeStorage?.getItem('flashcard-selected-groups');
    try {
      return savedGroups ? JSON.parse(savedGroups) : {};
    } catch (error) {
      console.error('Error parsing saved corpus groups:', error);
      return {};
    }
  }); // {corpus: [group1, group2]}

  // Initialize local settings from localStorage where available
  const [studyMode, setStudyMode] = useState(() => {
    return safeStorage?.getItem('flashcard-study-mode') || 'english-to-lithuanian';
  });
  const [stats, setStats] = useState({ correct: 0, incorrect: 0, total: 0 });
  const [showCorpora, setShowCorpora] = useState(false);
  const [quizMode, setQuizMode] = useState(() => {
    return safeStorage?.getItem('flashcard-quiz-mode') || 'flashcard';
  });
  const [multipleChoiceOptions, setMultipleChoiceOptions] = useState([]);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [grammarMode, setGrammarMode] = useState('conjugations');

  const [audioManager] = useState(() => new AudioManager());
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
  const [availableVerbCorpuses, setAvailableVerbCorpuses] = useState([]);
  const [selectedVerbCorpus, setSelectedVerbCorpus] = useState('verbs_present');
  const [declensions, setDeclensions] = useState({});
  const [availableNouns, setAvailableNouns] = useState([]);
  const [selectedNoun, setSelectedNoun] = useState(null);
  const [loadingDeclensions, setLoadingDeclensions] = useState(false);
  const [autoAdvanceTimer, setAutoAdvanceTimer] = useState(null);
  const [selectedVocabGroup, setSelectedVocabGroup] = useState(null);
  const [vocabGroupOptions, setVocabGroupOptions] = useState([]);
  const [vocabListWords, setVocabListWords] = useState([]);

  // Use global settings for audio and auto-advance
  const audioEnabled = settings.audioEnabled;
  const autoAdvance = settings.autoAdvance;
  const defaultDelay = settings.defaultDelay;
  
  // AudioButton component with access to app settings and playAudio function
  const AudioButton = ({ word, size = 'normal' }) => {
    // Define styles based on size
    const buttonStyle = {
      fontSize: size === 'small' ? '0.8rem' : size === 'large' ? '1.5rem' : '1rem',
      cursor: 'pointer',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center'
    };
    
    // If audio is disabled, show muted icon
    if (!audioEnabled) {
      return (
        <span 
          className="w-audio-button w-audio-disabled"
          title="Audio is disabled in settings"
          style={{
            ...buttonStyle,
            opacity: 0.5
          }}
        >
          🔇
        </span>
      );
    }
    
    return (
      <button 
        className="w-audio-button"
        onClick={(e) => {
          e.stopPropagation();
          playAudio(word);
        }}
        title="Play pronunciation"
        style={buttonStyle}
      >
        🔊
      </button>
    );
  };

  // Load initial data
  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [corpora, voices, verbCorpuses, conjugationData, declensionData] = await Promise.all([
          fetchCorpora(),
          fetchAvailableVoices(),
          fetchVerbCorpuses(),
          fetchConjugations(),
          fetchDeclensions()
        ]);
        setAvailableCorpora(corpora);
        setAvailableVoices(voices);
        setAvailableVerbCorpuses(verbCorpuses);
        setConjugations(conjugationData.conjugations);
        setAvailableVerbs(conjugationData.verbs);
        setDeclensions(declensionData.declensions);
        setAvailableNouns(declensionData.available_nouns);
        if (voices.length > 0) {
          setSelectedVoice(voices[0]);
        }
        const corporaStructures = {};
        // Only set default groups if we don't have any saved in localStorage
        const useDefaults = Object.keys(selectedGroups).length === 0;
        const defaultSelectedGroups = useDefaults ? {} : null;

        for (const corpus of corpora) {
          try {
            const structure = await fetchCorpusStructure(corpus);
            corporaStructures[corpus] = structure;

            // If we're using defaults, set all groups as selected
            if (useDefaults) {
              const groups = Object.keys(structure.groups);
              defaultSelectedGroups[corpus] = groups;
            }
          } catch (err) {
            console.warn(`Failed to load structure for corpus: ${corpus}`, err);
          }
        }
        setCorporaData(corporaStructures);

        // Only update selectedGroups if we're using defaults
        if (useDefaults) {
          setSelectedGroups(defaultSelectedGroups);
        }
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError('Failed to load vocabulary data. Please try refreshing the page.');
      } finally {
        setLoading(false);
      }
    };
    loadInitialData();
  }, []);

  // Save settings to localStorage whenever they change
  useEffect(() => {
    safeStorage.setItem('flashcard-selected-groups', JSON.stringify(selectedGroups));
  }, [selectedGroups]);

  useEffect(() => {
    safeStorage.setItem('flashcard-study-mode', studyMode);
  }, [studyMode]);

  useEffect(() => {
    safeStorage.setItem('flashcard-quiz-mode', quizMode);
  }, [quizMode]);

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
      // Always shuffle the cards
      words = words.sort(() => Math.random() - 0.5);
      setAllWords(words);
      setCurrentCard(0);
      setShowAnswer(false);
      setSelectedAnswer(null);
    };
    if (!loading) {
      generateWordsList();
    }
  }, [selectedGroups, loading, corporaData]);

  // Generate multiple choice options when card changes or mode changes
  useEffect(() => {
    if ((quizMode === 'multiple-choice' || quizMode === 'listening') && allWords.length > 0) {
      generateMultipleChoiceOptions();
    }
  }, [currentCard, quizMode, allWords, studyMode, settings.difficulty]);

  // Pre-load audio for multiple choice options when audio is enabled
  useEffect(() => {
    if (audioEnabled && (quizMode === 'multiple-choice' || quizMode === 'listening') && multipleChoiceOptions.length > 0) {
      preloadMultipleChoiceAudio();
    }
  }, [audioEnabled, quizMode, studyMode, multipleChoiceOptions, selectedVoice]);

  // Auto-play audio in listening mode when card changes
  useEffect(() => {
    if (quizMode === 'listening' && audioEnabled && allWords.length > 0 && allWords[currentCard]) {
      // Small delay to ensure the UI has updated
      const timer = setTimeout(() => {
        playAudio(allWords[currentCard].lithuanian);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [currentCard, quizMode, audioEnabled, allWords]);

  // Reload conjugations when verb corpus changes
  useEffect(() => {
    const loadConjugationsForCorpus = async () => {
      if (selectedVerbCorpus && !loading) {
        setLoadingConjugations(true);
        try {
          const conjugationData = await fetchConjugations(selectedVerbCorpus);
          setConjugations(conjugationData.conjugations);
          setAvailableVerbs(conjugationData.verbs);
          // Reset selected verb when corpus changes
          setSelectedVerb(null);
        } catch (error) {
          console.error('Failed to load conjugations for corpus:', selectedVerbCorpus, error);
        } finally {
          setLoadingConjugations(false);
        }
      }
    };
    loadConjugationsForCorpus();
  }, [selectedVerbCorpus, loading]);

  const generateMultipleChoiceOptions = () => {
    const currentWord = allWords[currentCard];
    if (!currentWord) return;

    // For listening mode, determine correct answer based on listening mode type
    let correctAnswer;
    if (quizMode === 'listening') {
      // In listening mode: LT->LT shows Lithuanian options, LT->EN shows English options
      correctAnswer = studyMode === 'lithuanian-to-english' ? currentWord.english : currentWord.lithuanian;
    } else {
      // Regular multiple choice mode
      correctAnswer = studyMode === 'english-to-lithuanian' ? currentWord.lithuanian : currentWord.english;
    }

    // Determine number of options based on difficulty
    const numOptions = settings.difficulty === 'easy' ? 4 : settings.difficulty === 'medium' ? 6 : 8;
    const numWrongAnswers = numOptions - 1;

    // Determine which field to use for filtering and generating wrong answers
    let answerField;
    if (quizMode === 'listening') {
      answerField = studyMode === 'lithuanian-to-english' ? 'english' : 'lithuanian';
    } else {
      answerField = studyMode === 'english-to-lithuanian' ? 'lithuanian' : 'english';
    }

    const sameCorpusWords = allWords.filter(word => 
      word.corpus === currentWord.corpus && 
      word[answerField] !== correctAnswer
    );
    const wrongAnswersSet = new Set();
    const wrongAnswers = [];
    // Gather wrong answers from same corpus - shuffle first to get random decoys
    const shuffledSameCorpusWords = [...sameCorpusWords].sort(() => Math.random() - 0.5);
    for (const word of shuffledSameCorpusWords) {
      const answer = word[answerField];
      if (answer !== correctAnswer && !wrongAnswersSet.has(answer)) {
        wrongAnswersSet.add(answer);
        wrongAnswers.push(answer);
        if (wrongAnswers.length >= numWrongAnswers) break;
      }
    }
    // Pad with any other words if needed
    if (wrongAnswers.length < numWrongAnswers) {
      const fallbackWords = allWords
        .map(w => w[answerField])
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
    await audioManager.preloadMultipleAudio(multipleChoiceOptions, selectedVoice);
  };



  const resetCards = () => {
    setCurrentCard(0);
    setShowAnswer(false);
    setStats({ correct: 0, incorrect: 0, total: 0 });
    setSelectedAnswer(null);
  };

  // Generate all available groups from all corpuses
  useEffect(() => {
    if (Object.keys(corporaData).length === 0) return;
    
    const options = [];
    // Iterate through all corpuses and their groups
    Object.entries(corporaData).forEach(([corpus, data]) => {
      Object.keys(data.groups || {}).forEach(group => {
        options.push({
          corpus,
          group,
          displayName: `${corpus} - ${group}`,
          wordCount: data.groups[group]?.length || 0
        });
      });
    });
    
    // Sort alphabetically by display name
    options.sort((a, b) => a.displayName.localeCompare(b.displayName));
    setVocabGroupOptions(options);
  }, [corporaData]);

  const loadVocabListForGroup = (optionValue) => {
    if (!optionValue) {
      setSelectedVocabGroup(null);
      setVocabListWords([]);
      return;
    }
    
    // Parse the combined value to get corpus and group
    const [corpus, group] = optionValue.split('|');
    if (!corpus || !group || !corporaData[corpus]?.groups[group]) return;
    
    setSelectedVocabGroup(optionValue);
    
    // Get words for this specific group
    const words = corporaData[corpus].groups[group].map(word => ({
      ...word,
      corpus,
      group
    }));
    
    // Sort alphabetically by Lithuanian word
    words.sort((a, b) => a.lithuanian.localeCompare(b.lithuanian));
    setVocabListWords(words);
  };

  const resetAllSettings = () => {
    // Clear localStorage items
    safeStorage.removeItem('flashcard-selected-groups');
    safeStorage.removeItem('flashcard-study-mode');
    safeStorage.removeItem('flashcard-quiz-mode');

    // Reset state to defaults
    setStudyMode('english-to-lithuanian');
    setQuizMode('flashcard');

    // For corpus groups, we need to reset to all groups
    const defaultSelectedGroups = {};
    Object.keys(corporaData).forEach(corpus => {
      defaultSelectedGroups[corpus] = Object.keys(corporaData[corpus]?.groups || {});
    });
    setSelectedGroups(defaultSelectedGroups);
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
    let correctAnswer;
    if (quizMode === 'listening') {
      // In listening mode: LT->EN shows English options, LT->LT shows Lithuanian options
      correctAnswer = studyMode === 'lithuanian-to-english' ? currentWord.english : currentWord.lithuanian;
    } else {
      // Regular multiple choice mode
      correctAnswer = studyMode === 'english-to-lithuanian' ? currentWord.lithuanian : currentWord.english;
    }
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

  const playAudio = async (word, onlyCached = false) => {
    audioManager.playAudio(word, selectedVoice, audioEnabled, onlyCached);
  };

  const handleHoverStart = (word) => {
    if (!audioEnabled || !selectedVoice) return;
    const timeout = setTimeout(() => {
      playAudio(word, onlyCached =true); // Only play if cached
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
      safeStorage.setItem('flashcard-selected-groups', JSON.stringify({...prev, [corpus]: newGroups}));
      return { ...prev, [corpus]: newGroups };
    });
  };

  const toggleCorpus = (corpus) => {
    setSelectedGroups(prev => {
      const allGroups = Object.keys(corporaData[corpus]?.groups || {});
      const currentGroups = prev[corpus] || [];
      const allSelected = allGroups.length > 0 && allGroups.every(g => currentGroups.includes(g));
      const newGroups = allSelected ? [] : allGroups;
      safeStorage.setItem('flashcard-selected-groups', JSON.stringify({...prev, [corpus]: newGroups}));
      return {
        ...prev,
        [corpus]: newGroups
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
                    <AudioButton 
                      word={conj.lithuanian}
                      size="small"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  // Render declension table
  const renderDeclensionTable = (noun) => {
    const nounData = declensions[noun];
    if (!nounData) return null;

    const cases = ['nominative', 'genitive', 'dative', 'accusative', 'instrumental', 'locative', 'vocative'];

    return (
      <div style={{ marginTop: 'var(--spacing-base)' }}>
        <h4>Declension Table for "{noun}" ({nounData.english})</h4>
        <div style={{ 
          fontSize: '0.9rem', 
          color: 'var(--color-text-muted)', 
          marginBottom: 'var(--spacing-small)' 
        }}>
          Gender: {nounData.gender} | Type: {nounData.declension_type}
        </div>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          border: '1px solid var(--color-border)',
          marginTop: 'var(--spacing-small)'
        }}>
          <thead>
            <tr style={{ background: 'var(--color-annotation-bg)' }}>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Case</th>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Question</th>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Form</th>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Example</th>
              <th style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)' }}>Audio</th>
            </tr>
          </thead>
          <tbody>
            {cases.map(caseName => {
              const caseData = nounData.cases[caseName];
              if (!caseData) return null;
              return (
                <tr key={caseName}>
                  <td style={{ 
                    padding: 'var(--spacing-small)', 
                    border: '1px solid var(--color-border)', 
                    fontWeight: 'bold',
                    textTransform: 'capitalize'
                  }}>
                    {caseName}
                  </td>
                  <td style={{ 
                    padding: 'var(--spacing-small)', 
                    border: '1px solid var(--color-border)',
                    fontSize: '0.85rem',
                    fontStyle: 'italic'
                  }}>
                    {caseData.question}
                  </td>
                  <td style={{ 
                    padding: 'var(--spacing-small)', 
                    border: '1px solid var(--color-border)',
                    fontWeight: 'bold',
                    cursor: audioEnabled ? 'pointer' : 'default'
                  }}
                  onMouseEnter={() => audioEnabled && handleHoverStart(caseData.form)}
                  onMouseLeave={handleHoverEnd}
                  >
                    {caseData.form}
                  </td>
                  <td style={{ 
                    padding: 'var(--spacing-small)', 
                    border: '1px solid var(--color-border)',
                    fontSize: '0.9rem'
                  }}>
                    <div style={{ marginBottom: '2px' }}>
                      <strong>LT:</strong> {caseData.sentence_lithuanian}
                    </div>
                    <div style={{ color: 'var(--color-text-muted)' }}>
                      <strong>EN:</strong> {caseData.sentence_english}
                    </div>
                  </td>
                  <td style={{ padding: 'var(--spacing-small)', border: '1px solid var(--color-border)', textAlign: 'center' }}>
                    <AudioButton 
                      word={caseData.form}
                      size="small"
                    />
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
          <div className="w-text-center w-mb-large">
            <div className="w-question w-mb-large">Loading vocabulary data...</div>
            <div className="w-stat-label">This may take a moment</div>
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
          <div className="w-text-center w-mb-large">
            <div className="w-feedback w-error">⚠️ Error</div>
            <div className="w-mb-large">{error}</div>
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
            className="w-game-header"
            style={{ 
              cursor: 'pointer', 
              marginBottom: showCorpora ? 'var(--spacing-base)' : '0'
            }}
            onClick={() => setShowCorpora(!showCorpora)}
          >
            <h3>Study Materials ({totalSelectedWords} words selected)</h3>
            <button className="w-button-secondary">
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
        {!isFullscreen && <h3>Study Options:</h3>}
        <div className="w-dropdown-container" style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '0.5rem',
          margin: '0 0.5rem'
        }}>
          <label style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>Mode:</label>
          <select 
            style={{
              padding: '0.5rem',
              borderRadius: 'var(--border-radius)',
              border: '1px solid var(--color-border)',
              background: 'var(--color-card-bg)',
              minHeight: '44px',
              cursor: 'pointer',
              fontSize: '0.9rem'
            }}
            value={quizMode === 'conjugations' || quizMode === 'declensions' ? 'grammar' : quizMode}
            onChange={(e) => {
              const selectedMode = e.target.value;
              if (selectedMode === 'grammar') {
                setQuizMode(grammarMode);
              } else {
                setQuizMode(selectedMode);
              }
              safeStorage.setItem('flashcard-quiz-mode', selectedMode === 'grammar' ? grammarMode : selectedMode);
            }}
          >
            <option value="flashcard">Flash Cards</option>
            <option value="multiple-choice">Multiple Choice</option>
            <option value="listening">🎧 Listening</option>
            <option value="vocabulary-list">📑 Vocabulary List</option>
            <option value="grammar">Grammar</option>
          </select>
        </div>

        <div className="w-dropdown-container" style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '0.5rem',
          margin: '0 0.5rem'
        }}>
          <label style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>
            {(quizMode === 'conjugations' || quizMode === 'declensions') ? 'Grammar Type:' : 'Direction:'}
          </label>
          {(quizMode === 'conjugations' || quizMode === 'declensions') ? (
            <select 
              style={{
                padding: '0.5rem',
                borderRadius: 'var(--border-radius)',
                border: '1px solid var(--color-border)',
                background: 'var(--color-card-bg)',
                minHeight: '44px',
                cursor: 'pointer',
                fontSize: '0.9rem'
              }}
              value={quizMode}
              onChange={(e) => {
                const selectedGrammarMode = e.target.value;
                setQuizMode(selectedGrammarMode);
                setGrammarMode(selectedGrammarMode);
                safeStorage.setItem('flashcard-quiz-mode', selectedGrammarMode);
              }}
            >
              <option value="conjugations">📖 Conjugations</option>
              <option value="declensions">📋 Declensions</option>
            </select>
          ) : (
            <select 
              style={{
                padding: '0.5rem',
                borderRadius: 'var(--border-radius)',
                border: '1px solid var(--color-border)',
                background: 'var(--color-card-bg)',
                minHeight: '44px',
                cursor: 'pointer',
                fontSize: '0.9rem'
              }}
              value={studyMode}
              onChange={(e) => {
                setStudyMode(e.target.value);
                safeStorage.setItem('flashcard-study-mode', e.target.value);
              }}
            >
              <option value="english-to-lithuanian">English → Lithuanian</option>
              <option value="lithuanian-to-english">Lithuanian → English</option>
            </select>
          )}
        </div>

        <button
          className="w-mode-option"
          onClick={resetAllSettings}
          title="Reset all local settings including selected corpuses"
        >
          🔄 Reset Local Settings
        </button>
        <SettingsToggle className="w-mode-option">
          ⚙️ Settings
        </SettingsToggle>
        {audioEnabled && availableVoices.length > 0 && (
          <select 
            value={selectedVoice || ''} 
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="w-mode-option"
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
        </div>
      )}

      {showNoGroupsMessage ? (
        <div className="w-card">
          <div className="w-text-center w-mb-large">
            <div className="w-question w-mb-large">📭 No Words Available</div>
            <div>No vocabulary words found for the selected groups. Please try selecting different groups.</div>
          </div>
        </div>
      ) : quizMode === 'conjugations' ? (
        <div className="w-card">
          <h3>Lithuanian Verb Conjugations</h3>

          {/* Corpus selector */}
          <div style={{ marginBottom: 'var(--spacing-base)' }}>
            <label htmlFor="corpus-select" style={{ marginRight: 'var(--spacing-small)' }}>
              Verb tense:
            </label>
            <select 
              id="corpus-select"
              value={selectedVerbCorpus} 
              onChange={(e) => setSelectedVerbCorpus(e.target.value)}
              disabled={loadingConjugations}
              className="w-mode-option"
              style={{ minWidth: '150px', marginRight: 'var(--spacing-base)' }}
            >
              {availableVerbCorpuses.map(corpus => (
                <option key={corpus} value={corpus}>
                  {corpus === 'verbs_present' ? 'Present Tense' : 
                   corpus === 'verbs_past' ? 'Past Tense' : 
                   corpus.replace('verbs_', '').replace('_', ' ')}
                </option>
              ))}
            </select>
            {loadingConjugations && <span style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>Loading...</span>}
          </div>

          {/* Verb selector */}
          <div style={{ marginBottom: 'var(--spacing-base)' }}>
            <label htmlFor="verb-select" style={{ marginRight: 'var(--spacing-small)' }}>
              Select a verb:
            </label>
            <select 
              id="verb-select"
              value={selectedVerb || ''} 
              onChange={(e) => setSelectedVerb(e.target.value)}
              disabled={loadingConjugations || availableVerbs.length === 0}
              className="w-mode-option"
              style={{ minWidth: '150px' }}
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
      ) : quizMode === 'declensions' ? (
        <div className="w-card">
          <h3>Lithuanian Noun Declensions</h3>
          <div style={{ marginBottom: 'var(--spacing-base)' }}>
            <label htmlFor="noun-select" style={{ marginRight: 'var(--spacing-small)' }}>
              Select a noun:
            </label>
            <select 
              id="noun-select"
              value={selectedNoun || ''} 
              onChange={(e) => setSelectedNoun(e.target.value)}
              className="w-mode-option"
              style={{ minWidth: '150px' }}
            >
              <option value="">Choose a noun...</option>
              {availableNouns.map(noun => (
                <option key={noun} value={noun}>
                  {noun} ({declensions[noun]?.english || ''})
                </option>
              ))}
            </select>
          </div>
          {selectedNoun && renderDeclensionTable(selectedNoun)}
        </div>
      ) : quizMode === 'vocabulary-list' ? (
        <div className="w-card">
          <h3>Lithuanian Vocabulary List</h3>
          <div style={{ marginBottom: 'var(--spacing-base)' }}>
            <label htmlFor="group-select" style={{ marginRight: 'var(--spacing-small)' }}>
              Select a vocabulary group:
            </label>
            <select
              id="group-select"
              value={selectedVocabGroup || ''}
              onChange={(e) => loadVocabListForGroup(e.target.value)}
              className="w-mode-option"
              style={{ minWidth: '250px' }}
            >
              <option value="">-- Select Group --</option>
              {vocabGroupOptions.map(option => (
                <option key={`${option.corpus}|${option.group}`} value={`${option.corpus}|${option.group}`}>
                  {option.displayName} ({option.wordCount} words)
                </option>
              ))}
            </select>
          </div>
          
          {selectedVocabGroup && (
            <div>
              <h4>{vocabListWords.length} Words</h4>
              <div style={{ 
                maxHeight: '60vh', 
                overflowY: 'auto',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--border-radius)',
                padding: 'var(--spacing-small)'
              }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ 
                        padding: 'var(--spacing-small)', 
                        borderBottom: '2px solid var(--color-border)',
                        textAlign: 'left',
                        position: 'sticky',
                        top: 0,
                        background: 'var(--color-card-bg)'
                      }}>Lithuanian</th>
                      <th style={{ 
                        padding: 'var(--spacing-small)', 
                        borderBottom: '2px solid var(--color-border)',
                        textAlign: 'left',
                        position: 'sticky',
                        top: 0,
                        background: 'var(--color-card-bg)'
                      }}>English</th>
                      <th style={{ 
                        padding: 'var(--spacing-small)', 
                        borderBottom: '2px solid var(--color-border)',
                        textAlign: 'center',
                        width: '60px',
                        position: 'sticky',
                        top: 0,
                        background: 'var(--color-card-bg)'
                      }}>Audio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vocabListWords.map((word, index) => (
                      <tr key={index} style={{ 
                        backgroundColor: index % 2 === 0 ? 'var(--color-card-bg)' : 'var(--color-card-bg-alt)' 
                      }}>
                        <td style={{ padding: 'var(--spacing-small)', borderBottom: '1px solid var(--color-border)' }}>
                          {word.lithuanian}
                        </td>
                        <td style={{ padding: 'var(--spacing-small)', borderBottom: '1px solid var(--color-border)' }}>
                          {word.english}
                        </td>
                        <td style={{ 
                          padding: 'var(--spacing-small)', 
                          borderBottom: '1px solid var(--color-border)',
                          textAlign: 'center'
                        }}>
                          <AudioButton 
                            word={word.lithuanian}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
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
              <AudioButton 
                word={currentWord.lithuanian}
              />
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
      ) : quizMode === 'listening' && currentWord ? (
        <div>
          <div className="w-card">
            <div className="w-badge">{currentWord.corpus} → {currentWord.group}</div>
            <div className="w-question w-text-center">
              <div className="w-mb-large">
                🎧 Listen and choose the correct answer:
              </div>
              <div style={{ marginBottom: 'var(--spacing-base)' }}>
                <AudioButton 
                  word={currentWord.lithuanian}
                  size="large"
                />
                <span style={{ marginLeft: '0.5rem', fontSize: '1.2rem' }}>Play Audio</span>
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)' }}>
                {studyMode === 'lithuanian-to-english' 
                  ? 'Choose the English translation:'
                  : 'Choose the matching Lithuanian word:'}
              </div>
            </div>
          </div>
          <div className="w-multiple-choice">
            {multipleChoiceOptions.map((option, index) => {
              const currentWord = allWords[currentCard];
              if (!currentWord) return null;
              const correctAnswer = studyMode === 'lithuanian-to-english' ? currentWord.english : currentWord.lithuanian;
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

              // Find the translation for any answer when showAnswer is true
              let translation = null;
              if (showAnswer) {
                if (isCorrect) {
                  // For correct answer, show the opposite translation
                  translation = studyMode === 'lithuanian-to-english' ? currentWord.lithuanian : currentWord.english;
                } else {
                  // For incorrect answers, find the word that matches this option
                  const wrongWord = allWords.find(w => 
                    (studyMode === 'lithuanian-to-english' ? w.english : w.lithuanian) === option
                  );
                  if (wrongWord) {
                    translation = studyMode === 'lithuanian-to-english' ? wrongWord.lithuanian : wrongWord.english;
                  }
                }
              }

              return (
                <button
                  key={index}
                  className={className}
                  onClick={() => !showAnswer && handleMultipleChoiceAnswer(option)}
                  disabled={showAnswer}
                >
                  <div className="choice-content">
                    <div style={{ textAlign: 'center' }}>
                      <span>{option}</span>
                      {translation && showAnswer && (
                        <div style={{ fontSize: '0.8rem', color: (isCorrect || isSelected) ? 'rgba(255,255,255,0.8)' : 'var(--color-text-secondary)', marginTop: '4px' }}>
                          ({translation})
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
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
              // Use same logic as handleMultipleChoiceAnswer for consistency
              let correctAnswer;
              if (quizMode === 'listening') {
                correctAnswer = studyMode === 'lithuanian-to-english' ? currentWord.english : currentWord.lithuanian;
              } else {
                correctAnswer = studyMode === 'english-to-lithuanian' ? currentWord.lithuanian : currentWord.english;
              }
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
                    {showAnswer && isCorrect && (
                      <div style={{ display: 'inline-block', marginLeft: '8px' }}>
                        <AudioButton 
                          word={studyMode === 'english-to-lithuanian' ? option : currentWord.lithuanian}
                        />
                      </div>
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
      {!showNoGroupsMessage && quizMode !== 'conjugations' && quizMode !== 'declensions' && (
        <div className="w-nav-controls">
          <button className="w-button" onClick={prevCard}>← Previous</button>
          <div className="w-nav-center"></div>
          <button className="w-button" onClick={nextCard}>Next →</button>
        </div>
      )}

      {/* Stats with Reset button */}
      {!showNoGroupsMessage && quizMode !== 'conjugations' && quizMode !== 'declensions' && (
        <div className="w-stats">
          <div className="w-stat-item">
            <div className="w-stat-value" style={{ color: 'var(--color-success)' }}>
              {stats.correct}
            </div>
            <div className="w-stat-label">Correct</div>
          </div>
          <div className="w-stat-item">
            <div className="w-stat-value" style={{ color: 'var(--color-error)' }}>
              {stats.incorrect}
            </div>
            <div className="w-stat-label">Incorrect</div>
          </div>
          <div className="w-stat-item">
            <div className="w-stat-value">
              {stats.total > 0 ? Math.round((stats.correct / stats.total) * 100) : 0}%
            </div>
            <div className="w-stat-label">Accuracy</div>
          </div>
          <button 
            className="w-button-secondary" 
            onClick={resetCards}
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
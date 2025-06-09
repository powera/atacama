// API configuration
const API_BASE = '/api/lithuanian';

// API helper functions
export const fetchCorpora = async () => {
  const response = await fetch(`${API_BASE}/wordlists`);
  if (!response.ok) throw new Error('Failed to fetch corpora');
  const data = await response.json();
  return data.corpora;
};

export const fetchCorpusStructure = async (corpus) => {
  const response = await fetch(`${API_BASE}/wordlists/${encodeURIComponent(corpus)}`);
  if (!response.ok) throw new Error(`Failed to fetch structure for corpus: ${corpus}`);
  const data = await response.json();
  return data;
};

export const fetchAvailableVoices = async () => {
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

export const fetchVerbCorpuses = async () => {
  try {
    const response = await fetch(`${API_BASE}/conjugations/corpuses`);
    if (!response.ok) throw new Error('Failed to fetch verb corpuses');
    const data = await response.json();
    return data.verb_corpuses;
  } catch (error) {
    console.warn('Failed to fetch verb corpuses:', error);
    return ['verbs_present']; // fallback to default
  }
};

export const fetchConjugations = async (corpus = 'verbs_present') => {
  try {
    const response = await fetch(`${API_BASE}/conjugations?corpus=${encodeURIComponent(corpus)}`);
    if (!response.ok) throw new Error('Failed to fetch conjugations');
    const data = await response.json();
    return data;
  } catch (error) {
    console.warn('Failed to fetch conjugations:', error);
    return { conjugations: {}, verbs: [], corpus };
  }
};

export const fetchDeclensions = async () => {
  try {
    const response = await fetch(`${API_BASE}/declensions`);
    if (!response.ok) throw new Error('Failed to fetch declensions');
    const data = await response.json();
    return data;
  } catch (error) {
    console.warn('Failed to fetch declensions:', error);
    return { declensions: {}, available_nouns: [] };
  }
};

// Audio functionality
export const getAudioUrl = (word, voice) => {
  return `${API_BASE}/audio/${encodeURIComponent(word)}${voice ? `?voice=${encodeURIComponent(voice)}` : ''}`;
};

// Audio utility functions
export class AudioManager {
  constructor() {
    this.audioCache = {};
  }

  async playAudio(word, voice, audioEnabled = true, onlyCached = false) {
    if (!audioEnabled) return;
    
    try {
      const cacheKey = `${word}-${voice}`;
      
      if (this.audioCache[cacheKey]) {
        const audio = this.audioCache[cacheKey].cloneNode();
        await audio.play();
        return;
      }
      
      // If onlyCached is true, don't fetch new audio
      if (onlyCached) {
        return;
      }
      
      const audioUrl = getAudioUrl(word, voice);
      const audio = new Audio(audioUrl);
      this.audioCache[cacheKey] = audio;
      await audio.play();
    } catch (error) {
      console.warn(`Failed to play audio for: ${word}`, error);
    }
  }

  async preloadAudio(word, voice) {
    try {
      const cacheKey = `${word}-${voice}`;
      if (!this.audioCache[cacheKey]) {
        const audioUrl = getAudioUrl(word, voice);
        const audio = new Audio(audioUrl);
        await new Promise((resolve, reject) => {
          audio.addEventListener('canplaythrough', resolve);
          audio.addEventListener('error', reject);
          audio.load();
        });
        this.audioCache[cacheKey] = audio;
      }
      return true;
    } catch (error) {
      console.warn(`Failed to preload audio for: ${word}`, error);
      return false;
    }
  }

  async preloadMultipleAudio(options, voice) {
    const promises = options.map(option => this.preloadAudio(option, voice));
    return Promise.allSettled(promises);
  }

  getCache() {
    return this.audioCache;
  }

  hasInCache(word, voice) {
    const cacheKey = `${word}-${voice}`;
    return !!this.audioCache[cacheKey];
  }
}

// Make API_BASE available for other potential usages
export const getApiBase = () => API_BASE;
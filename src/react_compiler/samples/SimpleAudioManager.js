// Simple AudioManager that fetches audio from trakaido.com
// Replaces the Lithuanian API AudioManager

class SimpleAudioManager {
  constructor() {
    this.audioCache = new Map();
    this.baseUrl = 'https://trakaido.com/audio';
  }

  // Generate audio URL for a Lithuanian word
  getAudioUrl(word, voice = null) {
    // Clean the word for URL (remove spaces, special characters)
    const cleanWord = word.toLowerCase().replace(/[^a-ząčęėįšųūž]/g, '');
    const voiceParam = voice ? `?voice=${voice.id}` : '';
    return `${this.baseUrl}/${cleanWord}.mp3${voiceParam}`;
  }

  // Play audio for a word
  async playAudio(word, voice = null, audioEnabled = true, onlyCached = false) {
    if (!audioEnabled || !word) return;

    try {
      // Check cache first
      const cacheKey = `${word}_${voice?.id || 'default'}`;
      
      if (onlyCached && !this.audioCache.has(cacheKey)) {
        return; // Don't play if not cached and onlyCached is true
      }

      let audio;
      if (this.audioCache.has(cacheKey)) {
        audio = this.audioCache.get(cacheKey);
      } else {
        if (onlyCached) return; // Don't create new audio if onlyCached
        
        const audioUrl = this.getAudioUrl(word, voice);
        audio = new Audio(audioUrl);
        
        // Cache the audio object
        this.audioCache.set(cacheKey, audio);
        
        // Handle loading errors gracefully
        audio.onerror = () => {
          console.warn(`Failed to load audio for word: ${word}`);
        };
      }

      // Reset audio to beginning and play
      audio.currentTime = 0;
      await audio.play();
    } catch (error) {
      console.warn(`Error playing audio for word "${word}":`, error);
    }
  }

  // Preload multiple audio files
  async preloadMultipleAudio(words, voice = null) {
    if (!words || !Array.isArray(words)) return;

    const preloadPromises = words.map(async (word) => {
      try {
        const cacheKey = `${word}_${voice?.id || 'default'}`;
        if (!this.audioCache.has(cacheKey)) {
          const audioUrl = this.getAudioUrl(word, voice);
          const audio = new Audio(audioUrl);
          
          // Preload the audio
          audio.preload = 'auto';
          this.audioCache.set(cacheKey, audio);
          
          // Return a promise that resolves when audio can play
          return new Promise((resolve) => {
            audio.addEventListener('canplaythrough', resolve, { once: true });
            audio.addEventListener('error', resolve, { once: true }); // Resolve even on error
          });
        }
      } catch (error) {
        console.warn(`Error preloading audio for word "${word}":`, error);
      }
    });

    // Wait for all preloads to complete (or fail)
    await Promise.allSettled(preloadPromises);
  }

  // Clear audio cache
  clearCache() {
    this.audioCache.clear();
  }
}

export default SimpleAudioManager;
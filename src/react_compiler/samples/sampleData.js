// Sample Lithuanian vocabulary data for the flashcard app
// This is a subset of the full Trakaido wordlists for demonstration purposes

export const sampleVocabulary = {
  "level_1": {
    "Food & Drink": [
      { english: "water", lithuanian: "vanduo", guid: "N06_002" },
      { english: "bread", lithuanian: "duona", guid: "N06_001" },
      { english: "coffee", lithuanian: "kava", guid: "N06_003" },
      { english: "milk", lithuanian: "pienas", guid: "N06_004" },
      { english: "tea", lithuanian: "arbata", guid: "N06_005" },
      { english: "beer", lithuanian: "alus", guid: "N06_006" },
      { english: "wine", lithuanian: "vynas", guid: "N06_007" },
      { english: "juice", lithuanian: "sultys", guid: "N06_012" },
      { english: "soup", lithuanian: "sriuba", guid: "N06_013" },
      { english: "meat", lithuanian: "mėsa", guid: "N06_014" }
    ],
    "Clothing": [
      { english: "shirt", lithuanian: "marškiniai", guid: "N09_001" },
      { english: "pants", lithuanian: "kelnės", guid: "N09_002" },
      { english: "dress", lithuanian: "suknelė", guid: "N09_003" },
      { english: "shoes", lithuanian: "batai", guid: "N09_005" },
      { english: "hat", lithuanian: "kepurė", guid: "N09_006" },
      { english: "coat", lithuanian: "paltas", guid: "N09_007" },
      { english: "socks", lithuanian: "kojinės", guid: "N09_008" },
      { english: "gloves", lithuanian: "pirštinės", guid: "N09_009" },
      { english: "scarf", lithuanian: "šalikas", guid: "N09_011" },
      { english: "jacket", lithuanian: "striukė", guid: "N09_012" }
    ],
    "Home & Building": [
      { english: "house", lithuanian: "namas", guid: "N07_001" },
      { english: "door", lithuanian: "durys", guid: "N07_002" },
      { english: "window", lithuanian: "langas", guid: "N07_003" },
      { english: "room", lithuanian: "kambarys", guid: "N07_005" },
      { english: "kitchen", lithuanian: "virtuvė", guid: "N07_006" },
      { english: "bathroom", lithuanian: "vonios kambarys", guid: "N07_007" },
      { english: "bedroom", lithuanian: "miegamasis", guid: "N07_008" },
      { english: "living room", lithuanian: "svetainė", guid: "N07_009" },
      { english: "garden", lithuanian: "sodas", guid: "N07_010" },
      { english: "garage", lithuanian: "garažas", guid: "N07_011" }
    ]
  },
  "level_2": {
    "Family": [
      { english: "mother", lithuanian: "mama", guid: "N01_001" },
      { english: "father", lithuanian: "tėvas", guid: "N01_002" },
      { english: "son", lithuanian: "sūnus", guid: "N01_003" },
      { english: "daughter", lithuanian: "dukra", guid: "N01_004" },
      { english: "brother", lithuanian: "brolis", guid: "N01_005" },
      { english: "sister", lithuanian: "sesuo", guid: "N01_006" },
      { english: "grandmother", lithuanian: "močiutė", guid: "N01_007" },
      { english: "grandfather", lithuanian: "senelis", guid: "N01_008" },
      { english: "uncle", lithuanian: "dėdė", guid: "N01_009" },
      { english: "aunt", lithuanian: "teta", guid: "N01_010" }
    ],
    "Colors": [
      { english: "red", lithuanian: "raudonas", guid: "N05_001" },
      { english: "blue", lithuanian: "mėlynas", guid: "N05_002" },
      { english: "green", lithuanian: "žalias", guid: "N05_003" },
      { english: "yellow", lithuanian: "geltonas", guid: "N05_004" },
      { english: "black", lithuanian: "juodas", guid: "N05_005" },
      { english: "white", lithuanian: "baltas", guid: "N05_006" },
      { english: "brown", lithuanian: "rudas", guid: "N05_007" },
      { english: "orange", lithuanian: "oranžinis", guid: "N05_008" },
      { english: "purple", lithuanian: "violetinis", guid: "N05_009" },
      { english: "pink", lithuanian: "rožinis", guid: "N05_010" }
    ]
  }
};

export const sampleVerbs = {
  "verbs_present": {
    "Basic Actions": [
      { english: "I eat", lithuanian: "aš valgau", guid: "V01_001" },
      { english: "you eat", lithuanian: "tu valgai", guid: "V01_002" },
      { english: "he/she eats", lithuanian: "jis/ji valgo", guid: "V01_003" },
      { english: "I drink", lithuanian: "aš geriu", guid: "V02_001" },
      { english: "you drink", lithuanian: "tu geri", guid: "V02_002" },
      { english: "he/she drinks", lithuanian: "jis/ji geria", guid: "V02_003" },
      { english: "I live", lithuanian: "aš gyvenu", guid: "V03_001" },
      { english: "you live", lithuanian: "tu gyveni", guid: "V03_002" },
      { english: "he/she lives", lithuanian: "jis/ji gyvena", guid: "V03_003" },
      { english: "I learn", lithuanian: "aš mokausi", guid: "V04_001" }
    ]
  }
};

export const samplePhrases = {
  "phrases_one": {
    "Greetings": [
      { english: "Hello", lithuanian: "Labas", guid: "P01_001" },
      { english: "Good morning", lithuanian: "Labas rytas", guid: "P01_002" },
      { english: "Good evening", lithuanian: "Labas vakaras", guid: "P01_003" },
      { english: "Goodbye", lithuanian: "Viso gero", guid: "P01_004" },
      { english: "Thank you", lithuanian: "Ačiū", guid: "P01_005" },
      { english: "Please", lithuanian: "Prašau", guid: "P01_006" },
      { english: "Excuse me", lithuanian: "Atsiprašau", guid: "P01_007" },
      { english: "Yes", lithuanian: "Taip", guid: "P01_008" },
      { english: "No", lithuanian: "Ne", guid: "P01_009" },
      { english: "How are you?", lithuanian: "Kaip sekasi?", guid: "P01_010" }
    ]
  }
};

// Available corpora list
export const availableCorpora = ["level_1", "level_2", "verbs_present", "phrases_one"];

// Available voices (mock data)
export const availableVoices = [
  { id: "lt-female-1", name: "Lithuanian Female", language: "lt" },
  { id: "lt-male-1", name: "Lithuanian Male", language: "lt" }
];

// Verb corpora list
export const availableVerbCorpora = ["verbs_present"];

// Mock conjugations data
export const conjugationsData = {
  conjugations: {
    "valgyti": {
      "english": "to eat",
      "present_tense": {
        "1s": { "english": "I eat", "lithuanian": "aš valgau" },
        "2s": { "english": "you eat", "lithuanian": "tu valgai" },
        "3s": { "english": "he/she eats", "lithuanian": "jis/ji valgo" }
      }
    }
  },
  verbs: ["valgyti"]
};

// Mock declensions data
export const declensionsData = {
  declensions: {},
  available_nouns: []
};
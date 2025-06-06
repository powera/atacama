#!/usr/bin/python3

"""
Lithuanian noun declensions for Trakaido language learning app.

This module contains complete declension data for 10 Lithuanian nouns
across all 7 cases (nominative, genitive, dative, accusative, 
instrumental, locative, vocative) with example sentences.

Structure:
- Each noun has entries for all 7 cases
- Each entry includes the declined form and an example sentence
- All nouns are chosen to work naturally in vocative case
- Covers different declension patterns and common vocabulary
"""

# Lithuanian noun declensions with example sentences
declensions = {
    "brolis": {
        "english": "brother",
        "gender": "masculine",
        "declension_type": "3rd (consonant stem)",
        "cases": {
            "nominative": {
                "form": "brolis",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Brolis grįžta namo.",
                "sentence_english": "The brother is returning home."
            },
            "genitive": {
                "form": "brolio",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai brolio knyga.",
                "sentence_english": "This is the brother's book."
            },
            "dative": {
                "form": "broliui",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Duodu dovaną broliui.",
                "sentence_english": "I give a gift to the brother."
            },
            "accusative": {
                "form": "brolį",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Matau brolį parduotuvėje.",
                "sentence_english": "I see the brother in the store."
            },
            "instrumental": {
                "form": "broliu",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Žaidžiu broliu futbolą.",
                "sentence_english": "I play football with my brother."
            },
            "locative": {
                "form": "brolyje",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Matau gerumą brolyje.",
                "sentence_english": "I see goodness in the brother."
            },
            "vocative": {
                "form": "broli",
                "question": "direct address",
                "sentence_lithuanian": "Broli, ateik čia!",
                "sentence_english": "Brother, come here!"
            }
        }
    },
    
    "sesuo": {
        "english": "sister",
        "gender": "feminine",
        "declension_type": "5th (special)",
        "cases": {
            "nominative": {
                "form": "sesuo",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Sesuo studijuoja universitete.",
                "sentence_english": "The sister studies at university."
            },
            "genitive": {
                "form": "sesers",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai sesers dviratis.",
                "sentence_english": "This is the sister's bicycle."
            },
            "dative": {
                "form": "seseriai",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Skambinu seseriai vakare.",
                "sentence_english": "I call the sister in the evening."
            },
            "accusative": {
                "form": "seserį",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Aplankau seserį ligoninėje.",
                "sentence_english": "I visit the sister in the hospital."
            },
            "instrumental": {
                "form": "seseria",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Keliauju seseria į miestą.",
                "sentence_english": "I travel to the city with my sister."
            },
            "locative": {
                "form": "seseryje",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Randu paguodą seseryje.",
                "sentence_english": "I find comfort in my sister."
            },
            "vocative": {
                "form": "seserie",
                "question": "direct address",
                "sentence_lithuanian": "Seserie, padėk man!",
                "sentence_english": "Sister, help me!"
            }
        }
    },
    
    "mama": {
        "english": "mom",
        "gender": "feminine",
        "declension_type": "1st (-a)",
        "cases": {
            "nominative": {
                "form": "mama",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Mama gamina pietus.",
                "sentence_english": "Mom is making lunch."
            },
            "genitive": {
                "form": "mamos",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai mamos receptas.",
                "sentence_english": "This is mom's recipe."
            },
            "dative": {
                "form": "mamai",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Nupirkau gėlių mamai.",
                "sentence_english": "I bought flowers for mom."
            },
            "accusative": {
                "form": "mamą",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Myliu mamą labai.",
                "sentence_english": "I love mom very much."
            },
            "instrumental": {
                "form": "mama",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Kalbu mama telefonu.",
                "sentence_english": "I talk with mom on the phone."
            },
            "locative": {
                "form": "mamoje",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Jaučiu meilę mamoje.",
                "sentence_english": "I feel love in mom."
            },
            "vocative": {
                "form": "mama",
                "question": "direct address",
                "sentence_lithuanian": "Mama, kur tu?",
                "sentence_english": "Mom, where are you?"
            }
        }
    },
    
    "tėvas": {
        "english": "father",
        "gender": "masculine",
        "declension_type": "1st (-as)",
        "cases": {
            "nominative": {
                "form": "tėvas",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Tėvas dirba biure.",
                "sentence_english": "Dad works in the office."
            },
            "genitive": {
                "form": "tėvo",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai tėvo automobilis.",
                "sentence_english": "This is dad's car."
            },
            "dative": {
                "form": "tėvui",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Pasakoju naujieną tėvui.",
                "sentence_english": "I tell the news to dad."
            },
            "accusative": {
                "form": "tėvą",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Palydžiu tėvą į oro uostą.",
                "sentence_english": "I take dad to the airport."
            },
            "instrumental": {
                "form": "tėvu",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Dirbu sode tėvu.",
                "sentence_english": "I work in the garden with dad."
            },
            "locative": {
                "form": "tėve",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Matau išmintį tėve.",
                "sentence_english": "I see wisdom in dad."
            },
            "vocative": {
                "form": "tėve",
                "question": "direct address",
                "sentence_lithuanian": "Tėve, ar girdite mane?",
                "sentence_english": "Father, do you hear me?"
            }
        }
    },
    
    "draugas": {
        "english": "friend",
        "gender": "masculine",
        "declension_type": "1st (-as)",
        "cases": {
            "nominative": {
                "form": "draugas",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Draugas atvyko iš Vokietijos.",
                "sentence_english": "The friend arrived from Germany."
            },
            "genitive": {
                "form": "draugo",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai draugo namų raktas.",
                "sentence_english": "This is the friend's house key."
            },
            "dative": {
                "form": "draugui",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Rašau laišką draugui.",
                "sentence_english": "I write a letter to the friend."
            },
            "accusative": {
                "form": "draugą",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Sutinku draugą kavinėje.",
                "sentence_english": "I meet the friend at the café."
            },
            "instrumental": {
                "form": "draugu",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Einu į kiną draugu.",
                "sentence_english": "I go to the cinema with the friend."
            },
            "locative": {
                "form": "drauge",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Pasitikiu drauge visada.",
                "sentence_english": "I always trust in the friend."
            },
            "vocative": {
                "form": "drauge",
                "question": "direct address",
                "sentence_lithuanian": "Drauge, kaip sekasi?",
                "sentence_english": "Friend, how are things going?"
            }
        }
    },
    
    "mokytojas": {
        "english": "teacher",
        "gender": "masculine",
        "declension_type": "1st (-jas)",
        "cases": {
            "nominative": {
                "form": "mokytojas",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Mokytojas aiškina temą.",
                "sentence_english": "The teacher explains the topic."
            },
            "genitive": {
                "form": "mokytojo",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai mokytojo kabinetas.",
                "sentence_english": "This is the teacher's office."
            },
            "dative": {
                "form": "mokytojui",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Duodu namų darbus mokytojui.",
                "sentence_english": "I give homework to the teacher."
            },
            "accusative": {
                "form": "mokytoją",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Gerbu mokytoją labai.",
                "sentence_english": "I respect the teacher very much."
            },
            "instrumental": {
                "form": "mokytoju",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Kalbamės mokytoju apie ateities planus.",
                "sentence_english": "We talk with the teacher about future plans."
            },
            "locative": {
                "form": "mokytoje",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Matau autoritetą mokytoje.",
                "sentence_english": "I see authority in the teacher."
            },
            "vocative": {
                "form": "mokytojau",
                "question": "direct address",
                "sentence_lithuanian": "Mokytojau, ar galiu užduoti klausimą?",
                "sentence_english": "Teacher, may I ask a question?"
            }
        }
    },
    
    "katė": {
        "english": "cat",
        "gender": "feminine",
        "declension_type": "2nd (-ė)",
        "cases": {
            "nominative": {
                "form": "katė",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Katė miega ant sofos.",
                "sentence_english": "The cat sleeps on the sofa."
            },
            "genitive": {
                "form": "katės",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai katės maistas.",
                "sentence_english": "This is the cat's food."
            },
            "dative": {
                "form": "katei",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Duodu pieną katei.",
                "sentence_english": "I give milk to the cat."
            },
            "accusative": {
                "form": "katę",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Glostau katę švelniai.",
                "sentence_english": "I pet the cat gently."
            },
            "instrumental": {
                "form": "kate",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Žaidžiu kate namuose.",
                "sentence_english": "I play with the cat at home."
            },
            "locative": {
                "form": "katėje",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Matau ištikimybę katėje.",
                "sentence_english": "I see loyalty in the cat."
            },
            "vocative": {
                "form": "kate",
                "question": "direct address",
                "sentence_lithuanian": "Kate, ateik valgyti!",
                "sentence_english": "Cat, come eat!"
            }
        }
    },
    
    "studentas": {
        "english": "student",
        "gender": "masculine",
        "declension_type": "1st (-as)",
        "cases": {
            "nominative": {
                "form": "studentas",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Studentas rengiasi egzaminui.",
                "sentence_english": "The student prepares for the exam."
            },
            "genitive": {
                "form": "studento",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai studento užrašai.",
                "sentence_english": "These are the student's notes."
            },
            "dative": {
                "form": "studentui",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Dėstytojas duoda patarimą studentui.",
                "sentence_english": "The lecturer gives advice to the student."
            },
            "accusative": {
                "form": "studentą",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Profesorius kviečia studentą į kabinetą.",
                "sentence_english": "The professor invites the student to the office."
            },
            "instrumental": {
                "form": "studentu",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Dirbu projekte studentu.",
                "sentence_english": "I work on the project with the student."
            },
            "locative": {
                "form": "studente",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Matau potencialą studente.",
                "sentence_english": "I see potential in the student."
            },
            "vocative": {
                "form": "studente",
                "question": "direct address",
                "sentence_lithuanian": "Studente, prašau atsakyti į klausimą.",
                "sentence_english": "Student, please answer the question."
            }
        }
    },
    
    "šuo": {
        "english": "dog",
        "gender": "masculine",
        "declension_type": "3rd (irregular)",
        "cases": {
            "nominative": {
                "form": "šuo",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Šuo bėga po kiemu.",
                "sentence_english": "The dog runs around the yard."
            },
            "genitive": {
                "form": "šuns",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai šuns kaulas.",
                "sentence_english": "This is the dog's bone."
            },
            "dative": {
                "form": "šuniui",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Duodu skanėstą šuniui.",
                "sentence_english": "I give a treat to the dog."
            },
            "accusative": {
                "form": "šunį",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Vedžioju šunį parke.",
                "sentence_english": "I walk the dog in the park."
            },
            "instrumental": {
                "form": "šuniu",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Žaidžiu šuniu lauke.",
                "sentence_english": "I play with the dog outside."
            },
            "locative": {
                "form": "šunyje",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Matau ištikimybę šunyje.",
                "sentence_english": "I see loyalty in the dog."
            },
            "vocative": {
                "form": "šunie",
                "question": "direct address",
                "sentence_lithuanian": "Šunie, sėdėk!",
                "sentence_english": "Dog, sit!"
            }
        }
    },
    
    "gydytojas": {
        "english": "doctor",
        "gender": "masculine",
        "declension_type": "1st (-jas)",
        "cases": {
            "nominative": {
                "form": "gydytojas",
                "question": "kas? (who?)",
                "sentence_lithuanian": "Gydytojas tiria pacientą.",
                "sentence_english": "The doctor examines the patient."
            },
            "genitive": {
                "form": "gydytojo",
                "question": "kieno? (whose?)",
                "sentence_lithuanian": "Tai gydytojo receptas.",
                "sentence_english": "This is the doctor's prescription."
            },
            "dative": {
                "form": "gydytojui",
                "question": "kam? (to whom?)",
                "sentence_lithuanian": "Pasakoju simptomus gydytojui.",
                "sentence_english": "I tell the symptoms to the doctor."
            },
            "accusative": {
                "form": "gydytoją",
                "question": "ką? (what/whom?)",
                "sentence_lithuanian": "Lankau gydytoją kas mėnesį.",
                "sentence_english": "I visit the doctor every month."
            },
            "instrumental": {
                "form": "gydytoju",
                "question": "kuo? (with what?)",
                "sentence_lithuanian": "Konsultuojuosi gydytoju dėl ligos.",
                "sentence_english": "I consult with the doctor about the illness."
            },
            "locative": {
                "form": "gydytoje",
                "question": "kur? (where?)",
                "sentence_lithuanian": "Pasitikiu gydytoje visiškai.",
                "sentence_english": "I trust completely in the doctor."
            },
            "vocative": {
                "form": "gydytojau",
                "question": "direct address",
                "sentence_lithuanian": "Gydytojau, kaip aš jaučiuosi?",
                "sentence_english": "Doctor, how am I doing?"
            }
        }
    }
}

# Helper function to get all cases for a noun
def get_noun_declension(noun_key):
    """
    Get complete declension for a specific noun.
    
    Args:
        noun_key (str): The nominative form of the noun (dictionary key)
        
    Returns:
        dict: Complete noun declension data or None if not found
    """
    return declensions.get(noun_key)

# Helper function to get all nouns with a specific case form
def get_nouns_by_case(case_name):
    """
    Get all nouns with their forms for a specific case.
    
    Args:
        case_name (str): Name of the case (nominative, genitive, etc.)
        
    Returns:
        list: List of dictionaries with noun info and case form
    """
    result = []
    for noun_key, noun_data in declensions.items():
        if case_name in noun_data["cases"]:
            case_data = noun_data["cases"][case_name]
            result.append({
                "noun": noun_key,
                "english": noun_data["english"],
                "gender": noun_data["gender"],
                "declension_type": noun_data["declension_type"],
                "form": case_data["form"],
                "question": case_data["question"],
                "sentence_lithuanian": case_data["sentence_lithuanian"],
                "sentence_english": case_data["sentence_english"]
            })
    return result

def get_all_forms():
    """
    Get all declension forms for all nouns.
    
    Returns:
        list: List of dictionaries with all noun forms and their details
    """
    all_forms = []
    for noun_key, noun_data in declensions.items():
        for case_name, case_data in noun_data["cases"].items():
            all_forms.append({
                "noun": noun_key,
                "english": noun_data["english"],
                "gender": noun_data["gender"],
                "declension_type": noun_data["declension_type"],
                "case": case_name,
                "form": case_data["form"],
                "question": case_data["question"],
                "sentence_lithuanian": case_data["sentence_lithuanian"],
                "sentence_english": case_data["sentence_english"]
            })
    return all_forms



# Helper function to get declension statistics
def get_declension_stats():
    """
    Get statistics about the declension data.
    
    Returns:
        dict: Statistics including total nouns, cases, gender distribution, etc.
    """
    total_nouns = len(declensions)
    total_cases = len(list(declensions.values())[0]["cases"]) if declensions else 0
    
    gender_count = {"masculine": 0, "feminine": 0}
    declension_types = {}
    
    for noun_data in declensions.values():
        gender = noun_data["gender"]
        if gender in gender_count:
            gender_count[gender] += 1
            
        decl_type = noun_data["declension_type"]
        declension_types[decl_type] = declension_types.get(decl_type, 0) + 1
    
    return {
        "total_nouns": total_nouns,
        "total_cases": total_cases,
        "total_entries": total_nouns * total_cases,
        "gender_distribution": gender_count,
        "declension_types": declension_types,
        "available_cases": list(list(declensions.values())[0]["cases"].keys()) if declensions else []
    }

# List of all available case names
CASE_NAMES = [
    "nominative", "genitive", "dative", "accusative", 
    "instrumental", "locative", "vocative"
]

# List of all noun keys (nominative forms)
NOUN_KEYS = list(declensions.keys())
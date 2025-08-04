# EP-Mapping Pipeline

Diese Pipeline mappt Einträge aus der Kundendatei auf den EP-Katalog und weist Artikelnummern zu.

## 📁 Struktur

```
EP_mapping/
├── 01_find_similar_entries.py            # Schritt 1: Ähnliche Einträge finden
├── 02_map_ep_headings.py                 # Schritt 2: EP-Überschriften Mapping
├── 03_openai_mapping.py                  # Schritt 3: OpenAI API Mapping
├── 04_article_number_mapping.py          # Schritt 4: Artikelnummer-Mapping
├── run_pipeline.py                       # Master-Skript (führt Schritte 1-4 aus)
├── hierarchy_structure_EP_Katalog.json   # Hierarchie-Struktur für OpenAI Mapping
└── README.md                             # Diese Datei
```

## 🚀 Schnellstart

### Vorbereitung:
```bash
# OpenAI API Key setzen
export OPENAI_API_KEY="your-api-key-here"

# Abhängigkeiten installieren
pip install -r requirements.txt
```

### Vollständige Pipeline ausführen:
```bash
cd EP_mapping
python run_pipeline.py
```


### Ergebnis:
Die finale Kundendatei mit Artikelnummer-Spalte wird in `cvs/kundendatei_final.xlsx` gespeichert.

## 📋 Voraussetzungen

### Erforderliche Dateien:
- `cvs/Kundendatei.xlsx` - Kundendatei mit zu mappenden Einträgen
- `cvs/EP_Katalog_subheadings.xlsx` - EP-Katalog mit Überschriften
- `cvs/EP_Katalog.xlsx` - Vollständiger EP-Katalog
- `hierarchy_structure_EP_Katalog.json` - Hierarchie-Struktur für OpenAI Mapping (im EP_mapping/ Ordner)


### API Keys:
- OpenAI API Key (Umgebungsvariable `OPENAI_API_KEY`)

## 🔄 Pipeline-Schritte

### **1. `01_find_similar_entries.py` - Ähnliche Einträge finden**

**Zweck:** Findet und gruppiert ähnliche/identische Einträge in der Kundendatei, um Redundanz zu reduzieren.

**Wichtige Funktionen:**

- **`__init__()`**: Initialisiert das Sentence Transformer Modell (`T-Systems-onsite/cross-en-de-roberta-sentence-transformer`)
- **`find_similar_entries()`**: 
  - Kombiniert alle Textspalten zu einem String
  - Berechnet Embeddings für alle Einträge
  - Erstellt Ähnlichkeitsmatrix mit Cosinus-Ähnlichkeit
  - **Wichtig:** Setzt Diagonale auf 0 (verhindert Selbst-Mappings)
  - Gruppiert ähnliche Einträge mit Schwellenwert 0.97
  - Repräsentant ist NICHT in der Liste der ähnlichen Indizes enthalten
- **`save_similarity_results()`**: 
  - Speichert `01_similar_groups.json` (für interne Verwendung)
  - Erstellt `01_similarity_grouping.xlsx` (visueller Vergleich)
  - Erstellt `01_similarity_statistics.xlsx` (Statistiken)

**Output:** Reduziert 973 Einträge auf 536 repräsentative Einträge.



### **2. `02_map_ep_headings.py` - EP-Überschriften Mapping**

**Zweck:** Mapped repräsentative Kundendatei-Einträge auf EP-Katalog-Überschriften.

**Wichtige Funktionen:**

- **`load_similarity_results()`**: Lädt `01_similar_groups.json`
- **`create_representative_dataframe()`**: Erstellt DataFrame nur mit repräsentativen Einträgen
- **`map_to_ep_subheadings()`**: 
  - Lädt EP-Überschriften (nur "NG"-Einträge)
  - Vergleicht 3 Kundendatei-Spalten: `["Anlagenausprägung", "EQ-Klasse-Bezeichnung", "EQ-Bezeichnung"]`
  - Gegen EP-Spalte: `"Kurztext / Bezeichnung"`
  - Verwendet Sentence Transformers + Cosinus-Ähnlichkeit
  - Schwellenwert: 0.9
- **`create_reduced_kundendatei()`**: Erstellt verkleinerte Kundendatei mit EP_idx-Spalte
- **`save_ep_mapping_results()`**: 
  - Speichert `02_ep_headings_mapping.json` (interne Mappings)
  - Erstellt `02_ep_mapping_statistics.xlsx` (Statistiken)
  - Erstellt `02_ep_mapping_result.xlsx` (visueller Vergleich)

**Output:** ~18% der repräsentativen Einträge werden auf EP-Überschriften gemappt.



### **3. `03_openai_mapping.py` - OpenAI API Mapping**

**Zweck:** Verwendet OpenAI API um verbleibende unmappte Einträge auf EP-Überschriften zu mappen.

**Wichtige Funktionen:**

- Lädt `hierarchy_structure_EP_Katalog.json` (Fehlerhaftes JSON)
- **`load_or_create_kundendatei_summary()`**: Lädt/erstellt `03_openai_mapping_results.xlsx`
- **`create_kundendatei_summary()`**: 
  - Erstellt Zusammenfassungstexte für alle Kundendatei-Einträge
  - Kombiniert relevante Spalten zu einem aussagekräftigen Text
- **`get_lowest_level_headings()`**: Extrahiert alle niedrigsten Ebenen aus der Hierarchie
- **`create_openai_prompt()`**: Erstellt strukturierten Prompt für GPT-4.1
- **`validate_ep_key()`**: Validiert OpenAI-Antwort gegen EP-Katalog
- **`map_unmapped_entries()`**: 
  - Verwendet OpenAI API für unmappte Einträge
  - Rate Limiting mit `time.sleep()`
  - Speichert Ergebnisse in `03_openai_mapping_results.xlsx`

**Output:** Zusätzliche Mappings für verbleibende Einträge.


### **4. `04_article_number_mapping.py` - Artikelnummer Mapping**

**Zweck:** Findet die besten Artikelnummern für Einträge mit EP-Überschriften.

**Wichtige Funktionen:**

- **`load_previous_results()`**: Lädt `01_similar_groups.json` und `03_openai_mapping_results.xlsx`
- **`extract_ep_group()`**: 
  - Extrahiert Artikelgruppe aus EP-Katalog basierend auf EP_idx
  - Von EP_idx+1 bis zur nächsten "NG"-Überschrift
- **`create_article_comparison_text()`**: Erstellt Vergleichstext für jeden Artikel
- **`create_openai_prompt()`**: Erstellt Prompt für Artikelnummer-Vergleich
- **`find_best_article_match()`**: 
  - Verwendet OpenAI API um beste Artikelnummer zu finden
  - Vergleicht Kundendatei-Zusammenfassung mit EP-Gruppe
- **`create_final_kundendatei()`**: 
  - Erstellt finale Kundendatei mit "Artikelnummer"-Spalte vorne
  - Speichert als `cvs/kundendatei_final.xlsx` und `cvs/kundendatei_final.csv`

**Output:** Finale Kundendatei mit zugeordneten Artikelnummern.



## **Pipeline-Ablauf:**

`../cvs/Kundendatei.xlsx`: 973 Einträge
1. **Schritt 1:** 973 → 536 repräsentative Einträge
2. **Schritt 2:** 536 → 440 ohne EP-Überschriften (Sentence Transformers)
3. **Schritt 3:** 440 → 0 ohne EP-Überschriften (OpenAI API)
4. **Schritt 4:**  → Finale Kundendatei mit Artikelnummern

Jeder Schritt baut auf den Ergebnissen des vorherigen auf und speichert strukturierte Zwischenergebnisse.

## 📊 Ausgabe-Dateien

### Zwischenergebnisse (`intermediate_results/`)
- **01_similar_groups.json**: JSON-Datei mit Ähnlichkeitsgruppen
- **01_similarity_grouping.xlsx**: Gruppierte Einträge mit visueller Vergleich
- **01_similarity_statistics.xlsx**: Statistiken der Ähnlichkeitsgruppen
- **02_ep_headings_mapping.json**: EP-Überschriften Mappings (intern)
- **02_ep_mapping_statistics.xlsx**: EP-Mapping Statistiken
- **02_ep_mapping_result.xlsx**: EP-Mapping Ergebnisse mit visueller Vergleich
- **03_openai_mapping_results.xlsx**: OpenAI Mapping-Ergebnisse

### Finale Ergebnisse (`cvs/`)
- **kundendatei_final.xlsx**: Finale Kundendatei mit Artikelnummer-Spalte
- **kundendatei_final.csv**: CSV-Version der finalen Kundendatei

 
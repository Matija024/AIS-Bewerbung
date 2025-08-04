# Vollständigkeitsprüfung - Erweiterte Analyse

## Übersicht
Dieses System führt eine erweiterte Vollständigkeitsprüfung zwischen einer Kundendatei und einer vollständigen Referenzdatenbank durch. Es kombiniert drei Analysemethoden:

1. **Frequenzanalyse**: Identifiziert "allgemein typische" Installationen
2. **Korrelationsanalyse**: Findet Installationen, die häufig zusammen vorkommen
3. **Text-Ähnlichkeit**: Mappt Kundendatei-Installationen auf Referenz-Installationen

## 📁 Struktur

```
Completeness_check/
├── 01_correlation_matrix.py          # Schritt 1: Korrelationsmatrix erstellen
├── 02_frequency_analysis.py          # Schritt 2: Frequenzanalyse durchführen
├── 03_completeness_check.py          # Schritt 3: Finale Vollständigkeitsprüfung
├── component_analysis.py             # Komponenten-Analyse (unabhängig)
├── run_pipeline.py                   # Master-Skript (führt alle Schritte aus)
└── README.md                         # Diese Datei
```

## Dateien

### Skripte
- `01_correlation_matrix.py` - Erstellt Korrelationsmatrix der Referenzdaten
- `02_frequency_analysis.py` - Führt Frequenzanalyse der Referenzdaten durch
- `03_completeness_check.py` - Hauptskript für die Vollständigkeitsprüfung
- `component_analysis.py` - Analysiert fehlende Komponenten basierend auf Verbandsnummern
- `run_pipeline.py` - Master-Skript
### Output-Dateien
- `01_correlation_matrix.xlsx` - Korrelationsmatrix
- `02_frequency_analysis.xlsx` - Frequenzanalyse-Ergebnisse
- `03_final_results.xlsx` - **Finale zusammengeführte Vorschläge** (mit Komponenten-Priorisierung)
- `component_suggestions.xlsx` - Komponenten-Vorschläge pro Gebäude

## Funktionsweise

### 1. `01_correlation_matrix.py`

### Zweck
Erstellt eine Korrelationsmatrix, die zeigt, welche Installationen häufig zusammen in Gebäuden vorkommen.

### Funktionsweise
1. **Daten laden**: Liest `../cvs/Beispielobjekte.xlsx` (Sheet: "Anlagen")
2. **Daten vorbereiten**: 
   - Gruppiert nach `Gebäude-ID` und `AKS-Bezeichnung`
   - Erstellt One-Hot-Encoding Matrix (1 = Installation vorhanden, 0 = nicht vorhanden)
3. **Korrelation berechnen**: Verwendet pandas `.corr()` für Pearson-Korrelation
4. **Speichern**: Exportiert als `01_correlation_matrix.xlsx`

### Ausgabe
- **01_correlation_matrix.xlsx**: Korrelationsmatrix (113x113 Installationen)

### Beispiel
```
Installation A    Installation B    Korrelation
Heizung           Thermostat        0.85
Aufzug            Notbeleuchtung    0.92
```

### 2. `02_frequency_analysis.py`

### Zweck
Analysiert die Häufigkeit jeder Installation in der Referenzdatenbank.

### Funktionsweise
1. **Daten laden**: Gleiche Quelle wie Schritt 1
2. **Frequenz berechnen**: 
   - Zählt in wie vielen Gebäuden jede Installation vorkommt
   - Berechnet Prozentsatz: `(Anzahl Gebäude mit Installation / Gesamtgebäude) * 100`
3. **Kategorisierung**: 
   - Sehr selten (0-10%)
   - Selten (10-25%)
   - Mittel (25-50%)
   - Häufig (50-75%)
   - Sehr häufig (75-100%)
4. **Speichern**: Exportiert als `02_frequency_analysis.xlsx`

### Beispiel
```
Installation        Anzahl_Gebaeude    Gesamt_Gebaeude    Prozent    Kategorie
Außentür           32                 32                 100.0%     Sehr häufig
Handfeuerlöscher   32                 32                 100.0%     Sehr häufig
Raumbeleuchtung    31                 32                 96.9%      Sehr häufig
```

### 3. `03_completeness_check.py`

### Zweck
Hauptskript der Pipeline - führt die finale Vollständigkeitsprüfung durch.

### Funktionsweise

#### 3.1 Daten laden
- Lädt `01_correlation_matrix.xlsx` und `02_frequency_analysis.xlsx`
- Lädt `../cvs/Beispielobjekte.xlsx` für Referenzmatrix
- Lädt `../cvs/Kundendatei.xlsx` für Kundenanalyse

#### 3.2 Installation Mapping
- **Sentence Transformer**: Verwendet `T-Systems-onsite/cross-en-de-roberta-sentence-transformer`
- **Text-Ähnlichkeit**: Kombiniert `EQ-Klasse-Bezeichnung` + `Anlagenausprägung` aus Kundendatei
- **Cosine Similarity**: Berechnet Ähnlichkeit zwischen Kunden- und Referenzinstallationen
- **Schwellenwert**: 0.7 für Mapping (70% Ähnlichkeit)

#### 3.3 Vorschlagsgenerierung

**Frequenzbasierte Vorschläge:**
- Installationen, die in >80% aller Gebäude vorkommen
- Wahrscheinlichkeit = Prozentsatz / 100

**Korrelationsbasierte Vorschläge:**
- Installationen, die stark mit vorhandenen Installationen korrelieren
- Mindestkorrelation: 0.7
- Wahrscheinlichkeit = Korrelationswert

#### 3.4 Komponenten-Integration
- Lädt `component_analysis_results/component_suggestions.xlsx`
- Priorisiert Komponenten-Vorschläge über andere Vorschläge
- Entfernt Duplikate basierend auf `Verbandsnummer`

#### 3.5 Ausgabe
- **03_final_results.xlsx**: Finale zusammengeführte Vorschläge mit Spalten:
  - `gebaeude_id`: Gebäude-ID
  - `installation`: Vorgeschlagene Installation
  - `probability`: Wahrscheinlichkeit (0-1)
  - `reason`: Grund (frequency/correlation/component)
  - `details`: Detaillierte Begründung
  - `verbandsnummer`: Verbandsnummer der Installation

### Beispiel
```
gebaeude_id    installation        probability    reason        details
28580          Handfeuerlöscher    1.0           frequency     Kommt in 100.0% aller Gebäude vor
28580          Notbeleuchtung      0.92          correlation   Korreliert stark (0.92) mit Aufzug
28580          Thermostat          0.9           component     Belongs to system: Heizung
```

### Bauteil-Analyse (component_analysis.py)
- Erstellt Mapping zwischen Anlagen und ihren Bauteilen basierend auf Verbandsnummern
- Analysiert jedes Gebäude der Kundendatei auf fehlende Bauteile
- Generiert Vorschläge basierend auf Artikelnummer-Matching



### 4. `component_analysis.py`

### Zweck
Separate Analyse für System-Komponenten Beziehungen basierend auf `Verbandsnummern`.

### Funktionsweise

#### 4.1 System-Komponenten Mapping
- **Systeme identifizieren**: Anlagen mit `Verbandsnummer` und `Anlagentyp = 'Anlage'`
- **Komponenten identifizieren**: Bauteile mit `Verbandsnummer` und `Anlagentyp = 'Bauteil'`
- **Beziehungen erstellen**: `Bauteil der Anlage` → `Anlagen-ID`

#### 4.2 Kundenanalyse
- **Artikelnummern finden**: Sucht nach Spalten mit "artikel" oder "verband" im Namen
- **System-Matching**: Vergleicht `Artikelnummer` mit `Verbandsnummer` von Systemen
- **Fehlende Komponenten**: Identifiziert Komponenten, die zum System gehören aber fehlen

#### 4.3 Ausgabe
- **component_analysis_results/component_suggestions.xlsx** mit Sheets:
  - `overview`: Übersicht pro Gebäude
  - `Building_[ID]`: Detaillierte Vorschläge pro Gebäude
  - `all_suggestions`: Alle Vorschläge zusammen

### Beispiel
```
building_id    component        article_number    reason                    probability
28580          Thermostat      12345             Belongs to system: Heizung    0.9
28580          Ventil          12346             Belongs to system: Heizung    0.9
```

## Verwendung

### Vollständige Pipeline ausführen:
```bash
cd Completeness_check
python run_pipeline.py
```

### Einzelne Skripte ausführen:
```bash
# 1. Korrelationsmatrix erstellen
python 01_correlation_matrix.py

# 2. Frequenzanalyse durchführen
python 02_frequency_analysis.py

# 3. Komponenten-Analyse (optional)
python component_analysis.py

# 4. Finale Vollständigkeitsprüfung
python 03_completeness_check.py
```

## Ausgabe

### Hauptpipeline (Schritte 1-3):
- `01_correlation_matrix.xlsx` - Korrelationsmatrix der Referenzdaten
- `02_frequency_analysis.xlsx` - Frequenzanalyse-Ergebnisse
- `03_final_results.xlsx` - **Finale zusammengeführte Vorschläge** (Hauptausgabe)

### Komponenten-Analyse:
- `component_analysis_results/component_suggestions.xlsx` - Komponenten-Vorschläge pro Gebäude

# AIS Bewerbungsprojekt - EP-Katalog Mapping & Vollständigkeitsprüfung

Dieses Projekt umfasst zwei Hauptkomponenten:
1. **EP-Katalog Mapping**: Mappt Einträge aus einer Kundendatei auf den EP-Katalog und weist Artikelnummern zu
2. **Vollständigkeitsprüfung**: Analysiert Gebäudeinstallationen und identifiziert fehlende Komponenten

## 📁 Projektstruktur

```
AIS_task/
├── cvs/                                    # Eingabe- und Ausgabedateien
│   ├── Kundendatei.xlsx                    # Originale Kundendatei
│   ├── Beispielobjekte.xlsx                # Vollständige Referenzdatenbank
│   ├── EP_Katalog.xlsx                     # Vollständiger EP-Katalog
│   ├── EP_Katalog_subheadings.xlsx         # EP-Katalog mit Überschriften
│   └── [weitere Excel-Dateien...]
├── EP_mapping/                             # EP-Katalog Mapping Pipeline
│   ├── 01_find_similar_entries.py          # Schritt 1: Ähnliche Einträge finden
│   ├── 02_map_ep_headings.py               # Schritt 2: EP-Überschriften Mapping
│   ├── 03_openai_mapping.py                # Schritt 3: OpenAI API Mapping
│   ├── 04_article_number_mapping.py        # Schritt 4: Artikelnummer-Mapping
│   ├── run_pipeline.py                     # Master-Skript
│   ├── intermediate_results/               # Zwischenergebnisse
│   └── README.md                           # Detaillierte Dokumentation
├── Completeness_check/                     # Vollständigkeitsprüfung Pipeline
│   ├── 01_correlation_matrix.py            # Schritt 1: Korrelationsmatrix erstellen
│   ├── 02_frequency_analysis.py            # Schritt 2: Frequenzanalyse durchführen
│   ├── 03_completeness_check.py            # Schritt 3: Finale Vollständigkeitsprüfung
│   ├── component_analysis.py               # Komponenten-Analyse (unabhängig)
│   ├── run_pipeline.py                     # Master-Skript
│   └── README.md                           # Detaillierte Dokumentation
├── requirements.txt                        # Python-Abhängigkeiten
├── AIS_Bewerbungspraesentation_Matija_Roncevic.pptx  # Projektpräsentation
└── README.md                               # Diese Übersicht
```

## 🚀 Schnellstart

1. **Abhängigkeiten installieren:**
   ```bash
   pip install -r requirements.txt
   ```

2. **EP_mapping Pipeline ausführen:**
   ```bash
   cd EP_mapping
   python run_pipeline.py
   ```

3. **Completeness_check Pipeline ausführen:**
   ```bash
   cd Completeness_check
   python run_pipeline.py
   ```

4. **Ergebnisse:**
   - **EP_mapping**: Finale Kundendatei mit Artikelnummern in `cvs/kundendatei_final.xlsx`
   - **Completeness_check**: Vollständigkeitsprüfung in `Completeness_check/03_final_results.xlsx`

5. **Präsentation:**
   - **AIS_Bewerbungspraesentation_Matija_Roncevic.pptx**: Vollständige Projektpräsentation

## 📋 Voraussetzungen

- Python 3.8+
- OpenAI API Key (für EP_mapping Schritt 3)
- Alle erforderlichen Excel-Dateien im `cvs/` Ordner
- Sentence Transformers 

## 🔄 Pipeline-Übersicht

### EP_mapping Pipeline
1. **Ähnliche Einträge finden** - Gruppiert ähnliche Kundendatei-Einträge
2. **EP-Überschriften Mapping** - Mapped repräsentative Einträge auf EP-Überschriften
3. **OpenAI API Mapping** - Verwendet KI für verbleibende Einträge
4. **Artikelnummer-Mapping** - Weist spezifische Artikelnummern zu

### Completeness_check Pipeline
1. **Korrelationsmatrix erstellen** - Analysiert Installation-Zusammenhänge
2. **Frequenzanalyse durchführen** - Identifiziert typische Installationen
3. **Finale Vollständigkeitsprüfung** - Kombiniert alle Analysen für Vorschläge

## 📖 Detaillierte Dokumentation

- **EP_mapping**: Siehe `EP_mapping/README.md` für eine vollständige Dokumentation der EP-Katalog Mapping Pipeline
- **Completeness_check**: Siehe `Completeness_check/README.md` für eine vollständige Dokumentation der Vollständigkeitsprüfung Pipeline


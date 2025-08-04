#!/usr/bin/env python3
"""
OpenAI API Mapping für verbleibende Einträge

Dieses Skript:
1. Erstellt eine Zusammenfassung der ursprünglichen Kundendatei
2. Verwendet OpenAI API um verbleibende Einträge auf EP-Überschriften zu mappen
3. Speichert die Ergebnisse in Kundendatei_summary.xlsx

Autor: AI Assistant
Datum: 2025-08-03
"""

import pandas as pd
import numpy as np
import json
import logging
import os
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm
import time

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OpenAIMapper:
    def __init__(self, test_limit=None):
        """
        Initialisiert den OpenAI Mapper.
        
        Args:
            test_limit: Begrenzung für Testläufe (None = alle Einträge)
        """
        self.client = OpenAI()
        self.test_limit = test_limit
        self.intermediate_dir = Path("intermediate_results")
        self.intermediate_dir.mkdir(exist_ok=True)
        
        # Dateipfade (relativ zum übergeordneten Verzeichnis)
        self.kundendatei_path = "../cvs/Kundendatei.xlsx"
        self.ep_subheadings_path = "../cvs/EP_Katalog_subheadings.xlsx"
        self.hierarchy_path = "hierarchy_structure_EP_Katalog.json"
        
    def load_data(self):
        """Lädt alle benötigten Daten."""
        logger.info("Lade Daten...")
        
        # Lade ursprüngliche Kundendatei
        self.kundendatei = pd.read_excel(self.kundendatei_path)
        logger.info(f"Kundendatei geladen: {len(self.kundendatei)} Einträge")
        
        # Lade EP Subheadings
        self.ep_subheadings = pd.read_excel(self.ep_subheadings_path)
        logger.info(f"EP Subheadings geladen: {len(self.ep_subheadings)} Einträge")
        
        # Lade Hierarchie
        with open(self.hierarchy_path, 'r', encoding='utf-8') as f:
            self.hierarchy = json.load(f)
        logger.info("Hierarchie geladen")
        
        # Lade bisherige Ergebnisse
        self.load_previous_results()
        
    def load_previous_results(self):
        """Lädt bisherige Mapping-Ergebnisse."""
        try:
            # Lade reduced Kundendatei mit EP Headings
            reduced_path = self.intermediate_dir / "reduced_kundendatei_with_ep_headings.xlsx"
            if reduced_path.exists():
                self.reduced_kundendatei = pd.read_excel(reduced_path)
                logger.info(f"Reduzierte Kundendatei geladen: {len(self.reduced_kundendatei)} Einträge")
                
                # Finde gemappte Kunden-Indizes
                self.mapped_kunden_indices = set(self.reduced_kundendatei['Kunden_index'].dropna())
                logger.info(f"Bereits gemappte Einträge: {len(self.mapped_kunden_indices)}")
            else:
                logger.warning("Keine reduzierten Kundendatei gefunden - alle Einträge werden als unmapped betrachtet")
                self.mapped_kunden_indices = set()
                
        except Exception as e:
            logger.error(f"Fehler beim Laden bisheriger Ergebnisse: {e}")
            self.mapped_kunden_indices = set()
    
    def load_or_create_kundendatei_summary(self):
        """Lädt vorhandene oder erstellt neue Kundendatei-Zusammenfassung."""
        summary_path = self.intermediate_dir / "03_openai_mapping_results.xlsx"
        
        if summary_path.exists():
            logger.info("Lade vorhandene OpenAI Mapping Ergebnisse...")
            self.kundendatei_summary = pd.read_excel(summary_path)
            logger.info(f"OpenAI Mapping Ergebnisse geladen: {len(self.kundendatei_summary)} Einträge")
            return self.kundendatei_summary
        else:
            logger.info("Keine vorhandenen OpenAI Mapping Ergebnisse gefunden - erstelle neue...")
            return self.create_kundendatei_summary()
    
    def create_kundendatei_summary(self):
        """Erstellt eine Zusammenfassung der ursprünglichen Kundendatei."""
        logger.info("Erstelle Kundendatei-Zusammenfassung...")
        
        # Spalten ausschließen (wie in clean_kundendatei.py)
        drop_columns = ["WirtEinh", "EQ_übergeordnet", "Equipment", "EQ-Klasse", "EQ-Menge"]
        
        # Verfügbare Spalten finden (alle außer den ausgeschlossenen)
        available_columns = [col for col in self.kundendatei.columns if col not in drop_columns]
        logger.info(f"Verfügbare Spalten für Zusammenfassung: {len(available_columns)} Spalten")
        
        # Zusammenfassung erstellen
        summary_data = []
        
        for idx, row in tqdm(self.kundendatei.iterrows(), total=len(self.kundendatei), desc="Erstelle Zusammenfassungen"):
            # Kombiniere verfügbare Spalten
            combined_text = []
            for col in available_columns:
                value = row[col]
                if pd.notna(value) and str(value).strip() != '' and str(value).strip() != 'nan':
                    combined_text.append(str(value).strip())
            
            summary_text = " | ".join(combined_text) if combined_text else "Keine Beschreibung verfügbar"
            
            summary_data.append({
                'Kunden_index': idx,
                'summary_text': summary_text,
                'original_columns': " | ".join(available_columns)
            })
        
        self.kundendatei_summary = pd.DataFrame(summary_data)
        
        # Speichere Zusammenfassung
        summary_path = self.intermediate_dir / "03_openai_mapping_results.xlsx"
        self.kundendatei_summary.to_excel(summary_path, index=False)
        logger.info(f"OpenAI Mapping Ergebnisse gespeichert: {summary_path}")
        
        return self.kundendatei_summary
    
    def get_lowest_level_headings(self):
        """Extrahiert die niedrigsten Ebenen der Hierarchie."""
        lowest_levels = []
        
        def find_lowest_levels(node, path=""):
            if not node.get("children") or len(node.get("children", {})) == 0:
                # Dies ist ein Blattknoten (niedrigste Ebene)
                lowest_levels.append({
                    "key": path,
                    "text": node.get("text", "")
                })
            else:
                # Rekursiv durch Kinder gehen
                for child_key, child_node in node["children"].items():
                    new_path = path + child_key if path else child_key
                    find_lowest_levels(child_node, new_path)
        
        # Starte mit dem Root-Knoten
        for root_key, root_node in self.hierarchy.items():
            find_lowest_levels(root_node, root_key)
        
        logger.info(f"Niedrigste Ebenen gefunden: {len(lowest_levels)}")
        if len(lowest_levels) <= 5:  # Debug: Zeige erste paar Einträge
            for i, level in enumerate(lowest_levels[:5]):
                logger.info(f"  {i+1}. {level['key']}: {level['text'][:50]}...")
        return lowest_levels
    
    def create_openai_prompt(self, summary_text, lowest_headings):
        """Erstellt den OpenAI Prompt für das Mapping."""
        # Erstelle Liste der verfügbaren Überschriften (alle Kategorien)
        headings_text = "\n".join([f"{h['key']}: {h['text']}" for h in lowest_headings])
        
        prompt = f"""
Du bist ein Experte für die Zuordnung von technischen Anlagen zu Kategorien.

Gegeben ist folgende Beschreibung einer technischen Anlage:
{summary_text}

Verfügbare Kategorien (nur die niedrigste Ebene):
{headings_text}

Aufgabe: Finde die am besten passende Kategorie für die beschriebene Anlage.

Wichtige Regeln:
1. Wähle nur aus den angegebenen Kategorien
2. Gib NUR den Schlüssel (z.B. "01.01.01.12.") zurück
3. Keine Erklärungen oder zusätzlichen Text
4. Wenn keine passende Kategorie gefunden wird, gib "KEINE_PASSENDE_KATEGORIE" zurück

Antwort (nur der Schlüssel):
"""
        return prompt
    
    def validate_ep_key(self, key):
        """Validiert einen EP-Schlüssel gegen die EP_Katalog_subheadings.xlsx."""
        if key == "KEINE_PASSENDE_KATEGORIE":
            return False, None
        
        # Suche nach dem Schlüssel in der OZ-Spalte
        matching_rows = self.ep_subheadings[self.ep_subheadings['OZ'] == key]
        
        if len(matching_rows) == 0:
            logger.warning(f"Schlüssel {key} nicht in EP_Katalog_subheadings gefunden")
            return False, None
        
        # Prüfe ob es eine Überschriftenzeile ist (Art beginnt mit "NG")
        for _, row in matching_rows.iterrows():
            if pd.notna(row['Art']) and str(row['Art']).startswith('NG'):
                return True, row.name  # Gib den ursprünglichen Index zurück
        
        logger.warning(f"Schlüssel {key} gefunden, aber keine Überschriftenzeile (Art nicht NG)")
        return False, None
    
    def map_unmapped_entries(self):
        """Mapped verbleibende Einträge mit OpenAI API."""
        logger.info("Starte OpenAI Mapping für verbleibende Einträge...")
        
        # Finde unmappte Einträge
        all_kunden_indices = set(self.kundendatei.index)
        unmapped_indices = all_kunden_indices - self.mapped_kunden_indices
        
        logger.info(f"Unmappte Einträge: {len(unmapped_indices)}")
        
        # Begrenze für Testläufe
        if self.test_limit:
            unmapped_indices = set(list(unmapped_indices)[:self.test_limit])
            logger.info(f"Testlauf: Begrenzt auf {len(unmapped_indices)} Einträge")
        
        # Hole niedrigste Ebenen der Hierarchie
        lowest_headings = self.get_lowest_level_headings()
        
        # Mapping-Ergebnisse
        mapping_results = []
        
        for kunden_index in tqdm(unmapped_indices, desc="OpenAI Mapping"):
            try:
                # Hole Zusammenfassung für diesen Eintrag
                summary_row = self.kundendatei_summary[self.kundendatei_summary['Kunden_index'] == kunden_index]
                if len(summary_row) == 0:
                    logger.warning(f"Keine Zusammenfassung gefunden für Kunden_index {kunden_index}")
                    continue
                
                summary_text = summary_row.iloc[0]['summary_text']
                
                # Erstelle OpenAI Prompt
                prompt = self.create_openai_prompt(summary_text, lowest_headings)
                
                # OpenAI API Call
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Du bist ein Experte für technische Kategorisierung."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=50
                )
                
                # Extrahiere Antwort
                response_text = response.choices[0].message.content.strip()
                
                # Validiere Antwort
                is_valid, ep_original_index = self.validate_ep_key(response_text)
                
                mapping_results.append({
                    'Kunden_index': kunden_index,
                    'summary_text': summary_text,
                    'openai_response': response_text,
                    'is_valid_mapping': is_valid,
                    'EP_original_index': ep_original_index,
                    'EP_key': response_text if is_valid else None
                })
                
                # Längere Pause zwischen API Calls um Rate Limiting zu vermeiden
                time.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Fehler beim Mapping von Kunden_index {kunden_index}: {e}")
                mapping_results.append({
                    'Kunden_index': kunden_index,
                    'summary_text': summary_text if 'summary_text' in locals() else "Fehler beim Laden",
                    'openai_response': f"Fehler: {str(e)}",
                    'is_valid_mapping': False,
                    'EP_original_index': None,
                    'EP_key': None
                })
        
        # Erstelle DataFrame und speichere
        self.mapping_results_df = pd.DataFrame(mapping_results)
        
        results_path = self.intermediate_dir / "openai_mapping_results.xlsx"
        self.mapping_results_df.to_excel(results_path, index=False)
        logger.info(f"OpenAI Mapping-Ergebnisse gespeichert: {results_path}")
        
        # Statistiken
        valid_mappings = self.mapping_results_df[self.mapping_results_df['is_valid_mapping']]
        logger.info(f"Erfolgreiche Mappings: {len(valid_mappings)} / {len(mapping_results)}")
        
        return self.mapping_results_df
    
    def update_kundendatei_summary(self):
        """Aktualisiert die Kundendatei-Zusammenfassung mit den neuen Mappings."""
        logger.info("Aktualisiere Kundendatei-Zusammenfassung mit neuen Mappings...")
        
        # Füge Mapping-Ergebnisse hinzu
        self.kundendatei_summary = self.kundendatei_summary.merge(
            self.mapping_results_df[['Kunden_index', 'openai_response', 'is_valid_mapping', 'EP_original_index', 'EP_key']],
            on='Kunden_index',
            how='left'
        )
        
        # Speichere aktualisierte Zusammenfassung
        summary_path = self.intermediate_dir / "03_openai_mapping_results.xlsx"
        self.kundendatei_summary.to_excel(summary_path, index=False)
        logger.info(f"Aktualisierte OpenAI Mapping Ergebnisse gespeichert: {summary_path}")
        
        return self.kundendatei_summary
    
    def run(self):
        """Führt die komplette OpenAI Mapping Pipeline aus."""
        logger.info("🚀 Starte OpenAI Mapping Pipeline")
        
        try:
            # Schritt 1: Daten laden
            self.load_data()
            
            # Schritt 2: Kundendatei-Zusammenfassung laden oder erstellen
            self.load_or_create_kundendatei_summary()
            
            # Schritt 3: Unmappte Einträge mappen
            self.map_unmapped_entries()
            
            # Schritt 4: Zusammenfassung aktualisieren
            self.update_kundendatei_summary()
            
            logger.info("🎉 OpenAI Mapping Pipeline erfolgreich abgeschlossen!")
            
        except Exception as e:
            logger.error(f"❌ Fehler in der OpenAI Mapping Pipeline: {e}")
            raise

def main():
    """Hauptfunktion für vollständige Verarbeitung."""
    # Vollständige Verarbeitung aller Einträge
    mapper = OpenAIMapper(test_limit=None)  # Alle Einträge verarbeiten
    mapper.run()

if __name__ == "__main__":
    main() 
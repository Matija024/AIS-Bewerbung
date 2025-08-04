#!/usr/bin/env python3
"""
Artikelnummer-Mapping Pipeline

Dieses Skript:
1. Extrahiert EP-Gruppen aus dem EP-Katalog basierend auf den gefundenen Überschriften
2. Vergleicht Kundendatei-Zusammenfassungen mit den EP-Gruppen
3. Findet die besten Artikelnummer-Matches
4. Erstellt finale Kundendatei mit Artikelnummer-Spalte

Autor: AI Assistant
Datum: 2025-08-03
"""

import pandas as pd
import numpy as np
import json
import logging
import os
import time
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArticleNumberMapper:
    def __init__(self):
        """Initialisiert den Article Number Mapper."""
        self.intermediate_dir = Path("intermediate_results")
        self.intermediate_dir.mkdir(exist_ok=True)
        
        # Dateipfade (relativ zum übergeordneten Verzeichnis)
        self.kundendatei_path = "../cvs/Kundendatei.xlsx"
        self.ep_katalog_path = "../cvs/EP_Katalog.xlsx"
        self.ep_subheadings_path = "../cvs/EP_Katalog_subheadings.xlsx"
        
        # OpenAI Client für Artikelnummer-Vergleich
        self.client = OpenAI()
        
    def load_data(self):
        """Lädt alle benötigten Daten."""
        logger.info("Lade Daten...")
        
        # Lade ursprüngliche Kundendatei
        self.kundendatei = pd.read_excel(self.kundendatei_path)
        logger.info(f"Kundendatei geladen: {len(self.kundendatei)} Einträge")
        
        # Lade EP Katalog
        self.ep_katalog = pd.read_excel(self.ep_katalog_path)
        logger.info(f"EP Katalog geladen: {len(self.ep_katalog)} Einträge")
        
        # Lade EP Subheadings
        self.ep_subheadings = pd.read_excel(self.ep_subheadings_path)
        logger.info(f"EP Subheadings geladen: {len(self.ep_subheadings)} Einträge")
        
        # Lade bisherige Ergebnisse
        self.load_previous_results()
        
    def load_previous_results(self):
        """Lädt bisherige Mapping-Ergebnisse."""
        try:
            # Lade Kundendatei-Zusammenfassung mit OpenAI Mappings
            summary_path = self.intermediate_dir / "03_openai_mapping_results.xlsx"
            if summary_path.exists():
                self.kundendatei_summary = pd.read_excel(summary_path)
                logger.info(f"Kundendatei-Zusammenfassung geladen: {len(self.kundendatei_summary)} Einträge")
            else:
                raise FileNotFoundError("Kundendatei-Zusammenfassung nicht gefunden")
            
            # Lade Similarity Groups
            groups_path = self.intermediate_dir / "01_similar_groups.json"
            if groups_path.exists():
                with open(groups_path, 'r') as f:
                    self.similar_groups = json.load(f)
                logger.info(f"Similarity Groups geladen: {len(self.similar_groups)} Gruppen")
            else:
                self.similar_groups = {}
                logger.warning("Keine Similarity Groups gefunden")
                
        except Exception as e:
            logger.error(f"Fehler beim Laden bisheriger Ergebnisse: {e}")
            raise
    
    def extract_ep_group(self, ep_original_index):
        """
        Extrahiert eine EP-Gruppe aus dem Katalog basierend auf dem EP-Index.
        
        Args:
            ep_original_index: Index der Überschrift in EP_Katalog_subheadings.xlsx
            
        Returns:
            DataFrame mit allen Artikeln der Gruppe
        """
        if pd.isna(ep_original_index):
            return pd.DataFrame()
        
        # Finde die Überschrift in EP_Katalog_subheadings
        if ep_original_index not in self.ep_subheadings.index:
            logger.warning(f"EP-Index {ep_original_index} nicht in EP_Katalog_subheadings gefunden")
            return pd.DataFrame()
        
        # Gehe zum nächsten Index (erster Artikel der Gruppe)
        start_index = ep_original_index + 1
        
        # Sammle alle Zeilen bis zur nächsten Überschrift
        group_rows = []
        current_index = start_index
        
        while current_index < len(self.ep_katalog):
            row = self.ep_katalog.iloc[current_index]
            
            # Prüfe ob es eine Überschrift ist (Art beginnt mit "NG")
            if pd.notna(row.get('Art', '')) and str(row['Art']).startswith('NG'):
                # Neue Überschrift gefunden - Gruppe ist vollständig
                break
            
            # Füge Artikel zur Gruppe hinzu
            group_rows.append(row)
            current_index += 1
        
        if group_rows:
            group_df = pd.DataFrame(group_rows)
            logger.info(f"EP-Gruppe extrahiert: {len(group_df)} Artikel (Start: {start_index})")
            return group_df
        else:
            logger.warning(f"Keine Artikel in EP-Gruppe gefunden für Index {ep_original_index}")
            return pd.DataFrame()
    
    def create_article_comparison_text(self, article_row):
        """
        Erstellt einen Vergleichstext für einen Artikel aus dem EP-Katalog.
        
        Args:
            article_row: Zeile aus dem EP-Katalog
            
        Returns:
            String mit relevanten Informationen des Artikels
        """
        # Wichtige Spalten für den Vergleich
        important_columns = ['Bezeichnung', 'Beschreibung', 'Spezifikation', 'Hersteller', 'Artikelnummer']
        
        comparison_parts = []
        for col in important_columns:
            if col in article_row.index and pd.notna(article_row[col]):
                value = str(article_row[col]).strip()
                if value and value != 'nan':
                    comparison_parts.append(value)
        
        return " | ".join(comparison_parts) if comparison_parts else "Keine Beschreibung verfügbar"
    
    def create_openai_prompt(self, customer_summary, ep_group_df):
        """
        Erstellt einen OpenAI Prompt für den Artikelnummer-Vergleich.
        
        Args:
            customer_summary: Zusammenfassungstext der Kundendatei
            ep_group_df: DataFrame mit EP-Gruppe
            
        Returns:
            String mit dem OpenAI Prompt
        """
        # Erstelle Artikel-Liste für den Prompt
        articles_text = ""
        for idx, row in ep_group_df.iterrows():
            article_text = self.create_article_comparison_text(row)
            articles_text += f"Artikel {idx}: {article_text}\n"
        
        prompt = f"""
Du bist ein Experte für die Zuordnung von Kundeneinträgen zu Artikelnummern.

KUNDENEINTRAG:
{customer_summary}

VERFÜGBARE ARTIKEL:
{articles_text}

AUFGABE:
Finde die beste Übereinstimmung zwischen dem Kundeneintrag und einem der verfügbaren Artikel.
Berücksichtige dabei Bezeichnung, Beschreibung, Spezifikation und Hersteller.

ANTWORT:
Gib NUR die Artikelnummer des besten Matches zurück. Falls kein passender Artikel gefunden wird, antworte mit "KEIN_MATCH".

Artikelnummer: """
        
        return prompt
    
    def find_best_article_match(self, customer_summary, ep_group_df):
        """
        Findet den besten Artikel-Match für eine Kundendatei-Zusammenfassung mit OpenAI.
        
        Args:
            customer_summary: Zusammenfassungstext der Kundendatei
            ep_group_df: DataFrame mit EP-Gruppe
            
        Returns:
            Tuple (best_match_row, article_number)
        """
        if len(ep_group_df) == 0:
            return None, None
        
        try:
            # Erstelle OpenAI Prompt
            prompt = self.create_openai_prompt(customer_summary, ep_group_df)
            
            # OpenAI API Call
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            # Extrahiere Antwort
            article_number = response.choices[0].message.content.strip()
            
            # Prüfe ob ein Match gefunden wurde
            if article_number == "KEIN_MATCH" or not article_number:
                return None, None
            
            # Finde die entsprechende Zeile im DataFrame
            matching_row = ep_group_df[ep_group_df['Artikelnummer'] == article_number]
            if len(matching_row) > 0:
                return matching_row.iloc[0], article_number
            else:
                logger.warning(f"Artikelnummer {article_number} nicht in EP-Gruppe gefunden")
                return None, None
                
        except Exception as e:
            logger.error(f"Fehler beim OpenAI API Call: {e}")
            return None, None
    
    def map_article_numbers(self):
        """
        Mapped Artikelnummern für alle Kundendatei-Einträge.
        """
        logger.info("Starte Artikelnummer-Mapping...")
        
        # Ergebnisse sammeln
        mapping_results = []
        
        # Gruppiere Einträge nach EP-Überschriften
        grouped_by_heading = self.kundendatei_summary.groupby('EP_original_index')
        
        for ep_index, group in tqdm(grouped_by_heading, desc="Verarbeite EP-Gruppen"):
            if pd.isna(ep_index):
                # Keine Überschrift gefunden - alle Einträge ohne Artikelnummer
                for _, row in group.iterrows():
                    mapping_results.append({
                        'Kunden_index': row['Kunden_index'],
                        'EP_original_index': None,
                        'article_number': None,
                        'similarity_score': 0.0,
                        'mapping_status': 'Keine Überschrift gefunden'
                    })
                continue
            
            # Extrahiere EP-Gruppe
            ep_group_df = self.extract_ep_group(ep_index)
            
            if len(ep_group_df) == 0:
                # Keine Artikel in der Gruppe gefunden
                for _, row in group.iterrows():
                    mapping_results.append({
                        'Kunden_index': row['Kunden_index'],
                        'EP_original_index': ep_index,
                        'article_number': None,
                        'similarity_score': 0.0,
                        'mapping_status': 'Keine Artikel in EP-Gruppe'
                    })
                continue
            
            # Verarbeite alle Einträge dieser Gruppe
            for _, row in group.iterrows():
                customer_summary = row['summary_text']
                
                # Finde besten Artikel-Match mit OpenAI
                best_match, article_number = self.find_best_article_match(
                    customer_summary, ep_group_df
                )
                
                if best_match is not None:
                    mapping_results.append({
                        'Kunden_index': row['Kunden_index'],
                        'EP_original_index': ep_index,
                        'article_number': article_number,
                        'mapping_status': 'Artikelnummer gefunden'
                    })
                else:
                    mapping_results.append({
                        'Kunden_index': row['Kunden_index'],
                        'EP_original_index': ep_index,
                        'article_number': None,
                        'mapping_status': 'Kein passender Artikel gefunden'
                    })
                
                # Rate limiting für OpenAI API
                time.sleep(1.0)
        
        # Erstelle DataFrame
        self.mapping_results_df = pd.DataFrame(mapping_results)
        
        # Speichere Ergebnisse
        results_path = self.intermediate_dir / "article_number_mapping.xlsx"
        self.mapping_results_df.to_excel(results_path, index=False)
        logger.info(f"Artikelnummer-Mapping-Ergebnisse gespeichert: {results_path}")
        
        # Statistiken
        successful_mappings = self.mapping_results_df[self.mapping_results_df['article_number'].notna()]
        logger.info(f"Erfolgreiche Artikelnummer-Mappings: {len(successful_mappings)} / {len(mapping_results)}")
        logger.info(f"Erfolgsrate: {len(successful_mappings) / len(mapping_results) * 100:.1f}%")
        
        return self.mapping_results_df
    
    def create_final_kundendatei(self):
        """
        Erstellt die finale Kundendatei mit Artikelnummer-Spalte.
        """
        logger.info("Erstelle finale Kundendatei...")
        
        # Füge Artikelnummern zur ursprünglichen Kundendatei hinzu
        final_kundendatei = self.kundendatei.copy()
        
        # Erstelle Mapping-Dictionary
        article_mapping = dict(zip(
            self.mapping_results_df['Kunden_index'],
            self.mapping_results_df['article_number']
        ))
        
        # Füge Artikelnummer-Spalte hinzu
        final_kundendatei.insert(0, 'Artikelnummer', final_kundendatei.index.map(article_mapping))
        
        # Speichere finale Kundendatei
        final_path = Path("../cvs/kundendatei_final.xlsx")
        final_kundendatei.to_excel(final_path, index=False)
        logger.info(f"Finale Kundendatei gespeichert: {final_path}")
        
        # Erstelle auch CSV-Version
        final_csv_path = Path("../cvs/kundendatei_final.csv")
        final_kundendatei.to_csv(final_csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"Finale Kundendatei (CSV) gespeichert: {final_csv_path}")
        
        return final_kundendatei
    
    def run(self):
        """Führt die komplette Artikelnummer-Mapping Pipeline aus."""
        logger.info("🚀 Starte Artikelnummer-Mapping Pipeline")
        
        try:
            # Schritt 1: Daten laden
            self.load_data()
            
            # Schritt 2: Artikelnummern mappen
            self.map_article_numbers()
            
            # Schritt 3: Finale Kundendatei erstellen
            self.create_final_kundendatei()
            
            logger.info("🎉 Artikelnummer-Mapping Pipeline erfolgreich abgeschlossen!")
            
        except Exception as e:
            logger.error(f"❌ Fehler in der Artikelnummer-Mapping Pipeline: {e}")
            raise

def main():
    """Hauptfunktion."""
    mapper = ArticleNumberMapper()
    mapper.run()

if __name__ == "__main__":
    main() 
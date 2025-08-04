import pandas as pd
import numpy as np
import logging
import json
import os
from typing import Dict, List, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FinalCompletenessChecker:
    def __init__(self, model_name: str = 'T-Systems-onsite/cross-en-de-roberta-sentence-transformer'):
        """
        Initialisiert den Final Completeness Checker.
        """
        self.model = SentenceTransformer(model_name)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.frequency_analysis = None
        self.correlation_matrix = None
        self.building_installations_reference = None
        self.installation_mapping = None
        self.verbandsnummer_mapping = None
        
        logger.info(f"Verwende Modell: {model_name} auf {self.device}")
        
    def load_reference_data(self):
        """
        Lädt die Referenzdaten (Frequenzanalyse und Korrelationsmatrix).
        """
        logger.info("Lade Referenzdaten...")
        
        # Lade Frequenzanalyse
        if os.path.exists("02_frequency_analysis.xlsx"):
            self.frequency_analysis = pd.read_excel("02_frequency_analysis.xlsx")
            logger.info(f"Frequenzanalyse geladen: {len(self.frequency_analysis)} Installationen")
        else:
            logger.error("Frequenzanalyse nicht gefunden! Führe zuerst 02_frequency_analysis.py aus.")
            return False
        
        # Lade Korrelationsmatrix
        if os.path.exists("01_correlation_matrix.xlsx"):
            self.correlation_matrix = pd.read_excel("01_correlation_matrix.xlsx", index_col=0)
            logger.info(f"Korrelationsmatrix geladen: {self.correlation_matrix.shape}")
        else:
            logger.error("Korrelationsmatrix nicht gefunden! Führe zuerst 01_correlation_matrix.py aus.")
            return False
        
        # Erstelle Gebäude-Installation Referenzmatrix
        self._create_reference_matrix()
        
        return True
    
    def _create_reference_matrix(self):
        """
        Erstellt die Referenzmatrix für Gebäude-Installationen.
        """
        logger.info("Erstelle Referenzmatrix...")
        
        # Lade Originaldaten
        data = pd.read_excel("../cvs/Beispielobjekte.xlsx", sheet_name="Anlagen")
        
        # Erstelle Gebäude-Installation Matrix
        self.building_installations_reference = (
            data.groupby(["Gebäude-ID", "AKS-Bezeichnung"])
            .size()
            .unstack(fill_value=0)
        )
        
        # Konvertiere zu 1/0 Matrix
        self.building_installations_reference = (self.building_installations_reference > 0).astype(int)
        
        # Erstelle Verbandsnummer-Mapping für Installationen
        self._create_verbandsnummer_mapping(data)
        
        logger.info(f"Referenzmatrix erstellt: {self.building_installations_reference.shape}")
    
    def _create_verbandsnummer_mapping(self, data: pd.DataFrame):
        """
        Erstellt ein Mapping zwischen AKS-Bezeichnung und Verbandsnummer.
        """
        logger.info("Erstelle Verbandsnummer-Mapping...")
        
        # Erstelle Mapping: AKS-Bezeichnung -> Verbandsnummer
        verbandsnummer_mapping = {}
        
        for _, row in data.iterrows():
            aks_bezeichnung = row['AKS-Bezeichnung']
            verbandsnummer = row.get('Verbandsnummer', '')
            
            if pd.notna(verbandsnummer) and verbandsnummer != '':
                verbandsnummer_mapping[aks_bezeichnung] = verbandsnummer
        
        self.verbandsnummer_mapping = verbandsnummer_mapping
        
        logger.info(f"Verbandsnummer-Mapping erstellt: {len(self.verbandsnummer_mapping)} Einträge")
    
    def create_installation_mapping(self, kunde_installations: List[str], similarity_threshold: float = 0.7):
        """
        Erstellt ein Mapping zwischen Kundendatei-Installationen und Referenz-Installationen.
        
        Args:
            kunde_installations: Liste der Installationen aus der Kundendatei
            similarity_threshold: Schwellenwert für Text-Ähnlichkeit
        """
        logger.info("Erstelle Installation Mapping...")
        
        # Referenz-Installationen
        reference_installations = self.frequency_analysis['Installation'].tolist()
        
        # Berechne Embeddings
        logger.info("Berechne Embeddings für Kundendatei-Installationen...")
        kunde_embeddings = self.model.encode(kunde_installations, show_progress_bar=True, device=self.device)
        
        logger.info("Berechne Embeddings für Referenz-Installationen...")
        reference_embeddings = self.model.encode(reference_installations, show_progress_bar=True, device=self.device)
        
        # Berechne Ähnlichkeiten
        logger.info("Berechne Ähnlichkeitsmatrix...")
        similarity_matrix = cosine_similarity(kunde_embeddings, reference_embeddings)
        
        # Erstelle Mapping
        self.installation_mapping = {}
        
        for i, kunde_inst in enumerate(kunde_installations):
            similarities = similarity_matrix[i]
            best_match_idx = np.argmax(similarities)
            best_match_score = similarities[best_match_idx]
            best_match_inst = reference_installations[best_match_idx]
            
            if best_match_score >= similarity_threshold:
                self.installation_mapping[kunde_inst] = {
                    'reference_installation': best_match_inst,
                    'similarity_score': best_match_score,
                    'mapped': True
                }
            else:
                self.installation_mapping[kunde_inst] = {
                    'reference_installation': None,
                    'similarity_score': best_match_score,
                    'mapped': False
                }
        
        # Statistiken
        mapped_count = sum(1 for mapping in self.installation_mapping.values() if mapping['mapped'])
        logger.info(f"Installation Mapping erstellt: {mapped_count}/{len(kunde_installations)} Installationen gemappt")
        
        return self.installation_mapping
    
    def load_customer_data(self, kundendatei_path: str) -> pd.DataFrame:
        """
        Lädt und bereitet die Kundendatei vor.
        
        Args:
            kundendatei_path: Pfad zur Kundendatei
            
        Returns:
            DataFrame mit vorbereiteten Kundendaten
        """
        logger.info(f"Lade Kundendatei: {kundendatei_path}")
        
        # Lade Kundendatei
        kunde_data = pd.read_excel(kundendatei_path)
        logger.info(f"Kundendatei geladen: {len(kunde_data)} Zeilen")
        
        # Prüfe ob WirtEinh Spalte existiert
        if 'WirtEinh' not in kunde_data.columns:
            logger.error("Spalte 'WirtEinh' nicht gefunden in Kundendatei!")
            return None
        
        # Kombiniere EQ-Klasse-Bezeichnung und Anlagenausprägung
        if 'EQ-Klasse-Bezeichnung' in kunde_data.columns and 'Anlagenausprägung' in kunde_data.columns:
            kunde_data['combined_installation'] = (
                kunde_data['EQ-Klasse-Bezeichnung'].fillna('').astype(str) + ' ' +
                kunde_data['Anlagenausprägung'].fillna('').astype(str)
            )
        else:
            # Fallback: Verwende alle Textspalten
            text_columns = kunde_data.select_dtypes(include=['object']).columns
            kunde_data['combined_installation'] = kunde_data[text_columns].fillna('').astype(str).agg(' '.join, axis=1)
        
        # Erstelle Gebäude-Installation Matrix
        kunde_building_installations = (
            kunde_data.groupby(["WirtEinh", "combined_installation"])
            .size()
            .unstack(fill_value=0)
        )
        
        # Konvertiere zu 1/0 Matrix
        kunde_building_installations = (kunde_building_installations > 0).astype(int)
        
        logger.info(f"Kundendatei Matrix erstellt: {kunde_building_installations.shape}")
        logger.info(f"Anzahl Gebäude in Kundendatei: {len(kunde_building_installations)}")
        
        # Erstelle Installation Mapping
        unique_installations = kunde_building_installations.columns.tolist()
        self.create_installation_mapping(unique_installations)
        
        return kunde_building_installations
    
    def find_missing_installations(self, kunde_building_installations: pd.DataFrame, 
                                 frequency_threshold: float = 50.0,
                                 correlation_threshold: float = 0.7) -> Dict:
        """
        Findet fehlende Installationen basierend auf Frequenzanalyse und Korrelation.
        
        Args:
            kunde_building_installations: Gebäude-Installation Matrix der Kundendatei
            frequency_threshold: Mindesthäufigkeit für "typische" Installationen (%)
            correlation_threshold: Mindestkorrelation für Vorschläge
            
        Returns:
            Dictionary mit Analyseergebnissen
        """
        logger.info("Analysiere fehlende Installationen...")
        
        results = {
            'buildings_analyzed': len(kunde_building_installations),
            'missing_installations': {},
            'summary': {}
        }
        
        # Für jedes Gebäude in der Kundendatei
        for building_id in kunde_building_installations.index:
            logger.info(f"Analysiere Gebäude: {building_id}")
            
            building_results = {
                'existing_installations': [],
                'existing_mapped_installations': [],
                'missing_high_frequency': [],
                'missing_correlated': [],
                'suggestions': []
            }
            
            # Finde vorhandene Installationen
            existing_installations = kunde_building_installations.loc[building_id]
            existing_installations = existing_installations[existing_installations == 1].index.tolist()
            building_results['existing_installations'] = existing_installations
            
            # Mappe vorhandene Installationen auf Referenz-Installationen
            mapped_installations = []
            for inst in existing_installations:
                if inst in self.installation_mapping and self.installation_mapping[inst]['mapped']:
                    mapped_inst = self.installation_mapping[inst]['reference_installation']
                    mapped_installations.append(mapped_inst)
            
            building_results['existing_mapped_installations'] = mapped_installations
            
            # 1. Frequenzbasierte Vorschläge
            high_frequency_installations = self.frequency_analysis[
                self.frequency_analysis['Prozent'] >= frequency_threshold
            ]['Installation'].tolist()
            
            missing_high_frequency = [
                inst for inst in high_frequency_installations 
                if inst not in mapped_installations
            ]
            
            building_results['missing_high_frequency'] = missing_high_frequency
            
            # 2. Korrelationsbasierte Vorschläge
            missing_correlated = []
            for existing_inst in mapped_installations:
                if existing_inst in self.correlation_matrix.columns:
                    # Finde Installationen, die stark mit der vorhandenen Installation korrelieren
                    correlations = self.correlation_matrix[existing_inst].sort_values(ascending=False)
                    high_correlations = correlations[correlations >= correlation_threshold]
                    
                    for correlated_inst, corr_value in high_correlations.items():
                        if (correlated_inst not in mapped_installations and 
                            correlated_inst != existing_inst):
                            missing_correlated.append({
                                'installation': correlated_inst,
                                'correlated_with': existing_inst,
                                'correlation': corr_value
                            })
            
            # Entferne Duplikate und sortiere nach Korrelation
            unique_correlated = {}
            for item in missing_correlated:
                inst = item['installation']
                if inst not in unique_correlated or item['correlation'] > unique_correlated[inst]['correlation']:
                    unique_correlated[inst] = item
            
            building_results['missing_correlated'] = list(unique_correlated.values())
            building_results['missing_correlated'].sort(key=lambda x: x['correlation'], reverse=True)
            
            # 3. Kombinierte Vorschläge mit Wahrscheinlichkeiten
            suggestions = []
            
            # Frequenzbasierte Vorschläge
            for inst in missing_high_frequency:
                freq_row = self.frequency_analysis[self.frequency_analysis['Installation'] == inst]
                if not freq_row.empty:
                    probability = freq_row.iloc[0]['Prozent'] / 100.0
                    verbandsnummer = self.verbandsnummer_mapping.get(inst, '')
                    suggestions.append({
                        'installation': inst,
                        'probability': probability,
                        'reason': 'frequency',
                        'details': f"Kommt in {freq_row.iloc[0]['Prozent']:.1f}% aller Gebäude vor",
                        'verbandsnummer': verbandsnummer
                    })
            
            # Korrelationsbasierte Vorschläge
            for item in building_results['missing_correlated'][:10]:  # Top 10
                verbandsnummer = self.verbandsnummer_mapping.get(item['installation'], '')
                suggestions.append({
                    'installation': item['installation'],
                    'probability': item['correlation'],
                    'reason': 'correlation',
                    'details': f"Korreliert stark ({item['correlation']:.2f}) mit {item['correlated_with']}",
                    'verbandsnummer': verbandsnummer
                })
            
            # Sortiere nach Wahrscheinlichkeit
            suggestions.sort(key=lambda x: x['probability'], reverse=True)
            building_results['suggestions'] = suggestions
            
            # Speichere Ergebnisse
            results['missing_installations'][building_id] = building_results
        
        # Erstelle Zusammenfassung
        self._create_summary(results)
        
        return results
    
    def _create_summary(self, results: Dict):
        """
        Erstellt eine Zusammenfassung der Analyseergebnisse.
        """
        logger.info("Erstelle Zusammenfassung...")
        
        total_buildings = results['buildings_analyzed']
        total_suggestions = 0
        frequency_suggestions = 0
        correlation_suggestions = 0
        total_mapped_installations = 0
        
        for building_id, building_data in results['missing_installations'].items():
            total_suggestions += len(building_data['suggestions'])
            total_mapped_installations += len(building_data['existing_mapped_installations'])
            
            for suggestion in building_data['suggestions']:
                if suggestion['reason'] == 'frequency':
                    frequency_suggestions += 1
                else:
                    correlation_suggestions += 1
        
        results['summary'] = {
            'total_buildings': total_buildings,
            'total_suggestions': total_suggestions,
            'frequency_suggestions': frequency_suggestions,
            'correlation_suggestions': correlation_suggestions,
            'total_mapped_installations': total_mapped_installations,
            'avg_suggestions_per_building': total_suggestions / total_buildings if total_buildings > 0 else 0,
            'avg_mapped_installations_per_building': total_mapped_installations / total_buildings if total_buildings > 0 else 0
        }
    
    def save_results(self, results: Dict):
        """
        Speichert die finale zusammengeführte Vorschlagsdatei.
        
        Args:
            results: Ergebnisse der Analyse
        """
        # Erstelle finale zusammengeführte Vorschläge
        self._create_final_merged_suggestions(results)
        
        logger.info("✓ Finale Vorschläge gespeichert in '03_final_results.xlsx'")
    
    def _create_final_merged_suggestions(self, results: Dict):
        """
        Erstellt finale zusammengeführte Vorschläge mit Bauteil-Priorisierung.
        """
        logger.info("Erstelle finale zusammengeführte Vorschläge...")
        
        # Lade Bauteil-Vorschläge falls vorhanden
        bauteil_suggestions = {}
        bauteil_file = "component_analysis_results/component_suggestions.xlsx"
        
        if os.path.exists(bauteil_file):
            try:
                # Prüfe ob das Sheet existiert
                excel_file = pd.ExcelFile(bauteil_file)
                if 'all_suggestions' in excel_file.sheet_names:
                    # Lade alle Vorschläge aus Bauteil-Analyse
                    bauteil_all_df = pd.read_excel(bauteil_file, sheet_name='all_suggestions')
                    
                    # Gruppiere nach Gebäude
                    for _, row in bauteil_all_df.iterrows():
                        gebaeude_id = row['building_id']
                        if gebaeude_id not in bauteil_suggestions:
                            bauteil_suggestions[gebaeude_id] = []
                        
                        bauteil_suggestions[gebaeude_id].append({
                            'installation': row['component'],
                            'probability': row['probability'],
                            'reason': 'component',
                            'details': row['reason'],
                            'verbandsnummer': row['article_number']
                        })
                    
                    logger.info(f"Bauteil-Vorschläge geladen: {len(bauteil_all_df)} Einträge")
                else:
                    logger.info("Keine Bauteil-Vorschläge vorhanden (Sheet 'all_suggestions' nicht gefunden)")
            except Exception as e:
                logger.warning(f"Konnte Bauteil-Vorschläge nicht laden: {e}")
        else:
            logger.info("Keine Bauteil-Vorschläge vorhanden (Datei nicht gefunden)")
        
        # Erstelle finale zusammengeführte Vorschläge
        final_suggestions = []
        
        for gebaeude_id, building_data in results['missing_installations'].items():
            # Sammle alle Vorschläge für dieses Gebäude
            gebaeude_suggestions = []
            
            # 1. Füge Bauteil-Vorschläge hinzu (hohe Priorität)
            if gebaeude_id in bauteil_suggestions:
                for bauteil_suggestion in bauteil_suggestions[gebaeude_id]:
                    gebaeude_suggestions.append({
                        'gebaeude_id': gebaeude_id,
                        'installation': bauteil_suggestion['installation'],
                        'probability': bauteil_suggestion['probability'],
                        'reason': bauteil_suggestion['reason'],
                        'details': bauteil_suggestion['details'],
                        'verbandsnummer': bauteil_suggestion['verbandsnummer'],
                        'priority': 1  # Höchste Priorität
                    })
            
            # 2. Füge andere Vorschläge hinzu
            for suggestion in building_data['suggestions']:
                gebaeude_suggestions.append({
                    'gebaeude_id': gebaeude_id,
                    'installation': suggestion['installation'],
                    'probability': suggestion['probability'],
                    'reason': suggestion['reason'],
                    'details': suggestion['details'],
                    'verbandsnummer': suggestion['verbandsnummer'],
                    'priority': 2  # Niedrigere Priorität
                })
            
            # 3. Entferne Duplikate basierend auf Verbandsnummer (Bauteil-Vorschläge priorisieren)
            unique_suggestions = {}
            for suggestion in gebaeude_suggestions:
                verbandsnummer = suggestion['verbandsnummer']
                
                if verbandsnummer == '' or verbandsnummer not in unique_suggestions:
                    # Keine Verbandsnummer oder noch nicht vorhanden
                    unique_suggestions[verbandsnummer] = suggestion
                elif suggestion['priority'] < unique_suggestions[verbandsnummer]['priority']:
                    # Höhere Priorität (Bauteil-Vorschlag)
                    unique_suggestions[verbandsnummer] = suggestion
            
            # 4. Füge zu finalen Vorschlägen hinzu
            final_suggestions.extend(unique_suggestions.values())
        
        # Sortiere nach Gebäude-ID und Wahrscheinlichkeit
        final_suggestions.sort(key=lambda x: (x['gebaeude_id'], -x['probability']))
        
        # Erstelle DataFrame und speichere
        if final_suggestions:
            final_df = pd.DataFrame(final_suggestions)
            final_df = final_df.drop('priority', axis=1)  # Entferne Priority-Spalte
            final_df.to_excel("03_final_results.xlsx", index=False)
            
            logger.info(f"Finale Vorschläge erstellt: {len(final_df)} Einträge")
        else:
            logger.info("Keine finalen Vorschläge erstellt")

def main():
    """
    Hauptfunktion für die finale Vollständigkeitsprüfung.
    """
    logger.info("=== FINALE VOLLSTÄNDIGKEITSPRÜFUNG STARTET ===")
    
    # Initialisiere Checker
    checker = FinalCompletenessChecker()
    
    # Lade Referenzdaten
    if not checker.load_reference_data():
        logger.error("Fehler beim Laden der Referenzdaten!")
        return
    
    # Lade Kundendatei
    kunde_building_installations = checker.load_customer_data("../cvs/Kundendatei.xlsx")
    if kunde_building_installations is None:
        logger.error("Fehler beim Laden der Kundendatei!")
        return
    
    # Führe Analyse durch
    results = checker.find_missing_installations(
        kunde_building_installations,
        frequency_threshold=50.0,  # Installationen, die in >50% aller Gebäude vorkommen
        correlation_threshold=0.7   # Mindestkorrelation für Vorschläge
    )
    
    # Speichere Ergebnisse
    checker.save_results(results)
    
    logger.info("=== FINALE VOLLSTÄNDIGKEITSPRÜFUNG ABGESCHLOSSEN ===")

if __name__ == "__main__":
    main() 
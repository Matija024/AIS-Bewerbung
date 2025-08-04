import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
from typing import List, Dict
import logging
import json
import os

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EPHeadingMapper:
    def __init__(self, model_name: str = 'T-Systems-onsite/cross-en-de-roberta-sentence-transformer'):
        """
        Initialisiert den EP Heading Mapper mit einem Sentence Transformer Modell.
        
        Args:
            model_name: Name des zu verwendenden Sentence Transformer Modells
        """
        self.model = SentenceTransformer(model_name)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Verwende Modell: {model_name} auf {self.device}")
    
    def load_similarity_results(self, input_dir: str = "intermediate_results") -> Dict[int, List[int]]:
        """
        Lädt die Ähnlichkeitsergebnisse aus Schritt 1.
        
        Args:
            input_dir: Eingabeverzeichnis
            
        Returns:
            Dictionary mit den ähnlichen Gruppen
        """
        with open(f"{input_dir}/01_similar_groups.json", 'r') as f:
            similar_groups = json.load(f)
        
        # Konvertiere String-Keys zurück zu Integers
        similar_groups = {int(k): v for k, v in similar_groups.items()}
        
        logger.info(f"Ähnlichkeitsergebnisse geladen: {len(similar_groups)} Gruppen")
        return similar_groups
    
    def create_representative_dataframe(self, kundendatei_path: str, similar_groups: Dict[int, List[int]]) -> pd.DataFrame:
        """
        Erstellt einen DataFrame mit nur den repräsentativen Einträgen.
        
        Args:
            kundendatei_path: Pfad zur Kundendatei
            similar_groups: Dictionary mit den ähnlichen Gruppen
            
        Returns:
            DataFrame mit repräsentativen Einträgen
        """
        df = pd.read_excel(kundendatei_path)
        
        # Erstelle DataFrame mit repräsentativen Einträgen
        representative_indices = list(similar_groups.keys())
        representative_df = df.iloc[representative_indices].copy()
        
        # Setze den Index auf die ursprünglichen Zeilenindizes
        representative_df.index = representative_indices
        
        # Füge Mapping-Informationen hinzu
        representative_df['original_indices'] = [similar_groups[idx] for idx in representative_indices]
        representative_df['representative_index'] = representative_indices
        
        logger.info(f"Repräsentativer DataFrame erstellt: {len(representative_df)} Einträge")
        
        return representative_df
    
    def map_to_ep_subheadings(self, representative_df: pd.DataFrame, ep_subheadings_path: str, 
                             similarity_threshold: float = 0.9) -> Dict[int, int]:
        """
        Mapped repräsentative Kundendatei-Einträge auf EP Katalog Überschriften.
        
        Args:
            representative_df: DataFrame mit repräsentativen Kundendatei-Einträgen
            ep_subheadings_path: Pfad zur EP_Katalog_subheadings.xlsx
            similarity_threshold: Schwellenwert für Mapping (0-1)
            
        Returns:
            Dictionary mit Mapping-Ergebnissen {kundendatei_index: ep_heading_index}
        """
        logger.info("Lade EP Katalog Überschriften...")
        df_ep = pd.read_excel(ep_subheadings_path)
        
        # Nur Überschriften aus EP-Datei filtern (Art beginnt mit "NG")
        ep_filtered = df_ep[df_ep["Art"].str.startswith("NG", na=False)]
        ep_texts = ep_filtered["Kurztext / Bezeichnung"].dropna().astype(str).tolist()
        
        # Speichere die ursprünglichen Indizes der gefilterten Zeilen
        ep_original_indices = ep_filtered.index.tolist()
        
        logger.info(f"EP Überschriften geladen: {len(ep_texts)} Einträge")
        
        # Spalten aus Kundendatei für den Vergleich
        kunde_spalten = ["Anlagenausprägung", "EQ-Klasse-Bezeichnung", "EQ-Bezeichnung"]
        
        # Berechne Embeddings für EP-Überschriften
        logger.info("Berechne Embeddings für EP-Überschriften...")
        emb_ep = self.model.encode(ep_texts, show_progress_bar=True, device=self.device)
        
        # Mapping-Ergebnisse
        mapping_results = {}
        
        # Für jeden repräsentativen Eintrag
        for idx, row in representative_df.iterrows():
            best_score = 0
            best_ep_idx = None
            
            # Vergleiche mit allen 3 Spalten
            for spalte in kunde_spalten:
                if pd.notna(row[spalte]) and str(row[spalte]).strip():
                    kunde_text = str(row[spalte])
                    
                    # Berechne Embedding für diesen Text
                    kunde_embedding = self.model.encode([kunde_text], device=self.device)
                    
                    # Berechne Ähnlichkeiten
                    similarities = cosine_similarity(kunde_embedding, emb_ep)[0]
                    
                    # Finde besten Match
                    max_idx = np.argmax(similarities)
                    max_score = similarities[max_idx]
                    
                    # Aktualisiere besten Score
                    if max_score > best_score:
                        best_score = max_score
                        best_ep_idx = max_idx
            
            # Prüfe Schwellenwert
            if best_score >= similarity_threshold:
                # Konvertiere gefilterten Index zu ursprünglichem Index
                original_ep_idx = ep_original_indices[best_ep_idx]
                mapping_results[idx] = original_ep_idx
                # Nur alle 10 Mappings loggen, um Terminal nicht zu überfluten
                if len(mapping_results) % 10 == 0:
                    logger.info(f"Mapping {len(mapping_results)}: Kunde {idx} -> EP Überschrift {original_ep_idx} (Score: {best_score:.4f})")
            else:
                # Nur alle 50 fehlgeschlagenen Mappings loggen
                if len([k for k, v in mapping_results.items()]) % 50 == 0:
                    logger.info(f"Kein Mapping für Kunde {idx} gefunden (bester Score: {best_score:.4f})")
        
        logger.info(f"Mapping abgeschlossen: {len(mapping_results)} von {len(representative_df)} Einträgen gemappt")
        
        return mapping_results
    
    def create_reduced_kundendatei(self, kundendatei_path: str, similar_groups: Dict[int, List[int]], 
                                  ep_mapping: Dict[int, int]) -> pd.DataFrame:
        """
        Erstellt eine verkleinerte Kundendatei mit zugewiesenen EP-Überschriften.
        
        Args:
            kundendatei_path: Pfad zur ursprünglichen Kundendatei
            similar_groups: Dictionary mit den ähnlichen Gruppen
            ep_mapping: Dictionary mit EP-Überschriften-Mapping
            
        Returns:
            DataFrame mit repräsentativen Einträgen und EP_idx Spalte
        """
        logger.info("Erstelle verkleinerte Kundendatei mit EP-Überschriften...")
        
        # Lade ursprüngliche Kundendatei
        df = pd.read_excel(kundendatei_path)
        
        # Erstelle DataFrame mit repräsentativen Einträgen
        representative_indices = list(similar_groups.keys())
        reduced_df = df.iloc[representative_indices].copy()
        
        # Setze den Index auf die ursprünglichen Zeilenindizes
        reduced_df.index = representative_indices
        
        # Füge EP_idx Spalte hinzu
        reduced_df['EP_idx'] = None
        
        # Weise EP-Überschriften zu
        for kunde_idx, ep_idx in ep_mapping.items():
            if kunde_idx in reduced_df.index:
                reduced_df.loc[kunde_idx, 'EP_idx'] = ep_idx
        
        # Füge Mapping-Informationen hinzu
        reduced_df['original_indices'] = [similar_groups[idx] for idx in representative_indices]
        reduced_df['representative_index'] = representative_indices
        
        logger.info(f"Verkleinerte Kundendatei erstellt: {len(reduced_df)} Einträge")
        logger.info(f"Davon {len(ep_mapping)} mit EP-Überschriften zugewiesen")
        
        return reduced_df
    
    def save_ep_mapping_results(self, ep_mapping: Dict[int, int], reduced_kundendatei: pd.DataFrame, 
                               output_dir: str = "intermediate_results"):
        """
        Speichert die EP-Mapping Ergebnisse.
        
        Args:
            ep_mapping: Dictionary mit EP-Überschriften-Mapping
            reduced_kundendatei: Verkleinerte Kundendatei mit EP_idx
            output_dir: Ausgabeverzeichnis
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. EP-Mapping Details (nur für interne Verwendung, nicht als Excel gespeichert)
        ep_mapping_data = []
        for kunde_idx, ep_idx in ep_mapping.items():
            ep_mapping_data.append({
                'kundendatei_index': kunde_idx,
                'ep_heading_index': ep_idx,
                'representative_index': kunde_idx
            })
        
        # Speichere als JSON für interne Verwendung
        with open(f"{output_dir}/02_ep_headings_mapping.json", 'w') as f:
            json.dump(ep_mapping_data, f, indent=2)
        
        # 2. Statistiken mit Threshold-Info
        stats = {
            'representative_entries': len(reduced_kundendatei),
            'mapped_with_ep_headings': len(ep_mapping),
            'remaining_for_alternative_method': len(reduced_kundendatei) - len(ep_mapping),
            'mapping_success_rate': len(ep_mapping) / len(reduced_kundendatei) * 100,
            'similarity_threshold': 0.9
        }
        
        stats_df = pd.DataFrame([stats])
        stats_df.to_excel(f"{output_dir}/02_ep_mapping_statistics.xlsx", index=False)
        
        # 3. Neue Datei: EP-Mapping Ergebnisse mit visueller Gegenüberstellung
        ep_mapping_result_data = []
        for rep_idx in reduced_kundendatei.index:
            # Hole Kundendatei-Daten für repräsentativen Index
            kunde_row = reduced_kundendatei.loc[rep_idx]
            
            # Erstelle Zusammenfassungstext für Kundendatei-Eintrag
            def create_kunde_summary(row):
                """Erstellt einen Zusammenfassungstext für einen Kundendatei-Eintrag."""
                drop_columns = ["WirtEinh", "EQ_übergeordnet", "Equipment", "EQ-Klasse", "EQ-Menge", "EP_idx", "original_indices", "representative_index"]
                available_columns = [col for col in row.index if col not in drop_columns]
                
                combined_text = []
                for col in available_columns:
                    value = row[col]
                    if pd.notna(value) and str(value).strip() != '' and str(value).strip() != 'nan':
                        combined_text.append(str(value).strip())
                
                return " | ".join(combined_text) if combined_text else "Keine Beschreibung verfügbar"
            
            kunde_summary = create_kunde_summary(kunde_row)
            
            # Hole EP-Überschrift (falls gemappt)
            ep_heading_text = ""
            if rep_idx in ep_mapping:
                ep_idx = ep_mapping[rep_idx]
                # Lade EP-Katalog für Überschrift
                ep_df = pd.read_excel("../cvs/EP_Katalog_subheadings.xlsx")
                if ep_idx < len(ep_df):
                    ep_row = ep_df.iloc[ep_idx]
                    ep_heading_text = ep_row.get('Kurztext / Bezeichnung', 'Keine Überschrift gefunden')
            
            ep_mapping_result_data.append({
                'representative_index': rep_idx,
                'kunde_summary': kunde_summary,
                'ep_heading_index': ep_mapping.get(rep_idx, None),
                'ep_heading_text': ep_heading_text,
                'mapping_success': rep_idx in ep_mapping,
                'group_size': len(reduced_kundendatei.loc[rep_idx, 'original_indices']) if 'original_indices' in reduced_kundendatei.columns else 0
            })
        
        ep_mapping_result_df = pd.DataFrame(ep_mapping_result_data)
        ep_mapping_result_df.to_excel(f"{output_dir}/02_ep_mapping_result.xlsx", index=False)
        
        logger.info(f"✓ EP-Mapping Ergebnisse gespeichert in '{output_dir}/'")
        logger.info(f"  - {len(reduced_kundendatei)} repräsentative Einträge")
        logger.info(f"  - {len(ep_mapping)} mit EP-Überschriften gemappt")
        logger.info(f"  - {len(reduced_kundendatei) - len(ep_mapping)} für alternatives Verfahren")

if __name__ == "__main__":
    mapper = EPHeadingMapper()
    
    # Lade Ähnlichkeitsergebnisse aus Schritt 1
    logger.info("=== SCHRITT 2: Lade Ähnlichkeitsergebnisse ===")
    similar_groups = mapper.load_similarity_results()
    
    # Erstelle repräsentativen DataFrame
    logger.info("=== SCHRITT 2: Erstelle repräsentativen DataFrame ===")
    representative_df = mapper.create_representative_dataframe("../cvs/Kundendatei.xlsx", similar_groups)
    
    # Mapped auf EP-Überschriften
    logger.info("=== SCHRITT 2: Mapped auf EP-Überschriften ===")
    ep_mapping = mapper.map_to_ep_subheadings(representative_df, "../cvs/EP_Katalog_subheadings.xlsx", similarity_threshold=0.9)
    
    # Erstelle verkleinerte Kundendatei
    logger.info("=== SCHRITT 2: Erstelle verkleinerte Kundendatei ===")
    reduced_kundendatei = mapper.create_reduced_kundendatei("../cvs/Kundendatei.xlsx", similar_groups, ep_mapping)
    
    # Speichere Ergebnisse
    mapper.save_ep_mapping_results(ep_mapping, reduced_kundendatei)
    
    logger.info("=== SCHRITT 2 ABGESCHLOSSEN ===")
    logger.info("Bereit für Schritt 3: Alternative Mapping-Verfahren") 
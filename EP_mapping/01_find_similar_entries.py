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

class SimilarityFinder:
    def __init__(self, model_name: str = 'T-Systems-onsite/cross-en-de-roberta-sentence-transformer'):
        """
        Initialisiert den Similarity Finder mit einem Sentence Transformer Modell.
        
        Args:
            model_name: Name des zu verwendenden Sentence Transformer Modells
        """
        self.model = SentenceTransformer(model_name)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Verwende Modell: {model_name} auf {self.device}")
        
    def find_similar_entries(self, kundendatei_path: str, similarity_threshold: float = 0.97) -> tuple[Dict[int, List[int]], pd.DataFrame]:
        """
        Findet ähnliche Einträge in der Kundendatei und gruppiert sie.
        
        Args:
            kundendatei_path: Pfad zur Kundendatei Excel-Datei
            similarity_threshold: Schwellenwert für Ähnlichkeit (0-1)
            
        Returns:
            Dictionary mit {representative_index: [similar_indices]}
        """
        logger.info("Lade Kundendatei...")
        df = pd.read_excel(kundendatei_path)
        
        # Alle Textspalten kombinieren für den Vergleich
        text_columns = df.select_dtypes(include=['object']).columns
        logger.info(f"Gefundene Textspalten: {list(text_columns)}")
        
        # Kombiniere alle Textspalten zu einem String
        df['combined_text'] = df[text_columns].fillna('').astype(str).agg(' '.join, axis=1)
        
        # Berechne Embeddings für alle Einträge
        logger.info("Berechne Embeddings...")
        texts = df['combined_text'].tolist()
        embeddings = self.model.encode(texts, show_progress_bar=True, device=self.device)
        
        # Berechne Cosinus-Ähnlichkeit zwischen allen Paaren
        logger.info("Berechne Ähnlichkeitsmatrix...")
        similarity_matrix = cosine_similarity(embeddings)
        
        # WICHTIG: Setze Diagonale auf 0 (Eintrag mit sich selbst)
        np.fill_diagonal(similarity_matrix, 0)
        
        # Überprüfe, dass keine Zeile gegen sich selbst gemappt wird
        diagonal_values = np.diag(similarity_matrix)
        if np.any(diagonal_values != 0):
            logger.error("FEHLER: Diagonale enthält noch Werte ungleich 0!")
            raise ValueError("Diagonale wurde nicht korrekt auf 0 gesetzt")
        else:
            logger.info("✓ Diagonale korrekt auf 0 gesetzt - keine Selbst-Mappings")
        
        # Finde ähnliche Einträge
        logger.info("Finde ähnliche Einträge...")
        similar_groups = {}
        processed_indices = set()
        
        for i in range(len(similarity_matrix)):
            if i in processed_indices:
                continue
                
            # Finde alle ähnlichen Einträge für Index i (ohne den repräsentativen Index selbst)
            similar_indices = np.where(similarity_matrix[i] >= similarity_threshold)[0]
            # Entferne den repräsentativen Index aus den ähnlichen Indizes
            similar_indices = similar_indices[similar_indices != i]
            
            if len(similar_indices) > 0:
                # Speichere nur die ähnlichen Indizes (ohne repräsentativen Index)
                similar_groups[i] = similar_indices.tolist()
                
                # Markiere alle Indizes als verarbeitet
                processed_indices.add(i)
                processed_indices.update(similar_indices)
                
                logger.info(f"Gruppe gefunden: Repräsentant {i} mit {len(similar_indices)} ähnlichen Einträgen")
                logger.info(f"  Ähnliche Indizes: {similar_indices.tolist()}")
        
        # Füge einzelne Einträge hinzu (die keine ähnlichen haben)
        for i in range(len(similarity_matrix)):
            if i not in processed_indices:
                similar_groups[i] = []
        
        logger.info(f"Insgesamt {len(similar_groups)} Gruppen gefunden")
        
        return similar_groups, df
    
    def save_similarity_results(self, similar_groups: Dict[int, List[int]], kundendatei_df: pd.DataFrame, output_dir: str = "intermediate_results"):
        """
        Speichert die Ähnlichkeitsergebnisse.
        
        Args:
            similar_groups: Dictionary mit den ähnlichen Gruppen
            kundendatei_df: DataFrame der Kundendatei für Zusammenfassungstexte
            output_dir: Ausgabeverzeichnis
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Speichere als JSON für einfache Wiederverwendung
        with open(f"{output_dir}/01_similar_groups.json", 'w') as f:
            json.dump(similar_groups, f, indent=2)
        
        # Erstelle Zusammenfassungstexte für die Kundendatei
        def create_summary_text(row):
            """Erstellt einen Zusammenfassungstext für eine Zeile."""
            drop_columns = ["WirtEinh", "EQ_übergeordnet", "Equipment", "EQ-Klasse", "EQ-Menge"]
            available_columns = [col for col in row.index if col not in drop_columns]
            
            combined_text = []
            for col in available_columns:
                value = row[col]
                if pd.notna(value) and str(value).strip() != '' and str(value).strip() != 'nan':
                    combined_text.append(str(value).strip())
            
            return " | ".join(combined_text) if combined_text else "Keine Beschreibung verfügbar"
        
        # Erstelle auch eine Excel-Datei für bessere Übersicht mit visuellen Vergleich
        grouping_data = []
        for rep_idx, similar_indices in similar_groups.items():
            # Hole Zusammenfassungstext für repräsentativen Index
            rep_summary = create_summary_text(kundendatei_df.iloc[rep_idx])
            
            # Hole Zusammenfassungstext für ersten ähnlichen Index (falls vorhanden)
            first_similar_summary = ""
            if len(similar_indices) > 0:
                first_similar_summary = create_summary_text(kundendatei_df.iloc[similar_indices[0]])
            
            grouping_data.append({
                'representative_index': rep_idx,
                'representative_summary': rep_summary,
                'similar_indices': str(similar_indices),
                'first_similar_summary': first_similar_summary,
                'group_size': len(similar_indices),
                'is_single_entry': len(similar_indices) == 0
            })
        
        grouping_df = pd.DataFrame(grouping_data)
        grouping_df.to_excel(f"{output_dir}/01_similarity_grouping.xlsx", index=False)
        
        # Statistiken (korrigiert)
        total_entries = len(kundendatei_df)  # Tatsächliche Anzahl aus DataFrame
        representative_entries = len(similar_groups)
        reduction_percentage = (1 - representative_entries / total_entries) * 100
        
        stats = {
            'total_original_entries': total_entries,
            'representative_entries': representative_entries,
            'reduction_percentage': reduction_percentage,
            'similarity_threshold': 0.97
        }
        
        stats_df = pd.DataFrame([stats])
        stats_df.to_excel(f"{output_dir}/01_similarity_statistics.xlsx", index=False)
        
        logger.info(f"✓ Ähnlichkeitsergebnisse gespeichert in '{output_dir}/'")
        logger.info(f"  - {representative_entries} repräsentative Einträge")
        logger.info(f"  - {total_entries} ursprüngliche Einträge")
        logger.info(f"  - {reduction_percentage:.1f}% Reduktion")

if __name__ == "__main__":
    finder = SimilarityFinder()
    
    # Finde ähnliche Einträge
    logger.info("=== SCHRITT 1: Finde ähnliche Einträge ===")
    similar_groups, kundendatei_df = finder.find_similar_entries("../cvs/Kundendatei.xlsx", similarity_threshold=0.97)
    
    # Speichere Ergebnisse
    finder.save_similarity_results(similar_groups, kundendatei_df)
    
    logger.info("=== SCHRITT 1 ABGESCHLOSSEN ===")
    logger.info("Bereit für Schritt 2: EP-Überschriften Mapping") 
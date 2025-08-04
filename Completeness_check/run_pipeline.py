#!/usr/bin/env python3
"""
Completeness_check Pipeline Runner

Führt alle Skripte der Completeness_check Pipeline in der richtigen Reihenfolge aus:
1. 01_correlation_matrix.py
2. 02_frequency_analysis.py
3. component_analysis.py
4. 03_completeness_check.py

Autor: AI Assistant
Datum: 2024
"""

import subprocess
import sys
import os
import logging
from pathlib import Path

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pipeline_run.log')
    ]
)
logger = logging.getLogger(__name__)

def run_script(script_name: str, description: str) -> bool:
    """
    Führt ein Python-Skript aus und gibt True zurück, wenn es erfolgreich war.
    
    Args:
        script_name: Name des Skripts (z.B. "01_correlation_matrix.py")
        description: Beschreibung was das Skript macht
        
    Returns:
        True wenn erfolgreich, False wenn Fehler
    """
    logger.info(f"=== STARTE: {description} ===")
    logger.info(f"Führe aus: {script_name}")
    
    try:
        # Führe Skript aus
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            logger.info(f"✓ ERFOLGREICH: {description}")
            if result.stdout:
                logger.info(f"Ausgabe:\n{result.stdout}")
            return True
        else:
            logger.error(f"✗ FEHLER: {description}")
            logger.error(f"Return Code: {result.returncode}")
            if result.stderr:
                logger.error(f"Fehlerausgabe:\n{result.stderr}")
            if result.stdout:
                logger.info(f"Standardausgabe:\n{result.stdout}")
            return False
            
    except Exception as e:
        logger.error(f"✗ AUSNAHME: {description}")
        logger.error(f"Fehler: {e}")
        return False

def check_prerequisites() -> bool:
    """
    Prüft ob alle Voraussetzungen erfüllt sind.
    
    Returns:
        True wenn alle Voraussetzungen erfüllt sind
    """
    logger.info("=== PRÜFE VORAUSSETZUNGEN ===")
    
    # Prüfe ob Eingabedateien existieren
    required_files = [
        "../cvs/Beispielobjekte.xlsx",
        "../cvs/Kundendatei.xlsx"
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            logger.error(f"✗ Eingabedatei nicht gefunden: {file_path}")
            return False
        else:
            logger.info(f"✓ Eingabedatei gefunden: {file_path}")
    
    # Prüfe ob Python-Skripte existieren
    required_scripts = [
        "01_correlation_matrix.py",
        "02_frequency_analysis.py",
        "03_completeness_check.py",
        "component_analysis.py"
    ]
    
    for script in required_scripts:
        if not os.path.exists(script):
            logger.error(f"✗ Skript nicht gefunden: {script}")
            return False
        else:
            logger.info(f"✓ Skript gefunden: {script}")
    
    logger.info("✓ Alle Voraussetzungen erfüllt")
    return True

def main():
    """
    Hauptfunktion - führt die gesamte Pipeline aus.
    """
    logger.info("=== COMPLETENESS_CHECK PIPELINE STARTET ===")
    logger.info(f"Aktuelles Verzeichnis: {os.getcwd()}")
    
    # Prüfe Voraussetzungen
    if not check_prerequisites():
        logger.error("Voraussetzungen nicht erfüllt! Pipeline wird abgebrochen.")
        sys.exit(1)
    
    # Pipeline-Schritte
    pipeline_steps = [
        {
            "script": "01_correlation_matrix.py",
            "description": "Korrelationsmatrix erstellen"
        },
        {
            "script": "02_frequency_analysis.py", 
            "description": "Frequenzanalyse durchführen"
        },
        {
            "script": "component_analysis.py",
            "description": "Komponenten-Analyse"
        },
        {
            "script": "03_completeness_check.py",
            "description": "Finale Vollständigkeitsprüfung"
        }
    ]
    
    # Führe Pipeline-Schritte aus
    success_count = 0
    total_steps = len(pipeline_steps)
    
    for i, step in enumerate(pipeline_steps, 1):
        logger.info(f"\n--- SCHRITT {i}/{total_steps} ---")
        
        if run_script(step["script"], step["description"]):
            success_count += 1
        else:
            logger.error(f"Pipeline-Schritt {i} fehlgeschlagen!")
            logger.error("Pipeline wird abgebrochen.")
            sys.exit(1)
    
    # Pipeline-Ergebnis
    logger.info(f"\n=== PIPELINE ABGESCHLOSSEN ===")
    logger.info(f"Erfolgreiche Schritte: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        logger.info("🎉 ALLE SCHRITTE ERFOLGREICH!")
        logger.info("\n=== ERWARTETE AUSGABEDATEIEN ===")
        logger.info("✓ 01_correlation_matrix.xlsx")
        logger.info("✓ 02_frequency_analysis.xlsx") 
        logger.info("✓ component_analysis_results/component_suggestions.xlsx")
        logger.info("✓ 03_final_results.xlsx")
        logger.info("\nPipeline erfolgreich abgeschlossen! 🚀")
    else:
        logger.error(f"❌ {total_steps - success_count} Schritte fehlgeschlagen!")
        sys.exit(1)

if __name__ == "__main__":
    main() 
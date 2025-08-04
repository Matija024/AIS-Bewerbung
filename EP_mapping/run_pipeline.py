#!/usr/bin/env python3
"""
EP-Mapping Pipeline Master Script

Führt die gesamte EP-Mapping Pipeline aus:
1. Finde ähnliche Einträge
2. Mapped auf EP-Überschriften
3. Alternative Mapping-Verfahren
4. Finale Zusammenführung

Autor: AI Assistant
Datum: 2025-08-03
"""

import subprocess
import sys
import os
import logging
from pathlib import Path

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_step(step_number: int, step_name: str, script_path: str):
    """
    Führt einen einzelnen Schritt der Pipeline aus.
    
    Args:
        step_number: Nummer des Schritts
        step_name: Name des Schritts
        script_path: Pfad zum Skript
    """
    logger.info(f"=== SCHRITT {step_number}: {step_name} ===")
    
    if not os.path.exists(script_path):
        logger.error(f"Skript nicht gefunden: {script_path}")
        return False
    
    try:
        # Führe Skript aus
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, check=True)
        
        # Zeige Ausgabe
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        logger.info(f"✓ Schritt {step_number} erfolgreich abgeschlossen")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Fehler in Schritt {step_number}: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False
    except Exception as e:
        logger.error(f"❌ Unerwarteter Fehler in Schritt {step_number}: {e}")
        return False

def check_prerequisites():
    """
    Überprüft, ob alle Voraussetzungen erfüllt sind.
    
    Returns:
        True wenn alle Voraussetzungen erfüllt sind
    """
    logger.info("Überprüfe Voraussetzungen...")
    
    # Überprüfe Dateien
    required_files = [
        "cvs/Kundendatei.xlsx",
        "cvs/EP_Katalog_subheadings.xlsx",
        "cvs/EP_Katalog.xlsx"
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            logger.error(f"Erforderliche Datei nicht gefunden: {file_path}")
            return False
    
    # Überprüfe Skripte
    required_scripts = [
        "01_find_similar_entries.py",
        "02_map_ep_headings.py",
        "03_openai_mapping.py",
        "04_article_number_mapping.py"
    ]
    
    for script in required_scripts:
        script_path = os.path.join(os.path.dirname(__file__), script)
        if not os.path.exists(script_path):
            logger.error(f"Erforderliches Skript nicht gefunden: {script_path}")
            return False
    
    logger.info("✓ Alle Voraussetzungen erfüllt")
    return True

def main():
    """
    Hauptfunktion der Pipeline.
    """
    logger.info("🚀 Starte EP-Mapping Pipeline")
    
    # Überprüfe Voraussetzungen
    if not check_prerequisites():
        logger.error("❌ Voraussetzungen nicht erfüllt - Pipeline wird abgebrochen")
        return False
    
    # Definiere Pipeline-Schritte
    steps = [
        (1, "Finde ähnliche Einträge", "01_find_similar_entries.py"),
        (2, "Mapped auf EP-Überschriften", "02_map_ep_headings.py"),
        (3, "OpenAI API Mapping", "03_openai_mapping.py"),
        (4, "Artikelnummer-Mapping", "04_article_number_mapping.py")
    ]
    
    # Führe Schritte aus
    for step_number, step_name, script_name in steps:
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        
        success = run_step(step_number, step_name, script_path)
        
        if not success:
            logger.error(f"❌ Pipeline fehlgeschlagen in Schritt {step_number}")
            logger.info("💡 Tipp: Du kannst einzelne Schritte manuell ausführen:")
            logger.info(f"   python {script_path}")
            return False
        
        logger.info(f"Schritt {step_number} abgeschlossen - fahre mit nächstem Schritt fort")
    
    # Pipeline erfolgreich abgeschlossen
    logger.info("🎉 EP-Mapping Pipeline erfolgreich abgeschlossen!")
    logger.info("📁 Ergebnisse verfügbar in:")
    logger.info("   - intermediate_results/ (Zwischenergebnisse)")
    logger.info("")
    logger.info("🎉 Vollständige Pipeline abgeschlossen!")
    logger.info("📁 Finale Ergebnisse verfügbar in:")
    logger.info("   - cvs/kundendatei_final.xlsx")
    logger.info("   - cvs/kundendatei_final.csv")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
import pandas as pd
import numpy as np
import logging

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_installation_frequency():
    """
    Analysiert die Häufigkeit von Installationen in Gebäuden.
    """
    logger.info("=== FREQUENZANALYSE STARTET ===")
    
    # === 1. Datei laden ===
    file_path = "../cvs/Beispielobjekte.xlsx"
    sheet_name = "Anlagen"
    
    logger.info(f"Lade Daten aus: {file_path}")
    data = pd.read_excel(file_path, sheet_name=sheet_name, header=0, engine="openpyxl")
    
    logger.info(f"Geladene Daten: {len(data)} Zeilen")
    logger.info(f"Spalten: {list(data.columns)}")
    
    # === 2. Daten vorbereiten ===
    # Pivot-Tabelle: Gebäude-ID vs. Installationen (One-Hot-Encoding)
    logger.info("Erstelle Gebäude-Installation Matrix...")
    building_installations = (
        data.groupby(["Gebäude-ID", "AKS-Bezeichnung"])
        .size()
        .unstack(fill_value=0)           # jede Installation eigene Spalte
    )
    
    # Alles in 1/0 umwandeln (vorhanden = 1, sonst 0)
    building_installations = (building_installations > 0).astype(int)
    
    logger.info(f"Gebäude-Installation Matrix erstellt: {building_installations.shape}")
    logger.info(f"Anzahl Gebäude: {len(building_installations)}")
    logger.info(f"Anzahl Installationen: {len(building_installations.columns)}")
    
    # === 3. Frequenzanalyse ===
    logger.info("Berechne Frequenzanalyse...")
    
    # Berechne Häufigkeit jeder Installation
    installation_frequency = building_installations.sum(axis=0)  # Summe über alle Gebäude
    total_buildings = len(building_installations)
    installation_percentage = (installation_frequency / total_buildings) * 100
    
    # Erstelle DataFrame mit Frequenzanalyse
    frequency_analysis = pd.DataFrame({
        'Installation': installation_frequency.index,
        'Anzahl_Gebaeude': installation_frequency.values,
        'Gesamt_Gebaeude': total_buildings,
        'Prozent': installation_percentage.values
    })
    
    # Sortiere nach Häufigkeit (absteigend)
    frequency_analysis = frequency_analysis.sort_values('Prozent', ascending=False)
    
    # === 4. Kategorisierung ===
    logger.info("Kategorisiere Installationen...")
    
    # Definiere Kategorien basierend auf Häufigkeit
    frequency_analysis['Kategorie'] = pd.cut(
        frequency_analysis['Prozent'],
        bins=[0, 10, 25, 50, 75, 100],
        labels=['Sehr selten (0-10%)', 'Selten (10-25%)', 'Mittel (25-50%)', 
                'Häufig (50-75%)', 'Sehr häufig (75-100%)']
    )
    
    # === 5. Zusätzliche Statistiken ===
    logger.info("Berechne zusätzliche Statistiken...")
    
    # Durchschnittliche Anzahl Installationen pro Gebäude
    installations_per_building = building_installations.sum(axis=1)
    avg_installations = installations_per_building.mean()
    median_installations = installations_per_building.median()
    
    # Gebäude mit den meisten/wenigsten Installationen
    buildings_most_installations = installations_per_building.nlargest(10)
    buildings_least_installations = installations_per_building.nsmallest(10)
    
    # === 6. Ergebnisse speichern ===
    logger.info("Speichere Ergebnisse...")
    
    # Hauptanalyse
    output_path_frequency = "02_frequency_analysis.xlsx"
    frequency_analysis.to_excel(output_path_frequency, index=False)
    

    
    # === 7. Ausgabe ===
    logger.info("=== FREQUENZANALYSE ABGESCHLOSSEN ===")
    logger.info(f"✓ Frequenzanalyse gespeichert: {output_path_frequency}")
    
    # Zeige Top-Ergebnisse
    logger.info("\n=== TOP 10 HÄUFIGSTE INSTALLATIONEN ===")
    for i, row in frequency_analysis.head(10).iterrows():
        logger.info(f"{row['Installation']}: {row['Prozent']:.1f}% ({row['Anzahl_Gebaeude']}/{row['Gesamt_Gebaeude']} Gebäude)")
    
    logger.info(f"\n=== ZUSAMMENFASSUNG ===")
    logger.info(f"Gesamtgebäude: {total_buildings}")
    logger.info(f"Eindeutige Installationen: {len(building_installations.columns)}")
    logger.info(f"Durchschnitt Installationen pro Gebäude: {avg_installations:.1f}")
    
    return frequency_analysis, building_installations

if __name__ == "__main__":
    frequency_analysis, building_installations = analyze_installation_frequency() 
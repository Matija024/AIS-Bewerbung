import pandas as pd

# === 1. Datei laden ===
file_path = "../cvs/Beispielobjekte.xlsx"   # Pfad zur Datei anpassen!
sheet_name = "Anlagen"

# Daten einlesen
data = pd.read_excel(file_path, sheet_name=sheet_name, header=0, engine="openpyxl")

# === 2. Daten vorbereiten ===
# Pivot-Tabelle: Gebäude-ID vs. Installationen (One-Hot-Encoding)
building_installations = (
    data.groupby(["Gebäude-ID", "AKS-Bezeichnung"])
    .size()
    .unstack(fill_value=0)           # jede Installation eigene Spalte
)

# Alles in 1/0 umwandeln (vorhanden = 1, sonst 0)
building_installations = (building_installations > 0).astype(int)

# === 3. Korrelationsmatrix berechnen ===
correlation_matrix = building_installations.corr()

# === 4. Ergebnisse speichern ===
output_path_matrix = "01_correlation_matrix.xlsx"
correlation_matrix.to_excel(output_path_matrix)

print(f"Korrelationsmatrix gespeichert unter: {output_path_matrix}")
print(f"Matrix-Größe: {correlation_matrix.shape}")
print(f"Anzahl Installationen: {len(correlation_matrix.columns)}")

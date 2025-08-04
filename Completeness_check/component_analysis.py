import pandas as pd
import numpy as np
import logging
import os
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComponentAnalyzer:
    def __init__(self):
        """
        Initializes the Component Analyzer.
        """
        self.system_component_mapping = {}
        self.customer_data = None
        
    def load_reference_data(self) -> bool:
        """
        Loads reference data and creates system-component mapping.
        """
        logger.info("Loading reference data...")
        
        # Load example objects
        file_path = "../cvs/Beispielobjekte.xlsx"
        sheet_name = "Anlagen"
        
        try:
            data = pd.read_excel(file_path, sheet_name=sheet_name, header=0, engine="openpyxl")
            logger.info(f"Reference data loaded: {len(data)} rows")
        except Exception as e:
            logger.error(f"Error loading reference data: {e}")
            return False
        
        # Check required columns
        required_columns = ['Anlagen-ID', 'AKS-Bezeichnung', 'Anlagentyp', 'Verbandsnummer']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            logger.error(f"Missing columns in reference data: {missing_columns}")
            return False
        
        # Create system-component mapping
        self._create_system_component_mapping(data)
        
        return True
    
    def _create_system_component_mapping(self, data: pd.DataFrame):
        """
        Creates mapping between systems and their components.
        """
        logger.info("Creating system-component mapping...")
        
        # 1. Find all systems with association number
        systems_with_association = data[
            (data['Anlagentyp'] == 'Anlage') & 
            (data['Verbandsnummer'].notna()) & 
            (data['Verbandsnummer'] != '')
        ].copy()
        
        logger.info(f"Systems with association number found: {len(systems_with_association)}")
        
        # 2. Find all components with association number
        components_with_association = data[
            (data['Anlagentyp'] == 'Bauteil') & 
            (data['Verbandsnummer'].notna()) & 
            (data['Verbandsnummer'] != '')
        ].copy()
        
        logger.info(f"Components with association number found: {len(components_with_association)}")
        
        # 3. Create mapping: System -> [Components]
        system_component_dict = {}
        
        for _, system in systems_with_association.iterrows():
            system_id = system['Anlagen-ID']
            association_number = system['Verbandsnummer']
            aks_designation = system['AKS-Bezeichnung']
            
            # Find all components that belong to this system
            related_components = components_with_association[
                components_with_association['Bauteil der Anlage'] == system_id
            ]
            
            if len(related_components) > 0:
                component_list = []
                for _, component in related_components.iterrows():
                    component_list.append({
                        'component_id': component['Anlagen-ID'],
                        'aks_designation': component['AKS-Bezeichnung'],
                        'association_number': component['Verbandsnummer']
                    })
                
                system_component_dict[association_number] = {
                    'system_id': system_id,
                    'aks_designation': aks_designation,
                    'association_number': association_number,
                    'components': component_list
                }
        
        self.system_component_mapping = system_component_dict
        
        logger.info(f"System-component mapping created: {len(self.system_component_mapping)} systems with components")
    
    def load_customer_data(self, customer_file_path: str) -> bool:
        """
        Loads the customer file.
        """
        logger.info(f"Loading customer file: {customer_file_path}")
        
        try:
            self.customer_data = pd.read_excel(customer_file_path)
            logger.info(f"Customer file loaded: {len(self.customer_data)} rows")
            
            # Check if WirtEinh column exists
            if 'WirtEinh' not in self.customer_data.columns:
                logger.error("Column 'WirtEinh' not found in customer file!")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading customer file: {e}")
            return False
    
    def find_missing_components(self) -> Dict:
        """
        Finds missing components based on association number matching.
        """
        logger.info("Analyzing missing components...")
        
        if self.customer_data is None:
            logger.error("Customer file not loaded!")
            return {}
        
        # Group by buildings
        building_groups = self.customer_data.groupby('WirtEinh')
        
        results = {}
        
        for building_id, building_data in building_groups:
            logger.info(f"Analyzing building: {building_id}")
            
            building_results = {
                'building_id': building_id,
                'systems_with_article_number': [],
                'missing_components': [],
                'suggestions': []
            }
            
            # 1. Find systems with article number
            systems_with_article_number = []
            for _, row in building_data.iterrows():
                # Check if article number is present (can have various column names)
                article_number_columns = [col for col in self.customer_data.columns if 'artikel' in col.lower() or 'verband' in col.lower()]
                
                for column in article_number_columns:
                    if pd.notna(row[column]) and row[column] != '':
                        systems_with_article_number.append({
                            'aks_designation': row.get('AKS-Bezeichnung', 'Unknown'),
                            'article_number': row[column],
                            'column': column
                        })
                        break  # Use only the first found article number
            
            building_results['systems_with_article_number'] = systems_with_article_number
            
            # 2. Find missing components
            missing_components = []
            
            for system in systems_with_article_number:
                article_number = system['article_number']
                
                # Check if this article number corresponds to a system with components
                if article_number in self.system_component_mapping:
                    system_data = self.system_component_mapping[article_number]
                    
                    # Check which components are already present
                    existing_components = []
                    for _, row in building_data.iterrows():
                        for column in article_number_columns:
                            if pd.notna(row[column]) and row[column] != '':
                                existing_components.append(row[column])
                    
                    # Find missing components
                    for component in system_data['components']:
                        if component['association_number'] not in existing_components:
                            missing_components.append({
                                'system_aks': system_data['aks_designation'],
                                'system_article_number': article_number,
                                'component_aks': component['aks_designation'],
                                'component_article_number': component['association_number'],
                                'reason': f"Belongs to system: {system_data['aks_designation']}"
                            })
            
            building_results['missing_components'] = missing_components
            
            # 3. Create suggestions
            for component in missing_components:
                building_results['suggestions'].append({
                    'component': component['component_aks'],
                    'article_number': component['component_article_number'],
                    'reason': component['reason'],
                    'probability': 0.9  # High probability due to direct assignment
                })
            
            results[building_id] = building_results
        
        return results
    
    def save_results(self, results: Dict, output_dir: str = "component_analysis_results"):
        """
        Saves the component analysis results.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info("Saving component analysis results...")
        
        # Create Excel writer
        output_file = f"{output_dir}/component_suggestions.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # 1. Overview
            overview_data = []
            for building_id, building_data in results.items():
                overview_data.append({
                    'Building_ID': building_id,
                    'Systems_with_Article_Number': len(building_data['systems_with_article_number']),
                    'Missing_Components': len(building_data['missing_components']),
                    'Suggestions': len(building_data['suggestions'])
                })
            
            overview_df = pd.DataFrame(overview_data)
            overview_df.to_excel(writer, sheet_name='overview', index=False)
            
            # 2. Detailed analysis per building
            for building_id, building_data in results.items():
                sheet_name = f"Building_{building_id}"[:31]  # Excel sheet names max 31 characters
                
                # Create DataFrame for this building
                building_suggestions = []
                for suggestion in building_data['suggestions']:
                    building_suggestions.append({
                        'Component': suggestion['component'],
                        'Article_Number': suggestion['article_number'],
                        'Reason': suggestion['reason'],
                        'Probability': suggestion['probability']
                    })
                
                if building_suggestions:
                    building_df = pd.DataFrame(building_suggestions)
                    building_df.to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    # Empty table for buildings without suggestions
                    empty_df = pd.DataFrame(columns=['Component', 'Article_Number', 'Reason', 'Probability'])
                    empty_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # 3. All suggestions together
            all_suggestions = []
            for building_id, building_data in results.items():
                for suggestion in building_data['suggestions']:
                    all_suggestions.append({
                        'building_id': building_id,
                        'component': suggestion['component'],
                        'article_number': suggestion['article_number'],
                        'reason': suggestion['reason'],
                        'probability': suggestion['probability']
                    })
            
            if all_suggestions:
                all_suggestions_df = pd.DataFrame(all_suggestions)
                all_suggestions_df.to_excel(writer, sheet_name='all_suggestions', index=False)
        
        logger.info(f"✓ Component analysis results saved: {output_file}")

def main():
    """
    Main function for component analysis.
    """
    logger.info("=== COMPONENT ANALYSIS STARTING ===")
    
    # Initialize analyzer
    analyzer = ComponentAnalyzer()
    
    # Load reference data
    if not analyzer.load_reference_data():
        logger.error("Error loading reference data!")
        return
    
    # Load customer file
    if not analyzer.load_customer_data("../cvs/Kundendatei.xlsx"):
        logger.error("Error loading customer file!")
        return
    
    # Perform analysis
    results = analyzer.find_missing_components()
    
    # Save results
    analyzer.save_results(results)
    
    logger.info("=== COMPONENT ANALYSIS COMPLETED ===")

if __name__ == "__main__":
    main() 
import pandas as pd
import sqlite3
from pathlib import Path
import logging
from typing import Set, Dict, List
from collections import defaultdict
import os
import json
import re

logger = logging.getLogger(__name__)

class DimProcScanner:
    """
    Utility to scan for CPT codes missing from dim_proc table.
    Helps identify codes that need to be added to the reference table.
    """
    
    def __init__(self, db_path: str = None, staging_path: str = None):
        """
        Initialize the scanner.
        
        Args:
            db_path: Path to SQLite database (default: brsystem.db in current directory)
            staging_path: Path to staging folder with JSON files (default: staging/ in current directory)
        """
        # Default to brsystem.db in current directory if not specified
        if db_path is None:
            db_path = "brsystem.db"
            
        # Default to staging/ in current directory if not specified
        if staging_path is None:
            staging_path = "staging"
            
        self.db_path = db_path
        self.staging_path = staging_path
        self._verify_db()
        self._verify_staging()
        
    def _verify_db(self):
        """Verify database exists and has required tables."""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}. Please specify the correct path with --db")
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dim_proc'")
            if not cursor.fetchone():
                raise ValueError("dim_proc table not found in database")
    
    def _verify_staging(self):
        """Verify staging directory exists."""
        if not Path(self.staging_path).exists():
            raise FileNotFoundError(f"Staging directory not found: {self.staging_path}. Please specify the correct path with --staging")
    
    def _extract_cpt_from_json(self, json_path: str) -> Dict[str, Dict]:
        """Extract CPT codes and their details from a JSON file."""
        cpt_details = {}
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            # Look specifically for CPT codes in service_lines
            if 'service_lines' in data:
                for service_line in data['service_lines']:
                    if 'cpt_code' in service_line:
                        cpt_code = service_line['cpt_code']
                        # Verify it's a valid CPT code (letter + 4 digits or 5 digits)
                        if isinstance(cpt_code, str) and re.match(r'^[A-Z]?\d{4,5}$', cpt_code):
                            if cpt_code not in cpt_details:
                                cpt_details[cpt_code] = {
                                    'files': [],
                                    'modifiers': set(),
                                    'units': set()
                                }
                            cpt_details[cpt_code]['files'].append(Path(json_path).name)
                            if 'modifiers' in service_line:
                                cpt_details[cpt_code]['modifiers'].update(service_line['modifiers'])
                            if 'units' in service_line:
                                cpt_details[cpt_code]['units'].add(str(service_line['units']))
            
            return cpt_details
        except Exception as e:
            logger.warning(f"Error processing {json_path}: {e}")
            return {}

    def analyze_json_codes(self) -> Dict:
        """
        Analyze CPT codes found in JSON files and compare against dim_proc.
        
        Returns:
            Dict with analysis results focusing on missing/uncategorized codes
        """
        results = {
            'missing_from_dim_proc': set(),  # Codes not in dim_proc at all
            'no_category': set(),  # Codes in dim_proc but with no category
            'stats': {
                'total_unique_cpts': 0,
                'total_in_dim_proc': 0,
                'total_missing': 0,
                'total_uncategorized': 0
            }
        }
        
        # First get all unique CPT codes from JSON files
        json_files = list(Path(self.staging_path).glob('**/*.json'))
        all_cpt_codes = set()
        
        for json_file in json_files:
            file_details = self._extract_cpt_from_json(str(json_file))
            all_cpt_codes.update(file_details.keys())
        
        results['stats']['total_unique_cpts'] = len(all_cpt_codes)
        logger.info(f"Found {len(all_cpt_codes)} unique CPT codes in JSON files")
        
        # Now check these against dim_proc
        with sqlite3.connect(self.db_path) as conn:
            # Get all codes and their categories from dim_proc
            dim_proc_df = pd.read_sql_query("""
                SELECT proc_cd, proc_category 
                FROM dim_proc 
                WHERE proc_cd IS NOT NULL
            """, conn)
            
            dim_proc_codes = set(dim_proc_df['proc_cd'])
            results['stats']['total_in_dim_proc'] = len(dim_proc_codes)
            
            # Find codes missing from dim_proc entirely
            missing_codes = all_cpt_codes - dim_proc_codes
            results['missing_from_dim_proc'] = missing_codes
            results['stats']['total_missing'] = len(missing_codes)
            
            if missing_codes:
                logger.info("\nCPT codes missing from dim_proc:")
                for code in sorted(missing_codes):
                    logger.info(f"  - {code}")
            
            # Find codes with no category
            codes_with_no_category = set(
                dim_proc_df[
                    (dim_proc_df['proc_cd'].isin(all_cpt_codes)) & 
                    ((dim_proc_df['proc_category'].isna()) | (dim_proc_df['proc_category'] == '') | (dim_proc_df['proc_category'] == '0'))
                ]['proc_cd']
            )
            results['no_category'] = codes_with_no_category
            results['stats']['total_uncategorized'] = len(codes_with_no_category)
            
            if codes_with_no_category:
                logger.info("\nCPT codes in dim_proc but with no category:")
                for code in sorted(codes_with_no_category):
                    logger.info(f"  - {code}")
            
        return results

    def analyze_line_items_codes(self) -> Dict:
        """
        Analyze CPT codes found in line_items table and compare against dim_proc.
        
        Returns:
            Dict with analysis results focusing on missing/uncategorized codes
        """
        results = {
            'missing_from_dim_proc': set(),  # Codes not in dim_proc at all
            'no_category': set(),  # Codes in dim_proc but with no category
            'stats': {
                'total_unique_cpts': 0,
                'total_in_dim_proc': 0,
                'total_missing': 0,
                'total_uncategorized': 0
            }
        }
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all unique CPT codes from line_items
            line_items_df = pd.read_sql_query("""
                SELECT DISTINCT CPT 
                FROM line_items 
                WHERE CPT IS NOT NULL
            """, conn)
            
            all_cpt_codes = set(line_items_df['CPT'])
            results['stats']['total_unique_cpts'] = len(all_cpt_codes)
            logger.info(f"Found {len(all_cpt_codes)} unique CPT codes in line_items table")
            
            # Get all codes and their categories from dim_proc
            dim_proc_df = pd.read_sql_query("""
                SELECT proc_cd, proc_category 
                FROM dim_proc 
                WHERE proc_cd IS NOT NULL
            """, conn)
            
            dim_proc_codes = set(dim_proc_df['proc_cd'])
            results['stats']['total_in_dim_proc'] = len(dim_proc_codes)
            
            # Find codes missing from dim_proc entirely
            missing_codes = all_cpt_codes - dim_proc_codes
            results['missing_from_dim_proc'] = missing_codes
            results['stats']['total_missing'] = len(missing_codes)
            
            if missing_codes:
                logger.info("\nCPT codes missing from dim_proc (line_items):")
                for code in sorted(missing_codes):
                    logger.info(f"  - {code}")
            
            # Find codes with no category
            codes_with_no_category = set(
                dim_proc_df[
                    (dim_proc_df['proc_cd'].isin(all_cpt_codes)) & 
                    ((dim_proc_df['proc_category'].isna()) | (dim_proc_df['proc_category'] == '') | (dim_proc_df['proc_category'] == '0'))
                ]['proc_cd']
            )
            results['no_category'] = codes_with_no_category
            results['stats']['total_uncategorized'] = len(codes_with_no_category)
            
            if codes_with_no_category:
                logger.info("\nCPT codes in dim_proc but with no category (line_items):")
                for code in sorted(codes_with_no_category):
                    logger.info(f"  - {code}")
            
        return results

    def generate_json_report(self, output_path: str = None) -> str:
        """
        Generate a report focused on missing and uncategorized CPT codes.
        
        Args:
            output_path: Optional path to save report
            
        Returns:
            str: Report content
        """
        results = self.analyze_json_codes()
        
        report = []
        report.append("CPT Code Category Analysis")
        report.append("=" * 50)
        report.append(f"Database: {self.db_path}")
        report.append(f"Staging Directory: {self.staging_path}")
        report.append("")
        
        # Add statistics
        report.append("Statistics:")
        report.append("-" * 20)
        report.append(f"Total unique CPT codes found: {results['stats']['total_unique_cpts']}")
        report.append(f"Total codes in dim_proc: {results['stats']['total_in_dim_proc']}")
        report.append(f"Total codes missing from dim_proc: {results['stats']['total_missing']}")
        report.append(f"Total codes without categories: {results['stats']['total_uncategorized']}")
        report.append("")
        
        # Show missing codes
        if results['missing_from_dim_proc']:
            report.append("CPT Codes Missing from dim_proc:")
            report.append("-" * 20)
            for code in sorted(results['missing_from_dim_proc']):
                report.append(f"  - {code}")
            report.append("")
        
        # Show uncategorized codes
        if results['no_category']:
            report.append("CPT Codes Without Categories:")
            report.append("-" * 20)
            for code in sorted(results['no_category']):
                report.append(f"  - {code}")
        
        report_content = "\n".join(report)
        
        # Save to file if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_content)
        
        return report_content

    def get_missing_codes(self, source: str = 'all') -> Dict[str, List[str]]:
        """
        Get CPT codes that are used in the system but missing from dim_proc.
        
        Args:
            source: Where to look for codes ('all', 'line_items', 'json')
            
        Returns:
            Dict: Mapping of source to list of missing codes
        """
        missing_codes = defaultdict(list)
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all codes from dim_proc
            dim_proc_codes = set(pd.read_sql_query("SELECT proc_cd FROM dim_proc", conn)['proc_cd'])
            logger.info(f"Found {len(dim_proc_codes)} codes in dim_proc")
            
            # Check line_items table
            if source in ['all', 'line_items']:
                line_codes = set(pd.read_sql_query("SELECT DISTINCT CPT FROM line_items WHERE CPT IS NOT NULL", conn)['CPT'])
                missing = line_codes - dim_proc_codes
                if missing:
                    missing_codes['line_items'] = sorted(list(missing))
                    logger.info(f"Found {len(missing)} missing codes in line_items")
            
            # Check JSON files in staging
            if source in ['all', 'json']:
                json_codes = set()
                json_files = list(Path(self.staging_path).glob('**/*.json'))
                logger.info(f"Found {len(json_files)} JSON files in {self.staging_path}")
                
                for json_file in json_files:
                    file_codes = self._extract_cpt_from_json(str(json_file))
                    if file_codes:
                        logger.info(f"Found {len(file_codes)} CPT codes in {json_file.name}")
                    json_codes.update(file_codes)
                
                missing = json_codes - dim_proc_codes
                if missing:
                    missing_codes['json_files'] = sorted(list(missing))
                    logger.info(f"Found {len(missing)} missing codes in JSON files")
        
        return dict(missing_codes)
    
    def get_category_mismatches(self) -> Dict[str, List[Dict]]:
        """
        Get codes that exist in multiple tables with different categories.
        
        Returns:
            Dict: Mapping of source to list of mismatched codes with their categories
        """
        mismatches = defaultdict(list)
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all codes and categories from dim_proc
            dim_proc_df = pd.read_sql_query("""
                SELECT proc_cd, proc_category 
                FROM dim_proc 
                WHERE proc_cd IS NOT NULL AND proc_category IS NOT NULL
            """, conn)
            
            # Check ppo table for mismatches
            ppo_df = pd.read_sql_query("""
                SELECT proc_cd, proc_category 
                FROM ppo 
                WHERE proc_cd IS NOT NULL AND proc_category IS NOT NULL
            """, conn)
            
            # Find mismatches between dim_proc and ppo
            for _, row in ppo_df.iterrows():
                dim_match = dim_proc_df[dim_proc_df['proc_cd'] == row['proc_cd']]
                if not dim_match.empty:
                    dim_category = dim_match['proc_category'].iloc[0]
                    if dim_category != row['proc_category']:
                        mismatches['ppo'].append({
                            'code': row['proc_cd'],
                            'dim_proc_category': dim_category,
                            'other_category': row['proc_category']
                        })
        
        return dict(mismatches)
    
    def generate_report(self, output_path: str = None) -> str:
        """
        Generate a comprehensive report of missing and uncategorized CPT codes
        from both JSON files and line_items table.
        
        Args:
            output_path: Optional path to save report
            
        Returns:
            str: Report content
        """
        json_results = self.analyze_json_codes()
        line_items_results = self.analyze_line_items_codes()
        
        report = []
        report.append("CPT Code Category Analysis")
        report.append("=" * 50)
        report.append(f"Database: {self.db_path}")
        report.append(f"Staging Directory: {self.staging_path}")
        report.append("")
        
        # Add statistics
        report.append("Statistics:")
        report.append("-" * 20)
        report.append("JSON Files:")
        report.append(f"  Total unique CPT codes found: {json_results['stats']['total_unique_cpts']}")
        report.append(f"  Total codes in dim_proc: {json_results['stats']['total_in_dim_proc']}")
        report.append(f"  Total codes missing from dim_proc: {json_results['stats']['total_missing']}")
        report.append(f"  Total codes without categories: {json_results['stats']['total_uncategorized']}")
        report.append("")
        report.append("Line Items Table:")
        report.append(f"  Total unique CPT codes found: {line_items_results['stats']['total_unique_cpts']}")
        report.append(f"  Total codes in dim_proc: {line_items_results['stats']['total_in_dim_proc']}")
        report.append(f"  Total codes missing from dim_proc: {line_items_results['stats']['total_missing']}")
        report.append(f"  Total codes without categories: {line_items_results['stats']['total_uncategorized']}")
        report.append("")
        
        # Show missing codes from JSON
        if json_results['missing_from_dim_proc']:
            report.append("CPT Codes Missing from dim_proc (JSON Files):")
            report.append("-" * 20)
            for code in sorted(json_results['missing_from_dim_proc']):
                report.append(f"  - {code}")
            report.append("")
        
        # Show missing codes from line_items
        if line_items_results['missing_from_dim_proc']:
            report.append("CPT Codes Missing from dim_proc (Line Items):")
            report.append("-" * 20)
            for code in sorted(line_items_results['missing_from_dim_proc']):
                report.append(f"  - {code}")
            report.append("")
        
        # Show uncategorized codes from JSON
        if json_results['no_category']:
            report.append("CPT Codes Without Categories (JSON Files):")
            report.append("-" * 20)
            for code in sorted(json_results['no_category']):
                report.append(f"  - {code}")
            report.append("")
        
        # Show uncategorized codes from line_items
        if line_items_results['no_category']:
            report.append("CPT Codes Without Categories (Line Items):")
            report.append("-" * 20)
            for code in sorted(line_items_results['no_category']):
                report.append(f"  - {code}")
        
        report_content = "\n".join(report)
        
        # Save to file if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_content)
        
        return report_content

def main():
    """Command line interface for the scanner."""
    import argparse
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    parser = argparse.ArgumentParser(description="Scan for CPT codes missing from dim_proc")
    parser.add_argument("--db", help="Path to SQLite database (default: brsystem.db in current directory)")
    parser.add_argument("--staging", help="Path to staging directory (default: staging/ in current directory)")
    parser.add_argument("--output", help="Path to save report (default: print to console)")
    parser.add_argument("--source", choices=['all', 'line_items', 'json'], 
                       default='all', help="Which sources to scan (default: all)")
    parser.add_argument("--json-only", action="store_true", help="Only analyze JSON files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed processing information")
    
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if not args.verbose:
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        scanner = DimProcScanner(args.db, args.staging)
        
        if args.json_only:
            if args.output:
                scanner.generate_json_report(args.output)
                print(f"Report saved to {args.output}")
            else:
                print(scanner.generate_json_report())
        else:
            if args.output:
                scanner.generate_report(args.output)
                print(f"Report saved to {args.output}")
            else:
                print(scanner.generate_report())
            
    except Exception as e:
        logger.error(f"Error running scanner: {e}")
        raise

if __name__ == "__main__":
    main() 
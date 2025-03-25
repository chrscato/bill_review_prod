# main_v2.py - Healthcare Bill Review System 2.0
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

# Config
from config.settings import settings

# Services
from core.services.database import DatabaseService
from core.services.normalizer import normalize_hcfa_format
from core.services.reporter import ValidationReporter

# Validators
from core.validators.bundle_validator import BundleValidator
from core.validators.intent_validator import ClinicalIntentValidator
from core.validators.line_items import LineItemValidator
from core.validators.rate_validator import RateValidator
from core.validators.modifier_validator import ModifierValidator
from core.validators.units_validator import UnitsValidator

# Models
from core.models.validation import ValidationResult, ValidationSession
from utils.code_mapper import CodeMapper
from utils.helpers import format_timestamp

class BillReviewApplication:
    """
    Main application class for the Healthcare Bill Review System 2.0.
    Coordinates validation flow and reporting.
    """
    
    def __init__(self):
        """Initialize the Bill Review Application with required services."""
        self.db_service = DatabaseService()
        self.reporter = ValidationReporter(Path(settings.LOG_PATH))
        self.session_id = str(uuid.uuid4())
        self.session_start_time = datetime.now()
        
        # Initialize validation results storage
        self.validation_results = []
    
    def process_file(self, file_path: Path, validators: Dict) -> None:
        """
        Process a single JSON file through all validators with enhanced bundle and intent recognition.
        
        Args:
            file_path: Path to the JSON file to process
            validators: Dictionary of validator instances
        """
        base_result = {
            "file_name": str(file_path),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "patient_name": None,
            "date_of_service": None,
            "order_id": None,
            "source_data": {}
        }

        try:
            # Load and normalize HCFA data
            with open(file_path, 'r') as f:
                raw_hcfa_data = json.load(f)
            
            hcfa_data = normalize_hcfa_format(raw_hcfa_data)
            order_id = hcfa_data.get('Order_ID')

            # Load provider & patient details
            provider_info = self.db_service.get_provider_details(order_id, validators['conn'])
            order_info = self.db_service.get_full_details(order_id, validators['conn'])
            patient_info = order_info.get('order_details', {})
            
            # Get order line items for bundle and intent comparison
            order_lines = self.db_service.get_line_items(order_id, validators['conn'])
            
            # Convert order line items to dict format for validators
            order_data = {
                "line_items": []
            }
            
            for _, row in order_lines.iterrows():
                order_data["line_items"].append({
                    "CPT": row["CPT"],
                    "Modifier": row["Modifier"],
                    "Units": row["Units"],
                    "Description": row["Description"]
                })

            # Update base result with all available data
            base_result.update({
                "patient_name": hcfa_data.get('patient_name'),
                "date_of_service": hcfa_data.get('date_of_service'),
                "order_id": order_id,
                "source_data": {
                    "hcfa": hcfa_data, 
                    "db_provider_info": provider_info, 
                    "db_patient_info": patient_info,
                    "db_line_items": order_lines.to_dict('records') if not order_lines.empty else []
                }
            })

            # ================================================================
            # ENHANCED VALIDATION FLOW - Run all validators and collect results
            # ================================================================
            validation_results = {}
            critical_failures = []
            non_critical_failures = []
            
            # 1. First check bundle matching
            print(f"Running bundle validation for {file_path.name}")
            bundle_result = validators['bundle'].validate(order_data, hcfa_data)
            validation_results['bundle'] = bundle_result
            
            # If a bundle is detected, attach this information for other validators to use
            if bundle_result['status'] == 'PASS' and bundle_result['bundle_comparison']['status'] != 'NO_BUNDLE':
                # Store bundle information in the HCFA data
                bundle_info = bundle_result['bundle_comparison']['hcfa_bundle']
                if bundle_info:
                    # Attach bundle info to HCFA data
                    hcfa_data['bundle_type'] = bundle_info.get('bundle_type')
                    hcfa_data['bundle_name'] = bundle_info.get('bundle_name')
                    
                    # Attach bundle info to each line item for rate validation
                    for line in hcfa_data['line_items']:
                        if str(line.get('cpt', '')) in bundle_info.get('all_bundle_codes', []):
                            line['bundle_type'] = bundle_info.get('bundle_type')
                            line['bundle_name'] = bundle_info.get('bundle_name')
                            
                            # Mark first line as primary component for rate validation
                            line['primary_component'] = not any(
                                l.get('primary_component', False) for l in hcfa_data['line_items']
                            )
            
            # 2. Check clinical intent - understanding the purpose of the procedure
            print(f"Running clinical intent validation for {file_path.name}")
            intent_result = validators['intent'].validate(order_data, hcfa_data)
            validation_results['intent'] = intent_result
            
            # 3. Check modifiers - not critical for bundles
            print(f"Running modifier validation for {file_path.name}")
            modifier_result = validators['modifier'].validate(hcfa_data)
            validation_results['modifier'] = modifier_result
            
            # 4. Check units - respecting bundle-specific rules
            print(f"Running units validation for {file_path.name}")
            units_result = validators['units'].validate(hcfa_data)
            validation_results['units'] = units_result
            
            # 5. Check line items matching
            print(f"Running line items validation for {file_path.name}")
            line_items_result = validators['line_items'].validate(hcfa_data['line_items'], order_lines)
            validation_results['line_items'] = line_items_result
            
            # 6. Check rates - providing bundle rates if applicable
            print(f"Running rate validation for {file_path.name}")
            rate_result = validators['rate'].validate(hcfa_data['line_items'], order_id)
            validation_results['rate'] = rate_result
            
            # ================================================================
            # DETERMINE OVERALL VALIDATION STATUS
            # ================================================================
            
            # Check if any validator failed
            has_bundle_pass = (
                bundle_result['status'] == 'PASS' and 
                bundle_result['bundle_comparison']['status'] != 'NO_BUNDLE'
            )
            
            # For each validation, determine if it's a critical failure
            # Bundle failure is always critical
            if bundle_result['status'] == 'FAIL':
                critical_failures.append(("bundle", bundle_result['message']))
            
            # Intent failure is critical if not a bundle
            if intent_result['status'] == 'FAIL' and not has_bundle_pass:
                critical_failures.append(("intent", intent_result['message']))
            elif intent_result['status'] == 'FAIL' and has_bundle_pass:
                non_critical_failures.append(("intent", intent_result['message']))
            
            # Modifiers are non-critical
            if modifier_result['status'] == 'FAIL':
                non_critical_failures.append(("modifier", modifier_result['message']))
            
            # Units are critical unless it's a bundle
            if units_result['status'] == 'FAIL' and not has_bundle_pass:
                critical_failures.append(("units", units_result['message']))
            elif units_result['status'] == 'FAIL' and has_bundle_pass:
                non_critical_failures.append(("units", units_result['message']))
            
            # Line items are always critical
            if line_items_result['status'] == 'FAIL':
                critical_failures.append(("line_items", line_items_result['message']))
            
            # Rate validation is critical
            if rate_result['status'] == 'FAIL':
                critical_failures.append(("rate", rate_result['message']))
            
            # Create overall validation result
            overall_status = "FAIL" if critical_failures else "PASS"
            
            # Generate overall messages
            overall_messages = []
            
            if critical_failures:
                overall_messages.append(f"Validation failed with {len(critical_failures)} critical issues:")
                for failure_type, message in critical_failures[:3]:
                    overall_messages.append(f"- {failure_type}: {message}")
                
                if len(critical_failures) > 3:
                    overall_messages.append(f"- ... and {len(critical_failures) - 3} more critical issues")
            
            elif non_critical_failures:
                overall_messages.append(f"Validation passed with {len(non_critical_failures)} non-critical issues:")
                for failure_type, message in non_critical_failures[:3]:
                    overall_messages.append(f"- {failure_type}: {message}")
                
                if len(non_critical_failures) > 3:
                    overall_messages.append(f"- ... and {len(non_critical_failures) - 3} more non-critical issues")
            
            else:
                overall_messages.append("Validation passed successfully with no issues")
            
            # Log the combined validation result
            validation_result = ValidationResult(
                **base_result,
                status=overall_status,
                validation_type="complete",
                details=validation_results,
                messages=overall_messages
            )
            
            # Add to results list
            self.validation_results.append(validation_result)
            
            # Add to reporter for generating reports
            self.reporter.add_result(validation_result.to_dict())
            
            print(f"Validation complete for {file_path.name}: {overall_status}")

        except Exception as e:
            # Log any processing errors
            error_result = ValidationResult(
                **base_result,
                status="FAIL",
                validation_type="process_error",
                details={"error": str(e)},
                messages=[f"Error processing file: {str(e)}"]
            )
            
            # Add to results list
            self.validation_results.append(error_result)
            
            # Add to reporter for generating reports
            self.reporter.add_result(error_result.to_dict())
            
            print(f"Error processing file {file_path.name}: {str(e)}")

    def run(self):
        """
        Main execution method to process all JSON files.
        """
        with self.db_service.connect_db() as conn:
            # Load reference data
            dim_proc_df = pd.read_sql_query("SELECT * FROM dim_proc", conn)
            
            # Initialize code mapper
            code_mapper = CodeMapper(settings.CLINICAL_EQUIV_CONFIG)
            
            # Initialize all validators
            validators = {
                'conn': conn,
                'bundle': BundleValidator(settings.BUNDLE_CONFIG),
                'intent': ClinicalIntentValidator(
                    settings.CLINICAL_EQUIV_CONFIG, 
                    dim_proc_df
                ),
                'line_items': LineItemValidator(dim_proc_df),
                'rate': RateValidator(conn),
                'modifier': ModifierValidator(),
                'units': UnitsValidator(dim_proc_df)
            }

            # Find and process all JSON files
            json_files = list(Path(settings.JSON_PATH).glob('*.json'))
            total_files = len(json_files)
            print(f"Found {total_files} files to process")

            # Process each file
            for index, json_file in enumerate(json_files, 1):
                print(f"Processing file {index}/{total_files}: {json_file.name}")
                self.process_file(json_file, validators)

        # Generate validation reports
        self.generate_reports()

    def generate_reports(self):
        """
        Generate validation reports.
        """
        # Generate and save reports
        timestamp = format_timestamp()
        
        # Generate summary
        summary = self.reporter.generate_summary()
        
        # Save reports
        report_paths = self.reporter.save_report(include_html=settings.GENERATE_HTML_REPORT)
        
        # Generate Excel report if enabled
        if settings.GENERATE_EXCEL_REPORT:
            excel_path = self.reporter.export_to_excel()
            report_paths["excel"] = excel_path
        
        print("\nValidation complete!")
        print(f"Processed {len(self.validation_results)} files")
        print(f"Pass: {sum(1 for r in self.validation_results if r.status == 'PASS')}")
        print(f"Fail: {sum(1 for r in self.validation_results if r.status == 'FAIL')}")
        print(f"\nReport files:")
        for report_type, path in report_paths.items():
            print(f"- {report_type}: {path}")

if __name__ == "__main__":
    print("Healthcare Bill Review System 2.0")
    print("=================================")
    
    app = BillReviewApplication()
    app.run()
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

            if not order_id:
                raise ValueError("No Order_ID found in HCFA data")

            # Load provider & patient details
            provider_info = self.db_service.get_provider_details(order_id, validators['conn'])
            if not provider_info:
                raise ValueError(f"No provider details found for Order_ID: {order_id}")

            order_info = self.db_service.get_full_details(order_id, validators['conn'])
            patient_info = order_info.get('order_details', {})
            
            # Get order line items for bundle and intent comparison
            order_lines = self.db_service.get_line_items(order_id, validators['conn'])
            if order_lines.empty:
                raise ValueError(f"No line items found for Order_ID: {order_id}")
            
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
            intent_result = validators['intent'].validate(order_data, hcfa_data)
            validation_results['intent'] = intent_result
            
            # 3. Check modifiers - not critical for bundles
            modifier_result = validators['modifier'].validate(hcfa_data)
            validation_results['modifier'] = modifier_result
            
            # 4. Check units - respecting bundle-specific rules
            units_result = validators['units'].validate(hcfa_data)
            validation_results['units'] = units_result
            
            # 5. Check line items matching
            line_items_result = validators['line_items'].validate(hcfa_data['line_items'], order_lines)
            validation_results['line_items'] = line_items_result
            
            # 6. Check rates - providing bundle rates if applicable
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
            
            # Generate overall messages with detailed failure information
            overall_messages = []
            
            if critical_failures:
                overall_messages.append(f"Validation failed with {len(critical_failures)} critical issues:")
                for failure_type, message in critical_failures:
                    # Get detailed validation result for this type
                    validator_result = validation_results.get(failure_type, {})
                    details = validator_result.get('details', {})
                    
                    # Add detailed failure information
                    overall_messages.append(f"\n{failure_type.upper()} Validation Failed:")
                    overall_messages.append(f"- Message: {message}")
                    
                    # Add specific failure details if available
                    if details:
                        if 'missing_codes' in details:
                            overall_messages.append(f"- Missing CPT codes: {', '.join(details['missing_codes'])}")
                        if 'mismatched_codes' in details:
                            overall_messages.append(f"- Mismatched CPT codes: {', '.join(details['mismatched_codes'])}")
                        if 'invalid_modifiers' in details:
                            overall_messages.append(f"- Invalid modifiers: {', '.join(details['invalid_modifiers'])}")
                        if 'rate_issues' in details:
                            overall_messages.append(f"- Rate issues: {details['rate_issues']}")
                        if 'bundle_issues' in details:
                            overall_messages.append(f"- Bundle issues: {details['bundle_issues']}")
                        if 'intent_mismatch' in details:
                            overall_messages.append(f"- Intent mismatch: {details['intent_mismatch']}")
            
            elif non_critical_failures:
                overall_messages.append(f"Validation passed with {len(non_critical_failures)} non-critical issues:")
                for failure_type, message in non_critical_failures:
                    # Get detailed validation result for this type
                    validator_result = validation_results.get(failure_type, {})
                    details = validator_result.get('details', {})
                    
                    # Add detailed non-critical issue information
                    overall_messages.append(f"\n{failure_type.upper()} Non-Critical Issue:")
                    overall_messages.append(f"- Message: {message}")
                    
                    # Add specific issue details if available
                    if details:
                        if 'missing_codes' in details:
                            overall_messages.append(f"- Missing CPT codes: {', '.join(details['missing_codes'])}")
                        if 'mismatched_codes' in details:
                            overall_messages.append(f"- Mismatched CPT codes: {', '.join(details['mismatched_codes'])}")
                        if 'invalid_modifiers' in details:
                            overall_messages.append(f"- Invalid modifiers: {', '.join(details['invalid_modifiers'])}")
                        if 'rate_issues' in details:
                            overall_messages.append(f"- Rate issues: {details['rate_issues']}")
                        if 'bundle_issues' in details:
                            overall_messages.append(f"- Bundle issues: {details['bundle_issues']}")
                        if 'intent_mismatch' in details:
                            overall_messages.append(f"- Intent mismatch: {details['intent_mismatch']}")
            
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
            
            # Log validation result with status
            print(f"Validation complete for {file_path.name}: {overall_status}")

        except Exception as e:
            # Log any processing errors with detailed information
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "file_path": str(file_path),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": order_id if 'order_id' in locals() else None,
                "provider_info": provider_info if 'provider_info' in locals() else None,
                "has_line_items": not order_lines.empty if 'order_lines' in locals() else False
            }
            
            error_result = ValidationResult(
                **base_result,
                status="FAIL",
                validation_type="process_error",
                details=error_details,
                messages=[f"Error processing file: {str(e)}"]
            )
            
            # Add to results list
            self.validation_results.append(error_result)
            
            # Add to reporter for generating reports
            self.reporter.add_result(error_result.to_dict())
            
            # Print detailed error information
            print(f"\nError processing file {file_path.name}:")
            print(f"Error Type: {type(e).__name__}")
            print(f"Message: {str(e)}")
            if 'order_id' in locals() and order_id:
                print(f"Order ID: {order_id}")
            print("----------------------------------------")

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
            print(f"Starting validation of {total_files} files...")

            # Process each file
            for index, json_file in enumerate(json_files, 1):
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
        
        # Print final summary
        print("\nValidation Summary:")
        print(f"Total Files: {len(self.validation_results)}")
        print(f"Pass: {sum(1 for r in self.validation_results if r.status == 'PASS')}")
        print(f"Fail: {sum(1 for r in self.validation_results if r.status == 'FAIL')}")
        print(f"\nReports generated:")
        for report_type, path in report_paths.items():
            print(f"- {report_type}: {path}")

if __name__ == "__main__":
    print("Healthcare Bill Review System 2.0")
    print("=================================")
    
    app = BillReviewApplication()
    app.run()
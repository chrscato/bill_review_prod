# main_v2.py - Healthcare Bill Review System 2.0
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import shutil

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
        
        # Create success and fails directories if they don't exist
        settings.SUCCESS_PATH.mkdir(exist_ok=True, parents=True)
        settings.FAILS_PATH.mkdir(exist_ok=True, parents=True)
    
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
            # Load and parse JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_hcfa_data = json.load(f)
            
            # Normalize HCFA data structure
            hcfa_data = normalize_hcfa_format(raw_hcfa_data)
            
            # Extract order ID from the JSON data
            order_id = raw_hcfa_data.get('Order_ID')
            if not order_id:
                raise ValueError(f"No Order_ID found in file: {file_path.name}")
            
            # Create database connection
            conn = self.db_service.connect_db()
            
            try:
                # Get provider info and full order details from database
                provider_info = self.db_service.get_provider_details(order_id, conn)
                order_details = self.db_service.get_full_details(order_id, conn)
                order_lines = self.db_service.get_line_items(order_id, conn)
                
                # Extract patient info from order details
                patient_info = order_details.get('order_details', {}) if order_details else {}
                
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
                if bundle_result.get('status') == 'PASS' and bundle_result.get('bundle_comparison', {}).get('status') != 'NO_BUNDLE':
                    # Store bundle information in the HCFA data
                    bundle_info = bundle_result.get('bundle_comparison', {}).get('hcfa_bundle')
                    if bundle_info:
                        # Attach bundle info to HCFA data
                        hcfa_data['bundle_type'] = bundle_info.get('bundle_type')
                        hcfa_data['bundle_name'] = bundle_info.get('bundle_name')
                        
                        # Attach bundle info to each line item for rate validation
                        for line in hcfa_data.get('line_items', []):
                            if str(line.get('cpt', '')) in bundle_info.get('all_bundle_codes', []):
                                line['bundle_type'] = bundle_info.get('bundle_type')
                                line['bundle_name'] = bundle_info.get('bundle_name')
                                
                                # Mark first line as primary component for rate validation
                                line['primary_component'] = not any(
                                    l.get('primary_component', False) for l in hcfa_data.get('line_items', [])
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
                line_items_result = validators['line_items'].validate(hcfa_data.get('line_items', []), order_lines)
                validation_results['line_items'] = line_items_result
                
                # 6. Check rates - providing bundle rates if applicable
                rate_result = validators['rate'].validate(hcfa_data.get('line_items', []), order_id)
                validation_results['rate'] = rate_result
                
                # ================================================================
                # DETERMINE OVERALL VALIDATION STATUS
                # ================================================================
                
                # Check if any validator failed
                has_bundle_pass = (
                    bundle_result.get('status') == 'PASS' and 
                    bundle_result.get('bundle_comparison', {}).get('status') != 'NO_BUNDLE'
                )
                
                # For each validation, determine if it's a critical failure
                # Bundle failure is always critical
                if bundle_result.get('status') == 'FAIL':
                    critical_failures.append(("bundle", bundle_result.get('message', 'Bundle validation failed')))
                
                # Intent failure is critical if not a bundle
                if intent_result.get('status') == 'FAIL' and not has_bundle_pass:
                    critical_failures.append(("intent", intent_result.get('message', 'Clinical intent validation failed')))
                elif intent_result.get('status') == 'FAIL' and has_bundle_pass:
                    non_critical_failures.append(("intent", intent_result.get('message', 'Clinical intent validation failed')))
                
                # Modifiers are non-critical
                if modifier_result.get('status') == 'FAIL':
                    non_critical_failures.append(("modifier", modifier_result.get('message', 'Modifier validation failed')))
                
                # Units are critical unless it's a bundle
                if units_result.get('status') == 'FAIL' and not has_bundle_pass:
                    critical_failures.append(("units", units_result.get('message', 'Units validation failed')))
                elif units_result.get('status') == 'FAIL' and has_bundle_pass:
                    non_critical_failures.append(("units", units_result.get('message', 'Units validation failed')))
                
                # Line items are always critical
                if line_items_result.get('status') == 'FAIL':
                    critical_failures.append(("line_items", line_items_result.get('message', 'Line items validation failed')))
                
                # Rate validation is critical
                if rate_result.get('status') == 'FAIL':
                    critical_failures.append(("rate", rate_result.get('message', 'Rate validation failed')))
                
                # Create overall validation result
                overall_status = "FAIL" if critical_failures else "PASS"
                
                # Generate overall messages with detailed failure information
                overall_messages = []
                
                # Check for component billing across validators
                has_component_billing = False
                component_type = None
                component_message = None
                
                # Look for component billing in modifier validator
                if validation_results.get('modifier', {}).get('component_billing', {}).get('is_component_billing'):
                    has_component_billing = True
                    component_info = validation_results['modifier']['component_billing']
                    component_type = component_info['component_type']
                    component_message = component_info['message']
                
                # Also check line items validator
                elif validation_results.get('line_items', {}).get('component_billing', {}).get('is_component_billing'):
                    has_component_billing = True
                    component_info = validation_results['line_items']['component_billing']
                    component_type = component_info['component_type']
                    component_message = component_info['message']
                
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
                
                # Add component billing information if present
                if has_component_billing:
                    # Add to validation messages
                    overall_messages.append(f"\nNon-Global Bill: {component_message}")
                    
                    # Add structured data
                    validation_result = ValidationResult(
                        **base_result,
                        status=overall_status,
                        validation_type="complete",
                        details={
                            **validation_results,
                            "component_billing": {
                                "is_component_billing": True,
                                "component_type": component_type,
                                "message": component_message
                            }
                        },
                        messages=overall_messages
                    )
                else:
                    validation_result = ValidationResult(
                        **base_result,
                        status=overall_status,
                        validation_type="complete",
                        details=validation_results,
                        messages=overall_messages
                    )
                
                # Move file to appropriate directory based on validation status
                target_dir = settings.SUCCESS_PATH if overall_status == "PASS" else settings.FAILS_PATH
                target_path = target_dir / file_path.name
                
                # If the file is a failure, add the failure messages to the file
                if overall_status == "FAIL":
                    # Read the original file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                    
                    # Add validation messages to the file
                    file_data['validation_messages'] = overall_messages
                    
                    # Write the modified file to the fails directory
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(file_data, f, indent=2)
                else:
                    # For successful validations, enhance the JSON with additional details
                    # Read the original file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                    
                    # Add validation status and messages
                    file_data['validation_status'] = "PASS"
                    file_data['validation_messages'] = overall_messages
                    
                    # Add rate information if available
                    rate_validation = validation_results.get('rate', {})
                    if rate_validation and 'results' in rate_validation:
                        # Extract rate details
                        rate_details = []
                        for line in rate_validation['results']:
                            if line.get('status') == 'PASS':
                                rate_details.append({
                                    'cpt': line.get('cpt'),
                                    'assigned_rate': line.get('validated_rate'),
                                    'rate_source': line.get('rate_source'),
                                    'is_bundled': line.get('is_bundled', False),
                                    'bundle_name': line.get('bundle_name', None)
                                })
                        file_data['assigned_rates'] = rate_details
                        file_data['total_assigned_rate'] = rate_validation.get('total_rate', 0)
                    
                    # Add order details from database
                    if order_details:
                        order_info = order_details.get('order_details', {})
                        clean_order_details = {
                            'FileMaker_Record_Number': order_info.get('FileMaker_Record_Number'),
                            'PatientName': order_info.get('PatientName'),
                            'Patient_DOB': order_info.get('Patient_DOB'),
                            'Patient_Injury_Date': order_info.get('Patient_Injury_Date'),
                            'Jurisdiction_State': order_info.get('Jurisdiction_State')
                        }
                        file_data['order_details'] = clean_order_details
                    
                    # Add provider details from database
                    if provider_info:
                        clean_provider_info = {
                            'Billing_Name': provider_info.get('Billing Name'),
                            'Billing_Address': {
                                'Address': provider_info.get('Billing Address 1'),
                                'City': provider_info.get('Billing Address City'),
                                'State': provider_info.get('Billing Address State'),
                                'Postal_Code': provider_info.get('Billing Address Postal Code')
                            }
                        }
                        file_data['provider_details'] = clean_provider_info
                    
                    # Add validation timestamp
                    file_data['validation_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Write the enhanced file to the success directory
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(file_data, f, indent=2)
                
                # Add to results list
                self.validation_results.append(validation_result)
                
                # Add to reporter for generating reports
                self.reporter.add_result(validation_result.to_dict())

            finally:
                # Always close the database connection
                conn.close()

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
            
            # Move failed file to fails directory with error message
            target_path = settings.FAILS_PATH / file_path.name
            
            # Read the original file
            with open(file_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            # Add error message to the file
            file_data['validation_messages'] = [f"Error processing file: {str(e)}"]
            
            # Write the modified file to the fails directory
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2)

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
        
        # Print only the validation summary
        print("\nValidation Summary:")
        print(f"Total Files: {len(self.validation_results)}")
        print(f"Pass: {sum(1 for r in self.validation_results if r.status == 'PASS')}")
        print(f"Fail: {sum(1 for r in self.validation_results if r.status == 'FAIL')}")

if __name__ == "__main__":
    print("Healthcare Bill Review System 2.0")
    print("=================================")
    
    app = BillReviewApplication()
    app.run()
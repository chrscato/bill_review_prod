# main_v2.py - Healthcare Bill Review System 2.0
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import shutil
import traceback
import argparse
import random

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
from core.validators.cpt_validator import CPTValidator

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
        self.db_service.clear_cache()  # Clear the cache to ensure the latest data is used
        self.reporter = ValidationReporter(Path(settings.LOG_PATH))
        self.session_id = str(uuid.uuid4())
        self.session_start_time = datetime.now()
        self.quiet = False
        
        # Initialize validation results storage
        self.validation_results = []
        
        # Create success, fails, and arthrogram directories if they don't exist
        settings.SUCCESS_PATH.mkdir(exist_ok=True, parents=True)
        settings.FAILS_PATH.mkdir(exist_ok=True, parents=True)
        settings.ARTHROGRAM_PATH = settings.JSON_PATH / "arthrogram"
        settings.ARTHROGRAM_PATH.mkdir(exist_ok=True, parents=True)
    
    def _get_escalation_files(self) -> set:
        """
        Get a set of filenames that are in the escalation folder.
        Creates the folder if it doesn't exist.
        
        Returns:
            set: Set of filenames in the escalation folder
        """
        # Use the correct escalation folder path
        escalation_path = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\escalations")
        escalation_files = set()
        
        try:
            # Create escalation folder if it doesn't exist
            escalation_path.mkdir(parents=True, exist_ok=True)
            
            # Get list of filenames in the escalations folder
            escalation_files = {f.name for f in escalation_path.glob('*.json')}
            if escalation_files and hasattr(self, 'quiet') and not self.quiet:
                print(f"Found {len(escalation_files)} files in the escalations folder.")
        except Exception as e:
            if hasattr(self, 'quiet') and not self.quiet:
                print(f"Warning: Error accessing escalation folder: {str(e)}")
            # Continue with empty set of escalation files
        
        return escalation_files
    
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
            order_id = raw_hcfa_data.get('Order_ID') or raw_hcfa_data.get('order_id')
            if not order_id:
                raise ValueError(f"No Order_ID found in file: {file_path.name}")
            
            # Create database connection
            conn = self.db_service.connect_db()
            
            try:
                # Get provider info and full order details from database
                provider_info = self.db_service.get_provider_details(order_id, conn)
                order_details = self.db_service.get_full_details(order_id, conn)
                
                # Check if this is an ARTHROGRAM bundle
                if order_details and order_details.get('order_details', {}).get('bundle_type') == 'ARTHROGRAM':
                    # Move file to ARTHROGRAM directory
                    arthrogram_path = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\arthrogram")
                    arthrogram_path.mkdir(exist_ok=True, parents=True)
                    target_path = arthrogram_path / file_path.name
                    shutil.move(str(file_path), str(target_path))
                    if not self.quiet:
                        print(f"Moved ARTHROGRAM file to: {target_path}")
                    return  # Exit processing for ARTHROGRAM files
                
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
                
                # 1. Check CPT codes against dim_proc table
                cpt_result = validators['cpt'].validate(hcfa_data)
                validation_results['cpt'] = cpt_result
                
                # If CPT validation fails, add to critical failures
                if cpt_result.get('status') == 'FAIL':
                    critical_failures.append(("cpt", cpt_result.get('message', 'CPT validation failed')))
                
                # Detect bundle from line items
                bundle_result = validators['bundle'].validate(order_data, hcfa_data)
                validation_results['bundle'] = bundle_result

                # If a bundle is detected, attach its information
                if bundle_result.get('status') == 'PASS':
                    bundle_comparison = bundle_result.get('bundle_comparison', {})
                    hcfa_bundle = bundle_comparison.get('hcfa_bundle', {})
                    
                    if hcfa_bundle and hcfa_bundle.get('bundle_type') and hcfa_bundle.get('bundle_name'):
                        # Attach bundle info to HCFA data if found
                        hcfa_data['bundle_type'] = hcfa_bundle.get('bundle_type')
                        hcfa_data['bundle_name'] = hcfa_bundle.get('bundle_name')
                        
                        # Optionally, attach to line items for further processing
                        for line in hcfa_data.get('line_items', []):
                            if str(line.get('cpt', '')) in hcfa_bundle.get('all_bundle_codes', []):
                                line['bundle_type'] = hcfa_bundle.get('bundle_type')
                                line['bundle_name'] = hcfa_bundle.get('bundle_name')
                
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
                
                # Check for component billing in modifier validator
                if validation_results.get('modifier', {}).get('component_billing', {}).get('is_component_billing'):
                    has_component_billing = True
                    component_info = validation_results['modifier']['component_billing']
                    component_type = component_info['component_type']
                    component_message = component_info['message']
                    # Add to critical failures
                    critical_failures.append(("component_billing", f"Non-global bill detected: {component_message}"))
                
                # Also check line items validator for component billing
                elif validation_results.get('line_items', {}).get('details', {}).get('component_billing', {}).get('is_component_billing'):
                    has_component_billing = True
                    component_info = validation_results['line_items']['details']['component_billing']
                    component_type = component_info['component_type']
                    component_message = component_info['message']
                    # Add to critical failures
                    critical_failures.append(("component_billing", f"Non-global bill detected: {component_message}"))
                
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
                    
                    # Check if this was a component billing failure
                    if has_component_billing:
                        file_data['component_billing'] = {
                            'is_component_billing': True,
                            'component_type': component_type,
                            'failure_reason': True  # Explicitly mark as a failure reason
                        }
                    
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
                    
                    # Add total rate at the top level
                    rate_validation = validation_results.get('rate', {})
                    if rate_validation:
                        file_data['total_assigned_rate'] = rate_validation.get('total_rate', 0)
                    
                    # Match service lines with database line items and add payment_id and rate info
                    if 'service_lines' in file_data and isinstance(file_data['service_lines'], list):
                        try:
                            # Create a mapping of CPT codes to rate results
                            rate_map = {}
                            if rate_validation and 'results' in rate_validation:
                                for rate_result in rate_validation['results']:
                                    if rate_result.get('status') == 'PASS':
                                        cpt = rate_result.get('cpt')
                                        if cpt:
                                            # Simple mapping by CPT code is sufficient for rates
                                            if cpt not in rate_map:
                                                rate_map[cpt] = rate_result

                            # Prepare database line items for matching
                            # Convert DataFrame to a list of dictionaries for easier manipulation
                            db_line_items = []
                            for _, row in order_lines.iterrows():
                                cpt = str(row.get('CPT', ''))
                                if cpt:
                                    db_line_items.append({
                                        'id': row.get('id'),
                                        'order_id': row.get('Order_ID'),
                                        'cpt': cpt,
                                        'modifier': row.get('Modifier', ''),
                                        'units': row.get('Units', 1),
                                        'matched': False  # Flag to track if this item has been matched
                                    })

                            # Track HCFA service lines that have been matched
                            for service_line in file_data['service_lines']:
                                cpt = service_line.get('cpt_code')
                                if not cpt:
                                    continue
                                    
                                # Get rate info for this CPT code
                                rate_info = rate_map.get(cpt)
                                
                                # Add rate info directly to the service line if available
                                if rate_info:
                                    service_line['assigned_rate'] = rate_info.get('validated_rate')
                                    service_line['rate_source'] = rate_info.get('rate_source')
                                    service_line['is_bundled'] = rate_info.get('is_bundled', False)
                                    
                                    if rate_info.get('bundle_name'):
                                        service_line['bundle_name'] = rate_info.get('bundle_name')
                                
                                # Find a matching database line item
                                match_found = False
                                
                                # First, look for an exact match by CPT code that hasn't been matched yet
                                for db_item in db_line_items:
                                    if db_item['cpt'] == cpt and not db_item['matched']:
                                        # We found a match - add payment_id and mark as matched
                                        service_line['payment_id'] = {
                                            'line_item_id': db_item['id'],
                                            'order_id': db_item['order_id']
                                        }
                                        db_item['matched'] = True
                                        match_found = True
                                        break
                                
                                # If no match found, this is either an ancillary code or all matching
                                # database line items have already been assigned
                                if not match_found:
                                    # No payment_id is added in this case
                                    pass

                        except Exception as e:
                            # Log the error but continue processing
                            logger.error(f"Error matching service lines to line items: {str(e)}")
                            file_data['validation_messages'].append(f"Warning: Error matching service lines to database IDs: {str(e)}")
                    
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
                            },
                            'TIN': provider_info.get('TIN'),
                            'NPI': provider_info.get('NPI')
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
                "has_line_items": not order_lines.empty if 'order_lines' in locals() else False,
                "traceback": traceback.format_exc(),
                "data_context": {
                    "order_data": order_data if 'order_data' in locals() else None,
                    "hcfa_data": hcfa_data if 'hcfa_data' in locals() else None,
                    "order_cpt_codes": list(order_cpt_codes) if 'order_cpt_codes' in locals() else None,
                    "hcfa_cpt_codes": list(hcfa_cpt_codes) if 'hcfa_cpt_codes' in locals() else None,
                    "bundle_config": self.bundle_config if hasattr(self, 'bundle_config') else None
                }
            }
            
            # Create detailed error message
            error_message = [
                f"Error processing file: {str(e)}",
                f"Error type: {type(e).__name__}",
                f"File: {file_path.name}",
                f"Order ID: {order_id if 'order_id' in locals() else 'Not found'}",
                "\nData Context:",
                f"Order CPT codes: {list(order_cpt_codes) if 'order_cpt_codes' in locals() else 'Not found'}",
                f"HCFA CPT codes: {list(hcfa_cpt_codes) if 'hcfa_cpt_codes' in locals() else 'Not found'}",
                "\nTraceback:",
                traceback.format_exc()
            ]
            
            error_result = ValidationResult(
                **base_result,
                status="FAIL",
                validation_type="process_error",
                details=error_details,
                messages=error_message
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
            
            # Add detailed error messages to the file
            file_data['validation_messages'] = error_message
            
            # Write the modified file to the fails directory
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2)

    def debug_process_file(self, file_path: Path, validators: Dict) -> Dict:
        """
        Process a file with enhanced error logging and return diagnostic information.
        
        Args:
            file_path: Path to the file to process
            validators: Dictionary of validators to use
            
        Returns:
            Dict: Debug information about the processing
        """
        debug_info = {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "processing_steps": [],
            "success": False,
            "error_type": None,
            "error_message": None,
            "error_details": None,
            "data_sample": None,
            "validation_results": {}
        }
        
        try:
            # Step 1: Read and parse JSON
            debug_info["processing_steps"].append("Reading JSON file")
            with open(file_path, 'r') as f:
                raw_data = json.load(f)
                debug_info["data_sample"] = {
                    "line_items_count": len(raw_data.get("line_items", [])),
                    "service_lines_count": len(raw_data.get("service_lines", [])),
                    "has_bundle_info": bool(raw_data.get("bundle_type")),
                    "has_order_id": bool(raw_data.get("Order_ID") or raw_data.get("order_id") or raw_data.get("filemaker_record_number")),
                    "has_patient_info": bool(raw_data.get("patient_info")),
                    "has_billing_info": bool(raw_data.get("billing_info")),
                    "first_cpt_code": (
                        raw_data.get("line_items", [{}])[0].get("cpt") if raw_data.get("line_items") else
                        raw_data.get("service_lines", [{}])[0].get("cpt_code") if raw_data.get("service_lines") else
                        "None"
                    ),
                    "sample_line_item": raw_data.get("line_items", [{}])[0] if raw_data.get("line_items") else None,
                    "sample_service_line": raw_data.get("service_lines", [{}])[0] if raw_data.get("service_lines") else None,
                    "data_structure": {
                        "top_level_keys": list(raw_data.keys()),
                        "service_line_keys": list(raw_data.get("service_lines", [{}])[0].keys()) if raw_data.get("service_lines") else [],
                        "patient_info_keys": list(raw_data.get("patient_info", {}).keys()),
                        "billing_info_keys": list(raw_data.get("billing_info", {}).keys())
                    }
                }
            
            # Step 2: Normalize HCFA data
            debug_info["processing_steps"].append("Normalizing HCFA data")
            try:
                normalized_data = normalize_hcfa_format(raw_data)
                debug_info["processing_steps"].append("HCFA data normalized successfully")
                debug_info["data_sample"]["normalized_line_items_count"] = len(normalized_data.get("line_items", []))
                debug_info["data_sample"]["normalized_sample"] = normalized_data.get("line_items", [{}])[0] if normalized_data.get("line_items") else None
            except Exception as e:
                debug_info["error_type"] = "NormalizationError"
                debug_info["error_message"] = str(e)
                debug_info["error_details"] = {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
                return debug_info
            
            # Step 3: Database connection
            debug_info["processing_steps"].append("Connecting to database")
            try:
                with self.db_service.connect_db() as conn:
                    debug_info["processing_steps"].append("Database connection successful")
                    
                    # Get order ID from normalized data
                    order_id = normalized_data.get("Order_ID")
                    if not order_id:
                        debug_info["error_type"] = "ValidationError"
                        debug_info["error_message"] = "No Order_ID found in file"
                        return debug_info
                    
                    # Get provider info and order details
                    provider_info = self.db_service.get_provider_details(order_id, conn)
                    order_details = self.db_service.get_full_details(order_id, conn)
                    order_lines = self.db_service.get_line_items(order_id, conn)
                    
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
                    
                    # Step 4: Run validators
                    debug_info["processing_steps"].append("Running validators")
                    validation_errors = []
                    
                    for validator_name, validator in validators.items():
                        try:
                            # Pass appropriate data to each validator
                            if validator_name == 'bundle':
                                result = validator.validate(order_data, normalized_data)
                            elif validator_name == 'intent':
                                result = validator.validate(order_data, normalized_data)
                            elif validator_name == 'line_items':
                                result = validator.validate(normalized_data.get('line_items', []), order_lines)
                            elif validator_name == 'rate':
                                result = validator.validate(normalized_data.get('line_items', []), order_id)
                            else:
                                result = validator.validate(normalized_data)
                            
                            debug_info["validation_results"][validator_name] = {
                                "status": result.get("status", "UNKNOWN"),
                                "messages": result.get("messages", []),
                                "details": result.get("details", {})
                            }
                            
                            if result.get("status") == "FAIL":
                                validation_errors.append({
                                    "validator": validator_name,
                                    "messages": result.get("messages", []),
                                    "details": result.get("details", {})
                                })
                        except Exception as e:
                            debug_info["validation_results"][validator_name] = {
                                "status": "ERROR",
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "traceback": traceback.format_exc()
                            }
                            validation_errors.append({
                                "validator": validator_name,
                                "error": str(e),
                                "error_type": type(e).__name__
                            })
                    
                    if validation_errors:
                        debug_info["error_type"] = "ValidationError"
                        debug_info["error_message"] = f"Found {len(validation_errors)} validation errors"
                        debug_info["error_details"] = {
                            "validation_errors": validation_errors
                        }
                    else:
                        debug_info["success"] = True
                        debug_info["processing_steps"].append("All validations passed")
                
            except Exception as e:
                debug_info["error_type"] = "DatabaseError"
                debug_info["error_message"] = str(e)
                debug_info["error_details"] = {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
                return debug_info
            
            return debug_info
            
        except Exception as e:
            debug_info["error_type"] = "ProcessingError"
            debug_info["error_message"] = str(e)
            debug_info["error_details"] = {
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
            return debug_info

    def run(self, quiet: bool = False):
        """
        Main execution method to process all JSON files.
        
        Args:
            quiet (bool): Whether to suppress output messages
        """
        self.quiet = quiet
        
        with self.db_service.connect_db() as conn:
            # Load reference data
            dim_proc_df = pd.read_sql_query("SELECT * FROM dim_proc", conn)
            
            # Initialize code mapper
            code_mapper = CodeMapper(settings.CLINICAL_EQUIV_CONFIG)
            
            # Initialize all validators
            validators = {
                'bundle': BundleValidator(),
                'intent': ClinicalIntentValidator(),
                'line_items': LineItemValidator(),
                'modifier': ModifierValidator(),
                'units': UnitsValidator(),
                'rate': RateValidator(conn, quiet=self.quiet),
                'cpt': CPTValidator()
            }

            # Check for files in the escalations folder
            escalation_files = self._get_escalation_files()
            
            # Find all JSON files in the staging folder
            json_files = list(Path(settings.JSON_PATH).glob('*.json'))
            total_files = len(json_files)
            skipped_files = 0
            
            # Process each file, skipping those that exist in the escalations folder
            for index, json_file in enumerate(json_files, 1):
                # Check if this file should be skipped
                if json_file.name in escalation_files:
                    if not quiet:
                        print(f"Skipping {json_file.name} - already in escalations folder")
                    skipped_files += 1
                    continue
                
                # Process the file normally
                self.process_file(json_file, validators)
                
            if not quiet:
                print(f"Processed {total_files - skipped_files} files, skipped {skipped_files} files.")
            else:
                # Always print summary stats even in quiet mode
                print(f"Summary: Processed {total_files - skipped_files}, skipped {skipped_files}")

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
        
        # Print only the validation summary - always show this regardless of quiet mode
        pass_count = sum(1 for r in self.validation_results if r.status == 'PASS')
        fail_count = sum(1 for r in self.validation_results if r.status == 'FAIL')
        print(f"Validation Summary: {len(self.validation_results)} files | Pass: {pass_count} | Fail: {fail_count}")

    def run_debug(self, sample_size: int = 5, quiet: bool = False):
        """
        Run the application in debug mode on a small sample of files.
        
        Args:
            sample_size: Number of files to process in debug mode
            quiet (bool): Whether to suppress output messages
        """
        self.quiet = quiet
        
        if not quiet:
            print(f"\nStarting debug mode with sample size: {sample_size}")
        
        # Create debug directory
        debug_dir = settings.LOG_PATH / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for files in the escalations folder
        escalation_files = self._get_escalation_files()
        
        # Get list of JSON files, excluding those in the escalations folder
        all_json_files = list(settings.JSON_PATH.glob("*.json"))
        json_files = [f for f in all_json_files if f.name not in escalation_files]
        
        if not json_files:
            if not quiet:
                print("No JSON files found to process (or all files are in escalations folder)")
            return
        
        if not quiet:
            print(f"Found {len(all_json_files)} files, {len(all_json_files) - len(json_files)} skipped due to escalations.")
        
        # Take a sample of files
        sample_files = random.sample(json_files, min(sample_size, len(json_files)))
        
        # Load reference data from database
        if not quiet:
            print("\nLoading reference data...")
        try:
            with self.db_service.connect_db() as conn:
                dim_proc_df = pd.read_sql_query("SELECT * FROM dim_proc", conn)
                if not quiet:
                    print(f"Loaded dim_proc_df with {len(dim_proc_df)} rows")
                    print(f"Columns: {list(dim_proc_df.columns)}")
                    if not dim_proc_df.empty:
                        print(f"Sample row: {dim_proc_df.iloc[0].to_dict()}")
            
                # Initialize validators with database connection
                validators = {
                    'bundle': BundleValidator(),
                    'intent': ClinicalIntentValidator(), 
                    'line_items': LineItemValidator(),
                    'modifier': ModifierValidator(),
                    'units': UnitsValidator(),
                    'rate': RateValidator(conn, quiet=self.quiet),  # Pass the database connection
                    'cpt': CPTValidator()
                }
                
                # Process each file
                debug_results = []
                for file_path in sample_files:
                    if not quiet:
                        print(f"\nProcessing file: {file_path.name}")
                    try:
                        debug_result = self.debug_process_file(file_path, validators)
                        debug_results.append(debug_result)
                        
                        # Save individual debug info
                        debug_file = debug_dir / f"{file_path.stem}_debug.json"
                        with open(debug_file, 'w') as f:
                            json.dump(debug_result, f, indent=2)
                        
                        # Print detailed info only in non-quiet mode
                        if debug_result["success"]:
                            if not quiet:
                                print(f"✓ Successfully processed {file_path.name}")
                                print("  Processing steps:")
                                for step in debug_result["processing_steps"]:
                                    print(f"    - {step}")
                        else:
                            if not quiet:
                                print(f"✗ Failed to process {file_path.name}")
                                print(f"  Error type: {debug_result['error_type']}")
                                print(f"  Error message: {debug_result['error_message']}")
                            
                            if debug_result.get("error_details"):
                                if "validation_errors" in debug_result["error_details"]:
                                    if not quiet:
                                        print("\n  Validation errors:")
                                        for error in debug_result["error_details"]["validation_errors"]:
                                            print(f"    - {error['validator']}:")
                                            for msg in error.get("messages", []):
                                                print(f"      * {msg}")
                                else:
                                    if not quiet:
                                        print(f"  Error details: {debug_result['error_details']}")
                            
                            if debug_result.get("data_sample"):
                                if not quiet:
                                    print("\n  Data sample:")
                                    sample = debug_result["data_sample"]
                                    print(f"    - Line items count: {sample.get('line_items_count', 'unknown')}")
                                    print(f"    - Has bundle info: {sample.get('has_bundle_info', False)}")
                                    print(f"    - Has Order ID: {sample.get('has_order_id', False)}")
                        
                    except Exception as e:
                        if not quiet:
                            print(f"✗ Error processing {file_path.name}: {str(e)}")
                        debug_results.append({
                            "file_path": str(file_path),
                            "file_name": file_path.name,
                            "success": False,
                            "error_type": "ProcessingError",
                            "error_message": str(e),
                            "error_details": {
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "traceback": traceback.format_exc()
                            }
                        })
                
                # Analyze results
                self._analyze_debug_results(debug_results)
                
                # Print summary - always show regardless of quiet mode
                success_count = sum(1 for r in debug_results if r["success"])
                failed_count = len(debug_results) - success_count
                print(f"Debug Summary: {len(debug_results)} files | Success: {success_count} | Failed: {failed_count}")
                
                # Print error types
                error_types = {}
                for result in debug_results:
                    if not result["success"]:
                        error_type = result["error_type"]
                        error_types[error_type] = error_types.get(error_type, 0) + 1
                
                if error_types and not quiet:
                    print("\nError types:")
                    for error_type, count in error_types.items():
                        print(f"  - {error_type}: {count} files")
                
        except Exception as e:
            if not quiet:
                print(f"Error loading reference data: {str(e)}")
            return

    def _analyze_debug_results(self, debug_results):
        """
        Analyze debug results to identify patterns in failures.
        
        Args:
            debug_results: List of debug result dictionaries
        """
        from collections import Counter
        
        error_types = Counter([r["error_type"] for r in debug_results if not r["success"]])
        failing_steps = Counter([r["processing_steps"][-1] for r in debug_results if not r["success"] and r["processing_steps"]])
        
        # Save analysis
        analysis = {
            "total_files": len(debug_results),
            "success_count": sum(1 for r in debug_results if r["success"]),
            "failure_count": sum(1 for r in debug_results if not r["success"]),
            "error_types": dict(error_types),
            "failing_steps": dict(failing_steps),
            "common_patterns": {
                "missing_order_id": sum(1 for r in debug_results if not r.get("order_id")),
                "normalization_failures": sum(1 for r in debug_results if r.get("normalization_success") is False),
                "db_connection_failures": sum(1 for r in debug_results if r.get("db_connection_success") is False)
            }
        }
        
        # Save analysis to file
        analysis_file = settings.LOG_PATH / "debug" / "debug_analysis.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        
        # Always print the summary stats, regardless of quiet mode
        print(f"Analysis Summary: {analysis['total_files']} files | Success: {analysis['success_count']} | Failed: {analysis['failure_count']}")
        
        # Show detailed stats only if not quiet
        if hasattr(self, 'quiet') and not self.quiet:
            print("\nError types:")
            for error_type, count in error_types.most_common():
                print(f"  {error_type}: {count}")
            print("\nFailing steps:")
            for step, count in failing_steps.most_common():
                print(f"  {step}: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Healthcare Bill Review System 2.0")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--sample", type=int, default=5, help="Number of files to debug")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential output")
    args = parser.parse_args()
    
    if not args.quiet:
        print("Healthcare Bill Review System 2.0")
        print("=================================")
    
    app = BillReviewApplication()
    
    if args.debug:
        app.run_debug(sample_size=args.sample, quiet=args.quiet)
    else:
        app.run(quiet=args.quiet)
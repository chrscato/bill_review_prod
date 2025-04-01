# Enhanced reporting service 
# core/services/reporter.py
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
import pandas as pd
from collections import Counter

class ValidationReporter:
    """
    Enhanced reporting service for generating detailed validation reports.
    Provides insights and statistics about validation results.
    """
    
    def __init__(self, log_dir: Path):
        """
        Initialize the validation reporter.
        
        Args:
            log_dir: Directory for validation logs
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True, parents=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.detailed_results = []
        self.summary = {}
        
    def add_result(self, result: Dict) -> None:
        """
        Add a validation result to the report.
        
        Args:
            result: Validation result dictionary
        """
        self.detailed_results.append(result)
    
    def add_results(self, results: List[Dict]) -> None:
        """
        Add multiple validation results to the report.
        
        Args:
            results: List of validation result dictionaries
        """
        self.detailed_results.extend(results)
    
    def generate_summary(self) -> Dict:
        """
        Generate summary statistics from validation results.
        
        Returns:
            Dict: Summary statistics
        """
        if not self.detailed_results:
            return {"error": "No validation results to summarize"}
        
        # Count by status
        status_counts = Counter(r.get('status') for r in self.detailed_results)
        
        # Count by validation type
        validation_type_counts = Counter(r.get('validation_type') for r in self.detailed_results)
        
        # Analyze bundle validations
        bundle_results = [r for r in self.detailed_results if r.get('validation_type') == 'bundle']
        bundle_statuses = Counter(r.get('bundle_comparison', {}).get('status') for r in bundle_results)
        
        # Analyze validation failures
        failures = [r for r in self.detailed_results if r.get('status') == 'FAIL']
        failure_types = Counter(r.get('validation_type') for r in failures)
        
        # Calculate success rate
        total_validations = len(self.detailed_results)
        success_rate = status_counts.get('PASS', 0) / total_validations if total_validations > 0 else 0
        
        # Count component billing failures
        component_billing_failures = len([r for r in self.detailed_results if 
                                      r.get('status') == 'FAIL' and 
                                      r.get('details', {}).get('component_billing', {}).get('is_component_billing', False)])
        
        # Generate summary
        self.summary = {
            "timestamp": self.timestamp,
            "total_validations": total_validations,
            "status_counts": dict(status_counts),
            "validation_type_counts": dict(validation_type_counts),
            "bundle_analysis": {
                "total_bundles": len(bundle_results),
                "bundle_statuses": dict(bundle_statuses)
            },
            "failure_analysis": {
                "total_failures": len(failures),
                "failure_types": dict(failure_types)
            },
            "success_rate": success_rate * 100,
            "total_files": total_validations,
            "passed_files": status_counts.get('PASS', 0),
            "failed_files": status_counts.get('FAIL', 0),
            "component_billing_failures": component_billing_failures
        }
        
        return self.summary
    
    def generate_html_report(self) -> str:
        """
        Generate an HTML report for validation results.
        
        Returns:
            str: Path to the HTML report file
        """
        if not self.detailed_results:
            return "No results to report"
            
        # Generate summary if not already done
        if not self.summary:
            self.generate_summary()
            
        # Create HTML content
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bill Review Validation Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1, h2, h3 { color: #333; }
                .summary { background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
                .success { color: green; }
                .failure { color: red; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .bundle-info { background-color: #e6f7ff; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
                .error-message { color: #d32f2f; }
            </style>
        </head>
        <body>
            <h1>Bill Review Validation Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p>Report generated: ${timestamp}</p>
                <p>Total validations: ${total_validations}</p>
                <p>Success rate: <span class="${success_class}">${success_rate}%</span></p>
                <p>Pass: ${pass_count} | Fail: ${fail_count}</p>
                
                <h3>Validation Types</h3>
                <ul>
                    ${validation_type_list}
                </ul>
                
                <h3>Bundle Analysis</h3>
                <p>Total bundles: ${total_bundles}</p>
                <ul>
                    ${bundle_status_list}
                </ul>
            </div>
            
            <h2>Failure Details</h2>
            <table>
                <tr>
                    <th>Validation Type</th>
                    <th>File Name</th>
                    <th>Order ID</th>
                    <th>Message</th>
                </tr>
                ${failure_rows}
            </table>
            
            <h2>Bundle Details</h2>
            <table>
                <tr>
                    <th>Bundle Type</th>
                    <th>Status</th>
                    <th>File Name</th>
                    <th>Order ID</th>
                    <th>Description</th>
                </tr>
                ${bundle_rows}
            </table>
        </body>
        </html>
        """
        
        # Replace placeholders with actual data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_validations = self.summary.get('total_validations', 0)
        success_rate = round(self.summary.get('success_rate', 0), 2)
        success_class = "success" if success_rate >= 90 else "failure"
        pass_count = self.summary.get('status_counts', {}).get('PASS', 0)
        fail_count = self.summary.get('status_counts', {}).get('FAIL', 0)
        
        # Generate validation type list
        validation_type_list = ""
        for vtype, count in self.summary.get('validation_type_counts', {}).items():
            validation_type_list += f"<li>{vtype}: {count}</li>"
        
        # Generate bundle status list
        bundle_status_list = ""
        for status, count in self.summary.get('bundle_analysis', {}).get('bundle_statuses', {}).items():
            bundle_status_list += f"<li>{status}: {count}</li>"
        
        # Generate failure rows
        failure_rows = ""
        for result in [r for r in self.detailed_results if r.get('status') == 'FAIL']:
            messages = result.get('messages', [])
            message = messages[0] if messages else "No message"
            
            # Check if this is a component billing failure
            is_component_failure = False
            component_type = ""
            if 'details' in result and 'component_billing' in result['details']:
                component_info = result['details']['component_billing']
                if component_info.get('is_component_billing'):
                    is_component_failure = True
                    component_type = component_info.get('component_type', 'unknown')
            
            failure_type = "Component Billing" if is_component_failure else result.get('validation_type', 'unknown')
            
            failure_rows += f"""
            <tr>
                <td>{failure_type}</td>
                <td>{result.get('file_name', 'unknown')}</td>
                <td>{result.get('order_id', 'unknown')}</td>
                <td class="error-message">{message}</td>
            </tr>
            """
        
        # Generate bundle rows
        bundle_rows = ""
        for result in [r for r in self.detailed_results if r.get('validation_type') == 'bundle']:
            bundle_comparison = result.get('bundle_comparison', {})
            bundle_status = bundle_comparison.get('status', 'unknown')
            bundle_message = bundle_comparison.get('message', 'No description')
            
            # Get bundle information
            bundle_name = "N/A"
            bundle_type = "N/A"
            
            if 'hcfa_bundle' in bundle_comparison and bundle_comparison['hcfa_bundle']:
                hcfa_bundle = bundle_comparison['hcfa_bundle']
                bundle_name = hcfa_bundle.get('bundle_name', 'N/A')
                bundle_type = hcfa_bundle.get('bundle_type', 'N/A')
            
            bundle_rows += f"""
            <tr>
                <td>{bundle_type}</td>
                <td>{bundle_status}</td>
                <td>{result.get('file_name', 'unknown')}</td>
                <td>{result.get('order_id', 'unknown')}</td>
                <td>{bundle_message}</td>
            </tr>
            """
        
        # Populate template
        html_content = html_content.replace("${timestamp}", timestamp)
        html_content = html_content.replace("${total_validations}", str(total_validations))
        html_content = html_content.replace("${success_rate}", str(success_rate))
        html_content = html_content.replace("${success_class}", success_class)
        html_content = html_content.replace("${pass_count}", str(pass_count))
        html_content = html_content.replace("${fail_count}", str(fail_count))
        html_content = html_content.replace("${validation_type_list}", validation_type_list)
        html_content = html_content.replace("${total_bundles}", str(self.summary.get('bundle_analysis', {}).get('total_bundles', 0)))
        html_content = html_content.replace("${bundle_status_list}", bundle_status_list)
        html_content = html_content.replace("${failure_rows}", failure_rows)
        html_content = html_content.replace("${bundle_rows}", bundle_rows)
        
        # Write HTML to file
        html_path = self.log_dir / f"validation_report_{self.timestamp}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(html_path)
    
    def save_report(self, include_html: bool = True) -> Dict:
        """
        Save validation report to files.
        
        Args:
            include_html: Whether to generate HTML report
            
        Returns:
            Dict: Paths to created report files
        """
        # Generate summary if not already done
        if not self.summary:
            self.generate_summary()
        
        # Create report paths
        detailed_json_path = self.log_dir / f"validation_detailed_{self.timestamp}.json"
        summary_json_path = self.log_dir / f"validation_summary_{self.timestamp}.json"
        
        # Helper function to convert non-JSON serializable objects
        def json_serializable_converter(obj):
            if isinstance(obj, set):
                return list(obj)
            elif hasattr(obj, 'to_dict'):
                return obj.to_dict()
            elif hasattr(obj, '__dict__'):
                return obj.__dict__
            elif hasattr(obj, 'item'):  # Handle numpy types
                return obj.item()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        # Save detailed results
        with open(detailed_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.detailed_results, f, indent=2, default=json_serializable_converter)
        
        # Save summary
        with open(summary_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, indent=2, default=json_serializable_converter)
        
        report_paths = {
            "detailed_json": str(detailed_json_path),
            "summary_json": str(summary_json_path)
        }
        
        # Generate HTML report if requested
        if include_html:
            html_path = self.generate_html_report()
            report_paths["html"] = html_path
        
        return report_paths
    
    def export_to_excel(self) -> str:
        """
        Export validation results to Excel.
        
        Returns:
            str: Path to the Excel file
        """
        if not self.detailed_results:
            return "No results to export"
        
        # Create Excel writer
        excel_path = self.log_dir / f"validation_results_{self.timestamp}.xlsx"
        
        # Create DataFrames for different sheets
        summary_data = pd.DataFrame([self.summary])
        
        # Create validation results DataFrame
        results_data = []
        for result in self.detailed_results:
            # Extract key information
            basic_result = {
                "file_name": result.get("file_name"),
                "order_id": result.get("order_id"),
                "validation_type": result.get("validation_type"),
                "status": result.get("status"),
                "message": result.get("messages", [""])[0] if result.get("messages") else "",
                "timestamp": result.get("timestamp")
            }
            
            # Add bundle-specific information if applicable
            if result.get("validation_type") == "bundle":
                bundle_comparison = result.get("bundle_comparison", {})
                basic_result.update({
                    "bundle_status": bundle_comparison.get("status"),
                    "bundle_message": bundle_comparison.get("message"),
                    "bundle_name": bundle_comparison.get("hcfa_bundle", {}).get("bundle_name") if bundle_comparison.get("hcfa_bundle") else None,
                    "bundle_type": bundle_comparison.get("hcfa_bundle", {}).get("bundle_type") if bundle_comparison.get("hcfa_bundle") else None
                })
            
            results_data.append(basic_result)
        
        results_df = pd.DataFrame(results_data)
        
        # Create bundle-specific DataFrame
        bundle_data = []
        for result in [r for r in self.detailed_results if r.get("validation_type") == "bundle"]:
            bundle_comparison = result.get("bundle_comparison", {})
            if bundle_comparison.get("status") != "NO_BUNDLE":
                # Extract bundle details
                order_bundle = bundle_comparison.get("order_bundle", {})
                hcfa_bundle = bundle_comparison.get("hcfa_bundle", {})
                
                bundle_details = {
                    "file_name": result.get("file_name"),
                    "order_id": result.get("order_id"),
                    "bundle_status": bundle_comparison.get("status"),
                    "bundle_message": bundle_comparison.get("message"),
                    "order_bundle_name": order_bundle.get("bundle_name") if order_bundle else None,
                    "hcfa_bundle_name": hcfa_bundle.get("bundle_name") if hcfa_bundle else None,
                    "order_bundle_type": order_bundle.get("bundle_type") if order_bundle else None,
                    "hcfa_bundle_type": hcfa_bundle.get("bundle_type") if hcfa_bundle else None,
                    "order_body_part": order_bundle.get("body_part") if order_bundle else None,
                    "hcfa_body_part": hcfa_bundle.get("body_part") if hcfa_bundle else None
                }
                
                # Add details about missing codes
                if "details" in bundle_comparison:
                    details = bundle_comparison["details"]
                    bundle_details.update({
                        "order_missing_core": ", ".join(details.get("order_missing_core", [])),
                        "hcfa_missing_core": ", ".join(details.get("hcfa_missing_core", [])),
                        "shared_codes": ", ".join(details.get("shared_codes", [])),
                        "order_only_codes": ", ".join(details.get("order_only_codes", [])),
                        "hcfa_only_codes": ", ".join(details.get("hcfa_only_codes", []))
                    })
                
                bundle_data.append(bundle_details)
        
        bundle_df = pd.DataFrame(bundle_data) if bundle_data else pd.DataFrame()
        
        # Create rate validation DataFrame
        rate_data = []
        for result in [r for r in self.detailed_results if r.get("validation_type") == "rate"]:
            rate_results = result.get("results", [])
            for rate_result in rate_results:
                rate_detail = {
                    "file_name": result.get("file_name"),
                    "order_id": result.get("order_id"),
                    "cpt": rate_result.get("cpt"),
                    "status": rate_result.get("status"),
                    "rate_source": rate_result.get("rate_source"),
                    "base_rate": rate_result.get("base_rate"),
                    "units": rate_result.get("units"),
                    "unit_adjusted_rate": rate_result.get("unit_adjusted_rate"),
                    "is_bundled": rate_result.get("is_bundled", False),
                    "bundle_name": rate_result.get("bundle_name"),
                    "message": rate_result.get("message", "")
                }
                rate_data.append(rate_detail)
        
        rate_df = pd.DataFrame(rate_data) if rate_data else pd.DataFrame()
        
        # Write DataFrames to Excel
        with pd.ExcelWriter(excel_path) as writer:
            summary_data.to_excel(writer, sheet_name='Summary', index=False)
            results_df.to_excel(writer, sheet_name='Validation Results', index=False)
            
            if not bundle_df.empty:
                bundle_df.to_excel(writer, sheet_name='Bundle Analysis', index=False)
                
            if not rate_df.empty:
                rate_df.to_excel(writer, sheet_name='Rate Analysis', index=False)
        
        return str(excel_path)
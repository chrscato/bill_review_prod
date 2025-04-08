# core/validators/rate_validator.py
from typing import Dict, List, Set, Optional, Tuple
import pandas as pd
import sqlite3
from utils.helpers import clean_tin, safe_int
import logging

class RateValidator:
    """
    Enhanced rate validator with bundle awareness and clinical equivalence support.
    """
    
    def __init__(self, conn: sqlite3.Connection, bundle_rates_path: Optional[str] = None):
        """
        Initialize the rate validator.
        
        Args:
            conn: SQLite database connection
            bundle_rates_path: Path to bundle rates config (optional)
        """
        self.conn = conn
        self.bundle_rates = {}
        self.logger = logging.getLogger(__name__)
        
        # Load bundle rates if provided
        if bundle_rates_path:
            self._load_bundle_rates(bundle_rates_path)
    
    def _load_bundle_rates(self, config_path: str) -> None:
        """Load bundle rate configuration if available."""
        import json
        from pathlib import Path
        
        try:
            with open(Path(config_path), 'r') as f:
                self.bundle_rates = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Warning: Could not load bundle rates from {config_path}")
            self.bundle_rates = {}
    
    def get_bundle_rate(self, 
                       bundle_name: str, 
                       provider_tin: str, 
                       network_status: str) -> Optional[float]:
        """
        Get rate for a bundle based on provider and network status.
        
        Args:
            bundle_name: Name of the bundle
            provider_tin: Provider TIN
            network_status: Network status (in-network, out-of-network)
            
        Returns:
            float: Bundle rate or None if not found
        """
        if not self.bundle_rates:
            return None
            
        # First look for provider-specific bundle rate
        if provider_tin in self.bundle_rates.get('provider_specific', {}):
            provider_bundles = self.bundle_rates['provider_specific'][provider_tin]
            if bundle_name in provider_bundles:
                return provider_bundles[bundle_name].get('rate')
        
        # Then look for network-specific bundle rate
        network_key = 'in_network' if network_status == 'in-network' else 'out_network'
        if network_key in self.bundle_rates:
            return self.bundle_rates[network_key].get(bundle_name, {}).get('rate')
        
        # Finally look for default bundle rate
        return self.bundle_rates.get('default', {}).get(bundle_name, {}).get('rate')
    
    def validate(self, hcfa_lines: List[Dict], order_id: str) -> Dict:
        """
        Validate rates for CPT codes with enhanced bundle handling.
        
        Args:
            hcfa_lines: Line items from HCFA data
            order_id: Order ID for reference data
            
        Returns:
            Dict: Validation results
        """
        rate_results = []
        
        # Get provider details for this order
        provider_details = self._get_provider_details(order_id)
        if not provider_details:
            return {
                "status": "FAIL",
                "reason": "Provider details not found",
                "results": [],
                "total_rate": 0,
                "messages": ["Provider details not found for this order"]
            }

        # Extract provider information
        clean_provider_tin = clean_tin(provider_details.get('TIN', ''))
        provider_network = provider_details.get('Provider Network', 'unknown')
        
        # Fetch procedure categories
        dim_proc_df = pd.read_sql_query("SELECT proc_cd, proc_category FROM dim_proc", self.conn)
        proc_categories = dict(zip(dim_proc_df['proc_cd'], dim_proc_df['proc_category']))
        
        # Counters for reporting
        has_any_failure = False
        total_rate = 0
        rate_sources = {}
        
        # Check for bundle first
        bundle_name = None
        bundle_type = None
        bundle_modality = None
        bundle_body_part = None
        
        # If any line has a bundle_type, consider it a bundle
        for line in hcfa_lines:
            if line.get("bundle_type") and line.get("bundle_name"):
                bundle_type = line.get("bundle_type")
                bundle_name = line.get("bundle_name")
                bundle_modality = line.get("bundle_modality", "unknown")
                bundle_body_part = line.get("bundle_body_part", "unknown")
                break
        
        # BUNDLE RATE HANDLING
        bundle_rate = None
        if bundle_name and bundle_type:
            bundle_rate = self.get_bundle_rate(bundle_name, clean_provider_tin, provider_network)
            
            # Log bundle rate processing
            self.logger.info(f"Processing bundled rate for {bundle_name} ({bundle_type})")
            if bundle_rate is None:
                self.logger.info(f"No bundle rate found for {bundle_name}, using component rates")
        
        if bundle_name and bundle_type and bundle_rate is not None:
            for line in hcfa_lines:
                cpt = str(line.get('cpt', ''))
                units = safe_int(line.get('units', 1))
                
                # Check if this CPT is part of the bundle
                is_bundle_component = (
                    line.get("bundle_type") == bundle_type and 
                    line.get("bundle_name") == bundle_name
                )
                
                if is_bundle_component:
                    # This is a bundle component, use proportional bundle rate
                    # Each component gets marked as bundle rate with 0.00 except the primary one
                    if 'primary_component' in line and line['primary_component']:
                        # Primary component gets the full bundle rate
                        unit_adjusted_rate = bundle_rate
                        rate_source = "Bundle Rate (Primary)"
                    else:
                        # Non-primary components get 0.00 rate (already included in bundle)
                        unit_adjusted_rate = 0.00
                        rate_source = "Bundle Rate (Included)"
                    
                    result = {
                        **line, 
                        "status": "PASS", 
                        "base_rate": unit_adjusted_rate,
                        "unit_adjusted_rate": unit_adjusted_rate,
                        "units": units,
                        "rate_source": rate_source,
                        "validated_rate": unit_adjusted_rate,
                        "is_bundled": True,
                        "bundle_name": bundle_name
                    }
                    rate_results.append(result)
                    
                    # Only count the primary component in the total
                    if 'primary_component' in line and line['primary_component']:
                        total_rate += unit_adjusted_rate
                        rate_sources[rate_source] = rate_sources.get(rate_source, 0) + 1
                else:
                    # Not a bundle component, validate normally
                    self._validate_individual_rate(
                        line, 
                        clean_provider_tin, 
                        provider_network, 
                        proc_categories,
                        total_rate, 
                        rate_sources, 
                        rate_results
                    )
            
            # Return results for bundle rate
            return {
                "status": "PASS",
                "results": rate_results,
                "total_rate": total_rate,
                "provider_details": provider_details,
                "bundle_name": bundle_name,
                "bundle_type": bundle_type, 
                "messages": [f"Bundle rate validated successfully: ${bundle_rate:.2f} for {bundle_name}"]
            }
        else:
            # COMPONENT-BASED RATE VALIDATION
            for line in hcfa_lines:
                component_result = self._validate_individual_rate(
                    line, 
                    clean_provider_tin, 
                    provider_network, 
                    proc_categories,
                    total_rate, 
                    rate_sources, 
                    rate_results
                )
                
                total_rate += component_result.get('unit_adjusted_rate', 0) if component_result.get('status') == 'PASS' else 0
                if component_result.get('status') == 'FAIL':
                    has_any_failure = True
                
                # Track rate sources for reporting
                if component_result.get('status') == 'PASS':
                    rate_source = component_result.get('rate_source', 'Unknown')
                    rate_sources[rate_source] = rate_sources.get(rate_source, 0) + 1

        # Determine final rate validation status
        has_failures = any(r.get("status") == "FAIL" for r in rate_results)
        
        return {
            "status": "FAIL" if has_failures else "PASS",
            "results": rate_results,
            "total_rate": total_rate,
            "provider_details": provider_details,
            "rate_sources": rate_sources,
            "bundle_name": bundle_name,
            "bundle_type": bundle_type,
            "messages": self._generate_messages(rate_results, total_rate, rate_sources, bundle_name)
        }
    
    def _validate_individual_rate(self, 
                                line: Dict, 
                                provider_tin: str, 
                                provider_network: str, 
                                proc_categories: Dict,
                                total_rate: float, 
                                rate_sources: Dict, 
                                rate_results: List) -> Dict:
        """
        Validate rate for an individual line item.
        
        Args:
            line: Line item data
            provider_tin: Provider TIN
            provider_network: Provider network status
            proc_categories: Procedure categories mapping
            total_rate: Running total rate (modified in place)
            rate_sources: Rate sources tracking dict (modified in place)
            rate_results: Results list (modified in place)
            
        Returns:
            Dict: Individual rate validation result
        """
        cpt = str(line.get('cpt', ''))
        units = safe_int(line.get('units', 1))
        modifier = line.get('modifier', '')  # Get modifier from line item
        
        # Default values if validation fails
        base_rate = None
        unit_adjusted_rate = None
        rate_source = "Unknown"
        
        # Skip validation for ancillary codes (they always pass with 0.00 rate)
        if cpt in proc_categories and proc_categories[cpt].lower() == 'ancillary':
            base_rate = 0.00
            unit_adjusted_rate = 0.00
            rate_source = "Ancillary"
            
            result = {
                **line, 
                "status": "PASS", 
                "base_rate": base_rate,
                "unit_adjusted_rate": unit_adjusted_rate,
                "units": units,
                "rate_source": rate_source,
                "validated_rate": unit_adjusted_rate
            }
            rate_results.append(result)
            return result

        # Try PPO Rate first (for all providers)
        ppo_rate = self._get_ppo_rate(provider_tin, cpt, modifier)
        
        if ppo_rate is not None:
            base_rate = float(ppo_rate)
            unit_adjusted_rate = base_rate * units
            rate_source = "PPO"
            
            result = {
                **line, 
                "status": "PASS", 
                "base_rate": base_rate,
                "unit_adjusted_rate": unit_adjusted_rate,
                "units": units,
                "rate_source": rate_source,
                "validated_rate": unit_adjusted_rate
            }
            rate_results.append(result)
            total_rate += unit_adjusted_rate
            rate_sources[rate_source] = rate_sources.get(rate_source, 0) + 1
            return result
            
        # Try OTA Rate next
        ota_rate = self._get_ota_rate(line.get('order_id', ''), cpt)
        
        if ota_rate is not None:
            base_rate = float(ota_rate)
            unit_adjusted_rate = base_rate * units
            rate_source = "OTA"
            
            result = {
                **line, 
                "status": "PASS", 
                "base_rate": base_rate,
                "unit_adjusted_rate": unit_adjusted_rate,
                "units": units,
                "rate_source": rate_source,
                "validated_rate": unit_adjusted_rate
            }
            rate_results.append(result)
            total_rate += unit_adjusted_rate
            rate_sources[rate_source] = rate_sources.get(rate_source, 0) + 1
            return result
            
        # Try equivalent codes for rate
        equivalent_rate = self._get_equivalent_code_rate(provider_tin, cpt)
        
        if equivalent_rate is not None:
            base_rate = float(equivalent_rate['rate'])
            unit_adjusted_rate = base_rate * units
            rate_source = f"Equivalent ({equivalent_rate['code']})"
            
            result = {
                **line, 
                "status": "PASS", 
                "base_rate": base_rate,
                "unit_adjusted_rate": unit_adjusted_rate,
                "units": units,
                "rate_source": rate_source,
                "equivalent_code": equivalent_rate['code'],
                "validated_rate": unit_adjusted_rate
            }
            rate_results.append(result)
            total_rate += unit_adjusted_rate
            rate_sources[rate_source] = rate_sources.get(rate_source, 0) + 1
            return result
            
        # If no rate is found, mark as failure
        failure_message = f"No rate found for CPT {cpt}"
        if modifier in ['26', 'TC']:
            failure_message += f" with modifier {modifier}"
            
        result = {
            **line, 
            "validated_rate": None, 
            "status": "FAIL",
            "base_rate": None,
            "unit_adjusted_rate": None,
            "units": units,
            "rate_source": None,
            "message": failure_message
        }
        rate_results.append(result)
        return result
    
    def _get_provider_details(self, order_id: str) -> Dict:
        """Get provider details for an order."""
        query = """
        SELECT 
            p."Address 1 Full",
            p."Billing Address 1",
            p."Billing Address 2",
            p."Billing Address City",
            p."Billing Address Postal Code",
            p."Billing Address State",
            p."Billing Name",
            p."DBA Name Billing Name",
            p."Latitude",
            p."Location",
            p."Need OTA",
            p."Provider Network",
            p."Provider Status",
            p."Provider Type",
            p."TIN",
            p."NPI",
            p.PrimaryKey
        FROM orders o
        JOIN providers p ON o.provider_id = p.PrimaryKey
        WHERE o.Order_ID = ?
        """
        
        df = pd.read_sql_query(query, self.conn, params=[order_id])
        if df.empty:
            return {}
        return df.iloc[0].to_dict()
    
    def _clean_rate_string(self, rate_str: str) -> float:
        """
        Clean a rate string by removing currency symbols, spaces, and commas.
        
        Args:
            rate_str: Rate string to clean
            
        Returns:
            float: Cleaned rate value
        """
        if not rate_str:
            self.logger.warning("Empty rate string received")
            return 0.0
            
        # Log the original rate string
        self.logger.debug(f"Cleaning rate string: '{rate_str}'")
        
        try:
            # First try direct float conversion
            return float(rate_str)
        except (ValueError, TypeError):
            # If that fails, try cleaning the string
            # Remove currency symbols, spaces, and commas
            cleaned = str(rate_str).replace('$', '').replace(',', '').strip()
            self.logger.debug(f"Cleaned rate string: '{cleaned}'")
            
            try:
                return float(cleaned)
            except (ValueError, TypeError) as e:
                self.logger.error(f"Failed to convert rate string '{rate_str}' to float: {str(e)}")
                return 0.0

    def _get_ppo_rate(self, provider_tin: str, cpt_code: str, modifier: Optional[str] = None) -> Optional[float]:
        """Get PPO rate for a provider and CPT code, considering modifiers 26 and TC if present."""
        # Clean TIN - remove non-digits
        clean_tin = ''.join(c for c in provider_tin if c.isdigit())
        
        # Base query for standard rate lookup
        base_query = "SELECT rate FROM ppo WHERE TRIM(TIN) = ? AND proc_cd = ?"
        params = [clean_tin, cpt_code]
        
        # Only consider TC or 26 modifiers
        if modifier in ['26', 'TC']:
            # Look for specific rate with the modifier
            query = base_query + " AND modifier = ?"
            params.append(modifier)
            
            result = pd.read_sql_query(query, self.conn, params=params)
            if not result.empty:
                return self._clean_rate_string(result['rate'].iloc[0])
            
            # If no rate found with modifier, return None (validation will fail)
            return None
        else:
            # For all other modifiers, ignore them and look for rate without modifier
            query = base_query + " AND (modifier IS NULL OR modifier = '' OR modifier = ?)"
            params.append(modifier)  # This will match empty modifier or the same modifier
            
            result = pd.read_sql_query(query, self.conn, params=params)
            if not result.empty:
                return self._clean_rate_string(result['rate'].iloc[0])
            
            return None
    
    def _get_ota_rate(self, order_id: str, cpt_code: str) -> Optional[float]:
        """Get OTA rate for an order and CPT code."""
        query = "SELECT rate FROM current_otas WHERE ID_Order_PrimaryKey = ? AND CPT = ?"
        result = pd.read_sql_query(query, self.conn, params=[order_id, cpt_code])
        
        if not result.empty:
            return self._clean_rate_string(result['rate'].iloc[0])
        return None
    
    def _get_equivalent_code_rate(self, provider_tin: str, cpt_code: str) -> Optional[Dict]:
        """
        Find rate for an equivalent code when the original code has no rate.
        
        Args:
            provider_tin: Provider TIN
            cpt_code: CPT code to find equivalent for
            
        Returns:
            Dict with rate and equivalent code, or None if no equivalent rate found
        """
        # This method would use the clinical_equivalents mapping to find alternatives
        # Simplified implementation for now - in production, this would use the 
        # clinical_equivalents.json configuration
        
        # Example equivalent groups - this would come from configuration
        equivalent_groups = {
            "CT Abdomen": ["74150", "74160", "74170", "74176", "74177", "74178"],
            "MRI Brain": ["70551", "70552", "70553"]
        }
        
        # Find if our CPT is in any equivalent group
        target_group = None
        for group_name, codes in equivalent_groups.items():
            if cpt_code in codes:
                target_group = codes
                break
        
        if not target_group:
            return None
        
        # Try to find rate for any code in the group
        for equivalent_code in target_group:
            if equivalent_code == cpt_code:
                continue  # Skip the original code
                
            rate = self._get_ppo_rate(provider_tin, equivalent_code)
            if rate is not None:
                return {"code": equivalent_code, "rate": rate}
        
        return None
    
    def _generate_messages(self, 
                         rate_results: List[Dict], 
                         total_rate: float, 
                         rate_sources: Dict,
                         bundle_name: Optional[str] = None) -> List[str]:
        """
        Generate human-readable messages about rate validation results.
        
        Args:
            rate_results: List of rate validation results
            total_rate: Total calculated rate
            rate_sources: Dictionary of rate sources and counts
            bundle_name: Name of the bundle if applicable
            
        Returns:
            List[str]: Human-readable messages
        """
        messages = []
        
        # Count failures
        failures = [r for r in rate_results if r.get("status") == "FAIL"]
        
        if not failures:
            # Bundle-specific message
            if bundle_name:
                messages.append(f"Bundle '{bundle_name}' rates validated successfully. Total rate: ${total_rate:.2f}")
            else:
                # Regular success message
                source_breakdown = ", ".join([f"{count} from {source}" for source, count in rate_sources.items()])
                messages.append(f"All rates validated successfully. Total rate: ${total_rate:.2f} ({source_breakdown})")
        else:
            if bundle_name:
                messages.append(f"Failed to validate some rates for bundle '{bundle_name}'.")
            else:
                messages.append(f"Failed to validate rates for {len(failures)} CPT codes.")
                
            failure_cpts = ", ".join([f"{r.get('cpt')}" for r in failures])
            messages.append(f"Missing rates for: {failure_cpts}")
            
            if len(rate_results) > len(failures):
                messages.append(f"Successfully validated {len(rate_results) - len(failures)} CPT codes. Partial total: ${total_rate:.2f}")
        
        return messages
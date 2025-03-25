# Healthcare Bill Review System 2.0

A comprehensive solution for validating medical bills against reference data with a focus on clinical intent rather than exact code matching.

## Overview

The Healthcare Bill Review System 2.0 is designed to validate healthcare claims by comparing HCFA data against reference orders with a focus on clinical intent and procedure purpose rather than exact CPT code matching. This approach recognizes that the same medical procedure may be coded differently between systems while still representing the same clinical service.

## Key Features

- **Intent-Based Validation**: Validates based on clinical intent and procedure categories rather than exact CPT code matching
- **Flexible Bundle Detection**: Identifies common procedure bundles (like arthrograms, EMGs, etc.) even when components vary
- **Partial Match Support**: Handles cases where some components of a procedure may be missing while still validating the core service
- **Body Part & Modality Focus**: Prioritizes matching the correct body part and service type over exact CPT codes
- **Provider-Specific Rules**: Supports provider-specific coding patterns and preferences
- **Enhanced Reporting**: Generates detailed reports to simplify the resolution of validation issues

## System Architecture

```
BRsystem/
├── config/
│   ├── settings.py               # System configuration and constants
│   ├── procedure_bundles.json    # Bundle definitions with core/optional codes
│   ├── clinical_equivalents.json # Clinically equivalent code mappings
│   └── provider_rules.json       # Provider-specific validation rules
├── core/
│   ├── models/
│   │   ├── validation.py         # Validation data models
│   │   ├── procedures.py         # Procedure representation models
│   │   └── clinical_intent.py    # Clinical intent classification models
│   ├── services/
│   │   ├── database.py           # Database operations
│   │   ├── normalizer.py         # Input data normalization
│   │   └── reporter.py           # Enhanced reporting service
│   └── validators/
│       ├── bundle_validator.py   # Flexible bundle validation
│       ├── intent_validator.py   # Clinical intent validation
│       ├── modifier_validator.py # Modifier validation
│       ├── rate_validator.py     # Rate validation
│       └── units_validator.py    # Units validation
├── utils/
│   ├── helpers.py                # Utility functions
│   └── code_mapper.py            # CPT code mapping utilities
└── main_v2.py                    # Main execution point
```

## Installation

### Prerequisites

- Python 3.7 or higher
- SQLite database with required schema (same as v1 system)
- Dependencies listed in requirements.txt

### Setup

1. Ensure your directories are configured properly in settings.py:
   ```python
   JSON_PATH = Path("path/to/input/json/files")
   DB_PATH = Path("path/to/reference/database.db")
   LOG_PATH = Path("path/to/validation/logs")
   ```

2. Install dependencies (preferably in a virtual environment):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Usage

Run the validation system:
```bash
python main_v2.py
```

The system will:
1. Load and process all JSON files in the configured directory
2. Perform enhanced validation with clinical intent recognition and bundle detection
3. Generate validation logs with detailed information about each validation step
4. Save results to the specified log directory

## Bundle Configuration

Procedure bundles are defined in `config/procedure_bundles.json` with the following structure:

```json
{
  "MR Arthrogram Shoulder": {
    "bundle_type": "arthrogram",
    "body_part": "shoulder",
    "modality": "MR",
    "description": "MRI arthrogram of the shoulder with injection",
    "core_codes": ["73222", "23350"],
    "optional_codes": ["77002"]
  }
}
```

- **bundle_type**: Category of the procedure (arthrogram, therapeutic_injection, etc.)
- **body_part**: Body part involved (shoulder, knee, etc.)
- **modality**: Type of imaging or service (MR, CT, XR, etc.)
- **core_codes**: CPT codes that must be present for the bundle to be valid
- **optional_codes**: CPT codes that may or may not be present

## Clinical Equivalence

Clinical equivalents are defined in `config/clinical_equivalents.json` to specify CPT codes that can be considered equivalent for validation purposes:

```json
{
  "equivalent_groups": [
    {
      "name": "MRI Brain",
      "codes": ["70551", "70552", "70553"],
      "description": "MRI of the brain with various contrast options"
    }
  ]
}
```

## Validation Flow

1. **Bundle Detection**: Identify potential bundles in both order and HCFA data
2. **Clinical Intent Matching**: Determine if the clinical intent matches
3. **Modifier Validation**: Check modifier usage
4. **Units Validation**: Verify unit counts with bundle-specific rules
5. **Line Item Validation**: Compare line items between HCFA and reference data
6. **Rate Validation**: Verify rates based on provider and network status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with detailed description
4. Ensure all tests pass

## License

[Insert your license information here]
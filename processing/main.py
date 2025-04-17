from core.services.arthrogram_service import ArthrogramService
from core.services.validator import Validator
from core.services.reporter import Reporter
from core.settings import settings

class BillReviewApplication:
    """Main application class for bill review processing."""
    
    def __init__(self):
        self.validators = [
            Validator("CPT Validator", self.validate_cpt),
            Validator("Modifier Validator", self.validate_modifiers),
            Validator("Units Validator", self.validate_units),
            Validator("Place of Service Validator", self.validate_pos),
            Validator("Date Validator", self.validate_dates)
        ]
        self.arthrogram_service = ArthrogramService()
    
    def run(self):
        """Run the bill review process."""
        try:
            # First, process arthrograms
            print("Processing arthrograms...")
            arthrogram_results = self.arthrogram_service.process_arthrogram_files()
            
            # Get remaining files from staging
            staging_path = settings.STAGING_PATH
            json_files = list(staging_path.glob('*.json'))
            
            # Process each file
            for file_path in json_files:
                try:
                    with open(file_path, 'r') as f:
                        raw_data = json.load(f)
                    
                    # Run validators
                    for validator in self.validators:
                        validator.validate(raw_data)
                    
                    # Generate report
                    reporter = Reporter(raw_data)
                    reporter.generate_report()
                    
                except Exception as e:
                    print(f"Error processing {file_path.name}: {str(e)}")
                    continue
            
            print("\nProcessing complete!")
            print(f"Arthrogram Results: {arthrogram_results}")
            
        except Exception as e:
            print(f"Error in main process: {str(e)}")
            raise
    
    def validate_cpt(self, data: dict) -> bool:
        """Validate CPT codes."""
        # Implementation here
        pass
    
    def validate_modifiers(self, data: dict) -> bool:
        """Validate modifiers."""
        # Implementation here
        pass
    
    def validate_units(self, data: dict) -> bool:
        """Validate units."""
        # Implementation here
        pass
    
    def validate_pos(self, data: dict) -> bool:
        """Validate place of service."""
        # Implementation here
        pass
    
    def validate_dates(self, data: dict) -> bool:
        """Validate dates."""
        # Implementation here
        pass

if __name__ == "__main__":
    app = BillReviewApplication()
    app.run() 
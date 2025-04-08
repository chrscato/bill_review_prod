import os
from pathlib import Path
from docx2pdf import convert
import time
from datetime import datetime

# Constants
DOCS_FOLDER = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\EOBR\20250407_004640\docs"
PDFS_FOLDER = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\EOBR\20250407_004640\pdf"

def find_missing_pdfs():
    """Find DOCX files that don't have corresponding PDFs."""
    # Get all DOCX files
    docx_files = {f.stem: f for f in Path(DOCS_FOLDER).glob('*.docx')}
    # Get all PDF files
    pdf_files = {f.stem: f for f in Path(PDFS_FOLDER).glob('*.pdf')}
    
    # Find DOCX files without corresponding PDFs
    missing_pdfs = {name: path for name, path in docx_files.items() 
                   if name not in pdf_files}
    
    return missing_pdfs

def convert_with_retry(docx_path, pdf_path, max_retries=3, delay=2):
    """Attempt to convert DOCX to PDF with retries."""
    for attempt in range(max_retries):
        try:
            convert(docx_path, pdf_path)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed for {docx_path.name}. Error: {str(e)}")
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"All {max_retries} attempts failed for {docx_path.name}")
                print(f"Final error: {str(e)}")
                return False

def process_missing_pdfs():
    """Process only the DOCX files that don't have corresponding PDFs."""
    # Create log file
    log_file = Path(PDFS_FOLDER) / f"conversion_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Find missing PDFs
    missing_pdfs = find_missing_pdfs()
    
    if not missing_pdfs:
        print("No missing PDFs found. All DOCX files have corresponding PDFs.")
        return
    
    print(f"Found {len(missing_pdfs)} DOCX files without corresponding PDFs.")
    
    # Process each missing PDF
    successful = []
    failed = []
    
    for name, docx_path in missing_pdfs.items():
        pdf_path = Path(PDFS_FOLDER) / f"{name}.pdf"
        print(f"\nProcessing: {docx_path.name}")
        
        if convert_with_retry(docx_path, pdf_path):
            successful.append(docx_path.name)
            print(f"Successfully converted: {docx_path.name}")
        else:
            failed.append(docx_path.name)
    
    # Write results to log file
    with open(log_file, 'w') as f:
        f.write(f"Conversion Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total files to process: {len(missing_pdfs)}\n")
        f.write(f"Successfully converted: {len(successful)}\n")
        f.write(f"Failed conversions: {len(failed)}\n\n")
        
        if successful:
            f.write("\nSuccessfully converted files:\n")
            for file in successful:
                f.write(f"- {file}\n")
        
        if failed:
            f.write("\nFailed conversions:\n")
            for file in failed:
                f.write(f"- {file}\n")
    
    # Print summary
    print("\n=== Conversion Summary ===")
    print(f"Total files processed: {len(missing_pdfs)}")
    print(f"Successfully converted: {len(successful)}")
    print(f"Failed conversions: {len(failed)}")
    print(f"\nDetailed log written to: {log_file}")

if __name__ == "__main__":
    print("Starting PDF conversion process...")
    process_missing_pdfs()
import sys
from PyPDF2 import PdfReader

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python count_pdfs.py <pdf_file>")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    try:
        reader = PdfReader(pdf_file)
        num_pages = len(reader.pages)
        print(f"PDF '{pdf_file}' has {num_pages} pages.")
    except Exception as e:
        print(f"Error reading PDF '{pdf_file}': {e}")
        sys.exit(1)

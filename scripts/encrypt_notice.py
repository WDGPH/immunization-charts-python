import json
import sys
from pathlib import Path
from utils import encrypt_pdf, convert_date

def encrypt_notice(json_path: str, pdf_path: str, language: str) -> None:
    """
    Encrypt a PDF notice using client data from JSON file.
    
    Args:
        json_path: Path to JSON file containing client data
        pdf_path: Path to PDF file to encrypt
        language: Language of the notice ('english' or 'french')
    """
    json_path = Path(json_path)
    pdf_path = Path(pdf_path)

    if not json_path.exists() or not pdf_path.exists():
        return

    data = json.loads(json_path.read_text())
    if not data:
        return

    first_key = next(iter(data))
    record = data[first_key]
    client_id = record.get("client_id", first_key)

    dob_iso = record.get("date_of_birth_iso")
    if not dob_iso:
        dob_display = record.get("date_of_birth")
        if not dob_display:
            return
        # Convert display date to ISO format using language parameter
        dob_iso = convert_date(dob_display, to_format='iso', 
                             lang='fr' if language == 'french' else 'en')

    try:
        encrypt_pdf(str(pdf_path), str(client_id), dob_iso)
    except Exception as exc:
        print(f"WARNING: Encryption failed for {pdf_path.name}: {exc}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: encrypt_notice.py <json_path> <pdf_path> <language>")
        sys.exit(1)
    
    encrypt_notice(sys.argv[1], sys.argv[2], sys.argv[3])
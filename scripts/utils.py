import typst
import locale
from datetime import datetime
import pandas as pd
from typing import Optional

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - fallback for legacy environments
    from PyPDF2 import PdfReader, PdfWriter  # type: ignore

def convert_date(date_str: str, to_format: str = 'display', lang: str = 'en') -> Optional[str]:
    """
    Convert dates between ISO and localized display formats.
    
    Parameters:
        date_str (str | datetime | pd.Timestamp): Date string to convert
        to_format (str): Target format - 'iso' or 'display' (default: 'display')
        lang (str): Language code ('en', 'fr', etc.) (default: 'en')
    
    Returns:
        str: Formatted date string according to specified format
    
    Examples:
        convert_date('2025-05-08', 'display', 'en') -> 'May 8, 2025'
        convert_date('2025-05-08', 'display', 'fr') -> '8 mai 2025'
        convert_date('May 8, 2025', 'iso', 'en') -> '2025-05-08'
        convert_date('8 mai 2025', 'iso', 'fr') -> '2025-05-08'
    """
    if pd.isna(date_str):
        return None

    # Month mappings for fallback
    FRENCH_MONTHS = {
        1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
        5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
        9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
    }
    FRENCH_MONTHS_REV = {v: k for k, v in FRENCH_MONTHS.items()}
    
    ENGLISH_MONTHS = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
        5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
        9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    ENGLISH_MONTHS_REV = {v: k for k, v in ENGLISH_MONTHS.items()}

    try:
        # Convert input to datetime object
        if isinstance(date_str, (pd.Timestamp, datetime)):
            date_obj = date_str
        elif isinstance(date_str, str):
            if '-' in date_str:  # ISO format
                date_obj = datetime.strptime(date_str.strip(), "%Y-%m-%d")
            else:  # Localized format
                try:
                    if lang == 'fr':
                        day, month, year = date_str.split()
                        month_num = FRENCH_MONTHS_REV.get(month.lower())
                        if not month_num:
                            raise ValueError(f"Invalid French month: {month}")
                        date_obj = datetime(int(year), month_num, int(day))
                    else:
                        month, rest = date_str.split(maxsplit=1)
                        day, year = rest.rstrip(',').split(',')
                        month_num = ENGLISH_MONTHS_REV.get(month.strip())
                        if not month_num:
                            raise ValueError(f"Invalid English month: {month}")
                        date_obj = datetime(int(year), month_num, int(day.strip()))
                except (ValueError, KeyError) as e:
                    raise ValueError(f"Unable to parse date string: {date_str}") from e
        else:
            raise ValueError(f"Unsupported date type: {type(date_str)}")

        # Convert to target format
        if to_format == 'iso':
            return date_obj.strftime("%Y-%m-%d")
        else:  # display format
            if lang == 'fr':
                month_name = FRENCH_MONTHS[date_obj.month]
                return f"{date_obj.day} {month_name} {date_obj.year}"
            else:
                month_name = ENGLISH_MONTHS[date_obj.month]
                return f"{month_name} {date_obj.day}, {date_obj.year}"

    except Exception as e:
        raise ValueError(f"Date conversion failed: {str(e)}") from e


def over_16_check(date_of_birth, delivery_date):
    """
    Check if the age is over 16 years.

    Parameters:
        date_of_birth (str): Date of birth in the format "YYYY-MM-DD".
        delivery_date (str): Date of visit in the format "YYYY-MM-DD".

    Returns:
        bool: True if age is over 16 years, False otherwise.
    
    Example:
        over_16_check("2009-09-08", "2025-05-08") -> False
    """

    birth_datetime = datetime.strptime(date_of_birth, "%Y-%m-%d")
    delivery_datetime = datetime.strptime(delivery_date, "%Y-%m-%d")

    age = delivery_datetime.year - birth_datetime.year

    # Adjust if birthday hasn't occurred yet in the DOV month
    if (delivery_datetime.month < birth_datetime.month) or \
       (delivery_datetime.month == birth_datetime.month and delivery_datetime.day < birth_datetime.day):
        age -= 1

    return age >= 16

def calculate_age(DOB, DOV):
    DOB_datetime = datetime.strptime(DOB, "%Y-%m-%d")

    if DOV[0].isdigit():
        DOV_datetime = datetime.strptime(DOV, "%Y-%m-%d")
    else:
        DOV_datetime = datetime.strptime(DOV, "%b %d, %Y")

    years = DOV_datetime.year - DOB_datetime.year
    months = DOV_datetime.month - DOB_datetime.month

    if DOV_datetime.day < DOB_datetime.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    return f"{years}Y {months}M"

def compile_typst(immunization_record, outpath):

    typst.compile(immunization_record, output = outpath)

def build_pdf_password(oen_partial: str, dob: str) -> str:
    """
    Construct the password for PDF access by combining the client identifier
    with the date of birth (YYYYMMDD).
    """
    dob_digits = dob.replace("-", "")
    return f"{oen_partial}{dob_digits}"


def encrypt_pdf(file_path: str, oen_partial: str, dob: str) -> str:
    """
    Encrypt a PDF with a password derived from the client identifier and DOB.

    Returns the path to the encrypted PDF (<file>_encrypted.pdf).
    """
    password = build_pdf_password(str(oen_partial), str(dob))
    reader = PdfReader(file_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    if reader.metadata:
        writer.add_metadata(reader.metadata)

    writer.encrypt(user_password=password, owner_password=password)

    encrypted_file_path = file_path.replace(".pdf", "_encrypted.pdf")
    with open(encrypted_file_path, "wb") as f:
        writer.write(f)

    return encrypted_file_path


def decrypt_pdf(encrypted_file_path: str, oen_partial: str, dob: str) -> str:
    """
    Decrypt a password-protected PDF generated by encrypt_pdf and write an
    unencrypted copy alongside it (for internal workflows/tests).
    """
    password = build_pdf_password(str(oen_partial), str(dob))
    reader = PdfReader(encrypted_file_path)
    if reader.is_encrypted:
        if reader.decrypt(password) == 0:
            raise ValueError("Failed to decrypt PDF with derived password.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    if reader.metadata:
        writer.add_metadata(reader.metadata)

    decrypted_file_path = encrypted_file_path.replace("_encrypted.pdf", "_decrypted.pdf")
    with open(decrypted_file_path, "wb") as f:
        writer.write(f)

    return decrypted_file_path

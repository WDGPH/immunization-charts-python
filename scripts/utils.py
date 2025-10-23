from __future__ import annotations

from datetime import datetime
from pathlib import Path
from string import Formatter
from typing import Optional

import pandas as pd
import typst
import yaml
from pypdf import PdfReader, PdfWriter

FRENCH_MONTHS = {
    1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
    5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
    9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
}
FRENCH_MONTHS_REV = {v.lower(): k for k, v in FRENCH_MONTHS.items()}

ENGLISH_MONTHS = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
}
ENGLISH_MONTHS_REV = {v.lower(): k for k, v in ENGLISH_MONTHS.items()}

# Configuration paths
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

_encryption_config = None
_formatter = Formatter()

def _load_encryption_config():
    """Load encryption configuration from unified parameters.yaml file."""
    global _encryption_config
    if _encryption_config is None:
        try:
            parameters_path = CONFIG_DIR / "parameters.yaml"
            if parameters_path.exists():
                with open(parameters_path) as f:
                    params = yaml.safe_load(f) or {}
                    _encryption_config = params.get("encryption", {})
            else:
                _encryption_config = {}
        except Exception:
            _encryption_config = {}
    return _encryption_config


def get_encryption_config():
    """Get the encryption configuration from parameters.yaml."""
    return _load_encryption_config()


def convert_date_string_french(date_str):
    """
    Convert a date string from "YYYY-MM-DD" to "8 mai 2025" (in French), without using locale.
    """
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day = date_obj.day
    month = FRENCH_MONTHS[date_obj.month]
    year = date_obj.year

    return f"{day} {month} {year}"


def convert_date_string(date_str):
    """
    Convert a date (string or Timestamp) from 'YYYY-MM-DD' to 'Mon DD, YYYY'.
    
    Parameters:
        date_str (str | datetime | pd.Timestamp): 
            Date string in 'YYYY-MM-DD' format or datetime-like object.
    
    Returns:
        str: Date in the format 'Mon DD, YYYY'.
    """
    if pd.isna(date_str):
        return None
    
    # If it's already a datetime or Timestamp
    if isinstance(date_str, (pd.Timestamp, datetime)):
        return date_str.strftime("%b %d, %Y")

    # Otherwise assume string input
    try:
        date_obj = datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
        return date_obj.strftime("%b %d, %Y")
    except ValueError:
        raise ValueError(f"Unrecognized date format: {date_str}")


def convert_date_iso(date_str):
    """
    Convert a date string from "Mon DD, YYYY" format to "YYYY-MM-DD".

    Parameters:
        date_str (str): Date in the format "Mon DD, YYYY" (e.g., "May 8, 2025").

    Returns:
        str: Date in the format "YYYY-MM-DD".

    Example:
        convert_date("May 8, 2025") -> "2025-05-08"
    """
    date_obj = datetime.strptime(date_str, "%b %d, %Y")
    return date_obj.strftime("%Y-%m-%d")


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
                        month_num = ENGLISH_MONTHS_REV.get(month.strip().lower())
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



def generate_qr_code(
    data: str,
    output_dir: Path,
    *,
    filename: Optional[str] = None,
) -> Path:
    """Generate a monochrome QR code PNG and return the saved path.

    Parameters
    ----------
    data:
        The string payload to encode inside the QR code.
    output_dir:
        Directory where the QR image should be saved. The directory is created
        if it does not already exist.
    filename:
        Optional file name (including extension) for the resulting PNG. When
        omitted a deterministic name derived from the payload hash is used.

    Returns
    -------
    Path
        Absolute path to the generated PNG file.
    """

    try:  # Import lazily so non-QR callers avoid mandatory installs.
        import qrcode
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - exercised in optional envs
        raise RuntimeError(
            "QR code generation requires the 'qrcode' and 'pillow' packages. "
            "Install them via 'uv sync' before enabling QR payloads."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    pil_image = getattr(image, "get_image", lambda: image)()

    # Convert to 1-bit black/white without dithering to keep crisp edges.
    pil_bitmap = pil_image.convert("1", dither=Image.NONE)

    if not filename:
        import hashlib

        digest = hashlib.sha1(data.encode("utf-8")).hexdigest()[:12]
        filename = f"qr_{digest}.png"

    target_path = output_dir / filename
    pil_bitmap.save(target_path, format="PNG", bits=1)
    return target_path


def compile_typst(immunization_record, outpath):
    typst.compile(immunization_record, output = outpath)

def build_pdf_password(oen_partial: str, dob: str) -> str:
    """
    Construct the password for PDF access based on encryption config template.
    
    Supports template-based password generation with placeholders such as:
    - {client_id}: Client identifier
    - {date_of_birth_iso}: Date in YYYY-MM-DD format
    - {date_of_birth_iso_compact}: Date in YYYYMMDD format
    
    By default, uses "{date_of_birth_iso_compact}" (YYYYMMDD format).
    Can be customized via config/parameters.yaml encryption.password.template.
    
    Args:
        oen_partial: Client identifier
        dob: Date of birth in YYYY-MM-DD format
        
    Returns:
        Password string for PDF encryption
    """
    config = get_encryption_config()
    password_config = config.get("password", {})
    
    # Get the template (default to compact DOB format if not specified)
    template = password_config.get("template", "{date_of_birth_iso_compact}")
    
    # Build the context with available placeholders
    context = {
        "client_id": str(oen_partial),
        "date_of_birth_iso": dob,
        "date_of_birth_iso_compact": dob.replace("-", ""),
    }
    
    # Render the template
    try:
        password = template.format(**context)
    except KeyError as e:
        raise ValueError(f"Unknown placeholder in password template: {e}")
    
    return password


def encrypt_pdf(file_path: str, oen_partial: str, dob: str) -> str:
    """
    Encrypt a PDF with a password derived from the client identifier and DOB.

    Returns the path to the encrypted PDF (<file>_encrypted.pdf).
    """
    password = build_pdf_password(str(oen_partial), str(dob))
    reader = PdfReader(file_path, strict=False)
    writer = PdfWriter()

    copied = False

    # Prefer optimized cloning/append operations when available to avoid page-by-page copies.
    append = getattr(writer, "append", None)
    if append:
        try:
            append(reader)
            copied = True
        except TypeError:
            try:
                append(file_path)
                copied = True
            except Exception:
                copied = False
        except Exception:
            copied = False

    if not copied:
        for attr in ("clone_reader_document_root", "cloneReaderDocumentRoot"):
            clone_fn = getattr(writer, attr, None)
            if clone_fn:
                try:
                    clone_fn(reader)
                    copied = True
                    break
                except Exception:
                    copied = False

    if not copied:
        append_from_reader = getattr(writer, "appendPagesFromReader", None)
        if append_from_reader:
            try:
                append_from_reader(reader)
                copied = True
            except Exception:
                copied = False

    if not copied:
        for page in reader.pages:
            writer.add_page(page)

    if reader.metadata:
        writer.add_metadata(reader.metadata)

    writer.encrypt(user_password=password, owner_password=password)

    src = Path(file_path)
    encrypted_path = src.with_name(f"{src.stem}_encrypted{src.suffix}")
    with open(encrypted_path, "wb") as f:
        writer.write(f)

    return str(encrypted_path)


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

    enc = Path(encrypted_file_path)
    stem = enc.stem
    if stem.endswith("_encrypted"):
        base = stem[:-len("_encrypted")]
    else:
        base = stem
    decrypted_path = enc.with_name(f"{base}_decrypted{enc.suffix}")
    with open(decrypted_path, "wb") as f:
        writer.write(f)

    return str(decrypted_path)

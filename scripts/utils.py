import typst
from datetime import datetime
import pandas as pd
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

def convert_date_string_french(date_str):
    """
    Convert a date string from "YYYY-MM-DD" to "8 mai 2025" (in French), without using locale.
    """
    MONTHS_FR = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day = date_obj.day
    month = MONTHS_FR[date_obj.month - 1]
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

def convert_date_french_to_iso(date_str: str) -> str:
    """
    Convert a French-formatted date string like "8 mai 2025" to "2025-05-08".
    """
    months = {
        "janvier": 1,
        "février": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "août": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "décembre": 12,
    }

    parts = date_str.strip().split()
    if len(parts) != 3:
        raise ValueError(f"Unexpected French date format: {date_str}")

    day = int(parts[0])
    month = months.get(parts[1].lower())
    if month is None:
        raise ValueError(f"Unknown French month: {parts[1]}")
    year = int(parts[2])
    return f"{year:04d}-{month:02d}-{day:02d}"

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

# Function to derive a key from client details

def derive_key(oen_partial: str, dob: str) -> bytes:
    # Combine OEN and DOB to create a unique key
    key_material = f"{oen_partial}{dob}".encode('utf-8')
    # Use SHA-256 to hash the key material
    return hashlib.sha256(key_material).digest()

# Function to encrypt PDF

def encrypt_pdf(file_path: str, oen_partial: str, dob: str) -> str:
    key = derive_key(oen_partial, dob)
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv

    with open(file_path, 'rb') as f:
        plaintext = f.read()

    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))

    # Save the encrypted PDF with IV prepended
    encrypted_file_path = file_path.replace('.pdf', '_encrypted.pdf')
    with open(encrypted_file_path, 'wb') as f:
        f.write(iv + ciphertext)

    return encrypted_file_path

# Function to decrypt PDF

def decrypt_pdf(encrypted_file_path: str, oen_partial: str, dob: str) -> str:
    key = derive_key(oen_partial, dob)

    with open(encrypted_file_path, 'rb') as f:
        iv = f.read(16)  # Read the IV from the beginning
        ciphertext = f.read()

    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)

    # Save the decrypted PDF
    decrypted_file_path = encrypted_file_path.replace('_encrypted.pdf', '_decrypted.pdf')
    with open(decrypted_file_path, 'wb') as f:
        f.write(plaintext)

    return decrypted_file_path

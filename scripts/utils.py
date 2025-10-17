import typst
from datetime import datetime
import pandas as pd
import qrcode
import base64
from io import BytesIO
from PIL import Image
import os

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



def generate_qr_code(data: str, client_id: str = None) -> str:
    """
    Generate a 1-bit black and white QR code and save it as a PNG file.
    
    Args:
        data (str): Data to encode in QR code
        client_id (str): Client ID for unique filename
        
    Returns:
        str: Path to the generated QR code image file
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create QR image
    img = qr.make_image(fill_color="black", back_color="white")

    
    try:
        pil_img = img.get_image()  # qrcode.image.pil.PilImage
    except AttributeError:
        pil_img = img

    # Convert to 1-bit B/W without dithering to keep sharp edges
    pil_img = pil_img.convert('1', dither=Image.NONE)

    # File path setup
    os.makedirs("../output/qr_codes", exist_ok=True)
    filename = f"qr_{client_id}.png" if client_id else "qr_code.png"
    save_path = os.path.join("../output/qr_codes", filename)

    # Save as 1-bit PNG
    pil_img.save(save_path, format='PNG', bits=1)

    # Return path relative to the Typst .typ files in ../output/json_*/
    return f"../qr_codes/{filename}"


def compile_typst(immunization_record, outpath):
    typst.compile(immunization_record, output = outpath)

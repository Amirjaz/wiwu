"""Cleaning what Iranian buyers type: Persian/Arabic digits and letters, phones, postal codes, Sheba."""
import re

_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
_LETTERS = str.maketrans({'ي': 'ی', 'ى': 'ی', 'ك': 'ک', 'ة': 'ه', '‏': None, '‎': None})
_TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def latin_digits(text):
    return str(text or '').translate(_DIGITS)


def fa_digits(value):
    return str(value).translate(_TO_FA)


def clean_text(text, limit=None):
    """Trimmed, Arabic letters → Persian, runs of spaces collapsed."""
    text = re.sub(r'[ \t]+', ' ', str(text or '').translate(_LETTERS)).strip()
    return text[:limit] if limit else text


def phone(text):
    """'09xxxxxxxxx' for an Iranian mobile (also from +98 / 0098 / 9xx… / Persian digits), else None."""
    digits = re.sub(r'\D', '', latin_digits(text))
    if digits.startswith('0098'):
        digits = digits[4:]
    elif digits.startswith('98') and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith('9'):
        digits = '0' + digits
    return digits if re.fullmatch(r'09\d{9}', digits) else None


def postal_code(text):
    """10 digits, else None. Iranian postal codes never start with 0 or 2 and have no 0 in the first five."""
    digits = re.sub(r'\D', '', latin_digits(text))
    if not re.fullmatch(r'\d{10}', digits) or digits[0] in '02' or '0' in digits[:5]:
        return None
    return digits


def sheba(text):
    """'IR' + 24 digits with a valid ISO 13616 check (mod 97), else None."""
    raw = re.sub(r'[\s-]', '', latin_digits(text)).upper()
    if raw.startswith('IR'):
        raw = raw[2:]
    if not re.fullmatch(r'\d{24}', raw):
        return None
    # Move country code + check digits to the end; I=18, R=27.
    check = int(raw[2:] + '1827' + raw[:2])
    return 'IR' + raw if check % 97 == 1 else None


def card_number(text):
    digits = re.sub(r'\D', '', latin_digits(text))
    if not re.fullmatch(r'\d{16}', digits):
        return None
    # Luhn: every Shetab card passes it.
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return digits if total % 10 == 0 else None


def toman(rial):
    """'۱۰٬۰۰۰٬۳۶۰' for 100003600 rials (no unit)."""
    return fa_digits(f'{int(rial) // 10:,}').replace(',', '٬')

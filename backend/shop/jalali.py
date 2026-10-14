"""Solar Hijri (Persian) calendar dates, as buyers and staff read them (copied from Contech)."""
from datetime import date, timedelta

_MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


def to_jalali(day):
    """(year, month, day) in the Persian calendar for a Gregorian date (the 33-year arithmetic cycle)."""
    gy, gm, gd = day.year, day.month, day.day
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + _MONTH_START[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jy, 1 + days // 31, 1 + days % 31
    return jy, 7 + (days - 186) // 30, 1 + (days - 186) % 30


def from_jalali(year, month, day):
    """The Gregorian date of a Persian one; ValueError if there's no such day (e.g. 1405-12-30)."""
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError('no such day')
    nowruz = date(year + 621, 3, 19)
    while to_jalali(nowruz) != (year, 1, 1):
        nowruz += timedelta(days=1)
    result = nowruz + timedelta(days=(month - 1) * 31 if month <= 7 else 186 + (month - 7) * 30) + timedelta(days=day - 1)
    if to_jalali(result) != (year, month, day):
        raise ValueError('no such day')
    return result


def parse(text):
    """A Gregorian date from Persian 'YYYY-MM-DD' (or with slashes, or Persian digits); ValueError if not one."""
    text = str(text).strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩/', '01234567890123456789-'))
    parts = text.split('-')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError('not a date')
    return from_jalali(*map(int, parts))


def iso(day):
    """'YYYY-MM-DD' in the Persian calendar."""
    year, month, d = to_jalali(day)
    return f'{year:04d}-{month:02d}-{d:02d}'


MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']


def long(moment):
    """'۲۲ مهر ۱۴۰۵، ۱۸:۳۵' in Tehran time, for SMS and pages."""
    from django.utils import timezone

    from .persian import fa_digits

    local = timezone.localtime(moment)
    year, month, d = to_jalali(local.date())
    return fa_digits(f'{d} {MONTHS[month - 1]} {year}، {local:%H:%M}')


def day_label(day):
    """'۲۹ مهر ۱۴۰۵' for a date."""
    from .persian import fa_digits

    year, month, d = to_jalali(day)
    return fa_digits(f'{d} {MONTHS[month - 1]} {year}')

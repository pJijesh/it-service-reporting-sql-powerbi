"""Time zone rules, holiday lists and support-hours windows.

Only the standard library is used. Daylight saving rules are written out by hand
for the four zones in the example, so the generator does not need the system time
zone database (which is missing on some platforms). The test suite compares these
rules with ``zoneinfo`` whenever the time zone database is available.

All datetimes in this module are naive and mean UTC unless a name says "local".
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

MINUTE = timedelta(minutes=1)


def last_sunday(year: int, month: int) -> date:
    """Return the date of the last Sunday of the month."""
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth given weekday (Monday is 0) of a month, counting from 1."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _eu_dst_active(utc: datetime) -> bool:
    """European Union rule: summer time runs from 01:00 UTC on the last Sunday of
    March to 01:00 UTC on the last Sunday of October."""
    start = datetime.combine(last_sunday(utc.year, 3), time(1, 0))
    end = datetime.combine(last_sunday(utc.year, 10), time(1, 0))
    return start <= utc < end


def _us_dst_active(utc: datetime) -> bool:
    """United States rule: daylight time runs from 02:00 local standard time on the
    second Sunday of March to 02:00 local daylight time on the first Sunday of
    November. For US Central time that is 08:00 UTC and 07:00 UTC respectively."""
    start = datetime.combine(nth_weekday(utc.year, 3, 6, 2), time(8, 0))
    end = datetime.combine(nth_weekday(utc.year, 11, 6, 1), time(7, 0))
    return start <= utc < end


@dataclass(frozen=True)
class Zone:
    name: str
    std_offset_minutes: int
    dst_rule: object  # callable(datetime) -> bool, or None for no daylight saving

    def offset_minutes(self, utc: datetime) -> int:
        if self.dst_rule is not None and self.dst_rule(utc):
            return self.std_offset_minutes + 60
        return self.std_offset_minutes

    def to_local(self, utc: datetime) -> datetime:
        return utc + timedelta(minutes=self.offset_minutes(utc))

    def to_utc(self, local: datetime) -> datetime:
        """Convert local wall-clock time to UTC.

        Correct for every time that is not inside the one-hour daylight saving
        transition on a Sunday morning. Support windows and ticket times used here
        avoid that hour, and the module documents the limit rather than hiding it.
        """
        if self.dst_rule is not None:
            candidate = local - timedelta(minutes=self.std_offset_minutes + 60)
            if self.dst_rule(candidate):
                return candidate
        return local - timedelta(minutes=self.std_offset_minutes)


ZONES = {
    "Europe/London": Zone("Europe/London", 0, _eu_dst_active),
    "Europe/Dublin": Zone("Europe/Dublin", 0, _eu_dst_active),
    "Europe/Berlin": Zone("Europe/Berlin", 60, _eu_dst_active),
    "America/Chicago": Zone("America/Chicago", -360, _us_dst_active),
    "Asia/Singapore": Zone("Asia/Singapore", 480, None),
}

# England and Wales bank holidays, checked against the GOV.UK bank holidays
# feed (https://www.gov.uk/bank-holidays.json) on 2026-11-11.
EMEA_HOLIDAYS = [
    date(2024, 12, 25), date(2024, 12, 26), date(2025, 1, 1), date(2025, 4, 18),
    date(2025, 4, 21), date(2025, 5, 5), date(2025, 5, 26), date(2025, 8, 25),
    date(2025, 12, 25), date(2025, 12, 26),
]
# Illustrative, deliberately short lists. They are not complete public holiday
# calendars for the United States or Singapore.
AMER_HOLIDAYS = [
    date(2024, 12, 25), date(2025, 1, 1), date(2025, 5, 26), date(2025, 7, 4),
    date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25),
]
APAC_HOLIDAYS = [date(2024, 12, 25), date(2025, 1, 1), date(2025, 5, 1), date(2025, 12, 25)]


@dataclass(frozen=True)
class CalendarDef:
    code: str
    name: str
    zone: str
    open_local: str
    close_local: str
    holidays: tuple
    note: str


CALENDARS = {
    "EMEA": CalendarDef(
        "EMEA", "EMEA support hours", "Europe/London", "08:00", "18:00",
        tuple(EMEA_HOLIDAYS), "Monday to Friday, England and Wales bank holidays excluded"),
    "AMER": CalendarDef(
        "AMER", "Americas support hours", "America/Chicago", "08:00", "18:00",
        tuple(AMER_HOLIDAYS), "Monday to Friday, short illustrative holiday list"),
    "APAC": CalendarDef(
        "APAC", "Asia Pacific support hours", "Asia/Singapore", "08:00", "18:00",
        tuple(APAC_HOLIDAYS), "Monday to Friday, short illustrative holiday list"),
}


def _parse_hhmm(text: str) -> time:
    hour, minute = text.split(":")
    return time(int(hour), int(minute))


def build_windows(cal: CalendarDef, first_local: date, last_local: date):
    """Return sorted (open_utc, close_utc, local_date) tuples for each working day."""
    zone = ZONES[cal.zone]
    opens, closes = _parse_hhmm(cal.open_local), _parse_hhmm(cal.close_local)
    holidays = set(cal.holidays)
    out = []
    day = first_local
    while day <= last_local:
        if day.weekday() < 5 and day not in holidays:
            out.append((
                zone.to_utc(datetime.combine(day, opens)),
                zone.to_utc(datetime.combine(day, closes)),
                day,
            ))
        day += timedelta(days=1)
    return out


class SupportClock:
    """Adds support-hours minutes to a start time. ``windows`` may be None for a
    24 by 7 clock, which is plain elapsed time."""

    def __init__(self, windows):
        self.windows = windows
        self._closes = [w[1] for w in windows] if windows else None

    def add_minutes(self, start: datetime, minutes: int) -> datetime:
        if self.windows is None:
            return start + minutes * MINUTE
        i = bisect_right(self._closes, start)  # first window that closes after start
        remaining = minutes
        cursor = start
        while True:
            if i >= len(self.windows):
                raise ValueError("support windows exhausted; extend the calendar range")
            opens, closes, _ = self.windows[i]
            begin = max(opens, cursor)
            available = int((closes - begin) / MINUTE)
            if remaining <= available:
                return begin + remaining * MINUTE
            remaining -= available
            i += 1

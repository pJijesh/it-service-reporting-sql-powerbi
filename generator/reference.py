"""Reference data for the fictional group. Every name here is invented."""

from __future__ import annotations

GROUP_NAME = "Kelderwick Group (fictional)"

# company_id, company_name, sector
COMPANIES = [
    ("C01", "Fennick Packaging", "Packaging manufacture"),
    ("C02", "Quillon Foods", "Food distribution"),
    ("C03", "Marrowdene Engineering", "Precision engineering"),
    ("C04", "Pelham Rook Retail", "Specialist retail"),
]

# site_id, company_id, site_name, country, time_zone, support_calendar, headcount
SITES = [
    ("S01", "C01", "Leeds head office", "United Kingdom", "Europe/London", "EMEA", 420),
    ("S02", "C01", "Cork plant", "Ireland", "Europe/Dublin", "EMEA", 130),
    ("S03", "C02", "Bristol depot", "United Kingdom", "Europe/London", "EMEA", 260),
    ("S04", "C02", "Hamburg depot", "Germany", "Europe/Berlin", "EMEA", 140),
    ("S05", "C03", "Coventry works", "United Kingdom", "Europe/London", "EMEA", 310),
    ("S06", "C03", "Chicago office", "United States", "America/Chicago", "AMER", 120),
    ("S07", "C03", "Singapore office", "Singapore", "Asia/Singapore", "APAC", 90),
    ("S08", "C04", "Manchester head office", "United Kingdom", "Europe/London", "EMEA", 240),
    ("S09", "C04", "Norwich distribution centre", "United Kingdom", "Europe/London", "EMEA", 85),
]

# team_id, team_name, fte, description
TEAMS = [
    ("SD", "Service Desk", 4.0, "First line, triage and first contact resolution"),
    ("INF", "Infrastructure", 3.0, "Network, servers, email platform and telephony"),
    ("APP", "Application Support", 3.0, "Business applications, reporting and releases"),
    ("IAM", "Identity and Security", 2.0, "Accounts, access and security events"),
    ("FLD", "Field Services", 2.0, "Laptops, printers and on-site work"),
]

TICKET_TYPES = ["incident", "service_request", "problem", "change"]
TYPE_PREFIX = {"incident": "INC", "service_request": "REQ", "problem": "PRB", "change": "CHG"}

# Tickets per head per month for each type, before seasonal effects.
PER_HEAD_MONTHLY = {"incident": 0.17, "service_request": 0.115, "problem": 0.006, "change": 0.015}

# category, weight, resolver team, probability of first contact resolution (P3 and P4 only)
INCIDENT_CATEGORIES = [
    ("Password and access", 16, "IAM", 0.65),
    ("Email and collaboration", 11, "INF", 0.30),
    ("Laptop and desktop", 15, "FLD", 0.25),
    ("Printing and peripherals", 9, "FLD", 0.35),
    ("Network and Wi-Fi", 10, "INF", 0.10),
    ("Business application", 18, "APP", 0.08),
    ("Reporting and data", 5, "APP", 0.05),
    ("Telephony and meeting rooms", 6, "INF", 0.15),
    ("Server and hosting", 3, "INF", 0.0),
    ("Security event", 4, "IAM", 0.0),
    ("Software how-to", 3, "SD", 0.75),
]
REQUEST_CATEGORIES = [
    ("Access request", 25, "IAM", 0.35),
    ("Software install", 16, "SD", 0.55),
    ("New starter setup", 10, "FLD", 0.0),
    ("Leaver processing", 8, "IAM", 0.0),
    ("Hardware request", 14, "FLD", 0.05),
    ("Mailbox and group change", 10, "INF", 0.30),
    ("Report or data request", 10, "APP", 0.0),
    ("Information request", 7, "SD", 0.80),
]
PROBLEM_CATEGORIES = [
    ("Recurring network fault", 30, "INF", 0.0),
    ("Application defect", 35, "APP", 0.0),
    ("Hardware failure trend", 15, "FLD", 0.0),
    ("Authentication failures", 20, "IAM", 0.0),
]
CHANGE_CATEGORIES = [
    ("Patching and maintenance", 35, "INF", 0.0),
    ("Application release", 30, "APP", 0.0),
    ("Access policy change", 10, "IAM", 0.0),
    ("Device refresh", 15, "FLD", 0.0),
    ("Network change", 10, "INF", 0.0),
]
CATEGORIES = {
    "incident": INCIDENT_CATEGORIES,
    "service_request": REQUEST_CATEGORIES,
    "problem": PROBLEM_CATEGORIES,
    "change": CHANGE_CATEGORIES,
}

# (impact, urgency) -> weight, per ticket type. Impact 1 is widest, urgency 1 is most urgent.
_INCIDENT_JOINT = {
    (1, 1): 2, (1, 2): 4, (1, 3): 1,
    (2, 1): 4, (2, 2): 12, (2, 3): 9,
    (3, 1): 8, (3, 2): 17, (3, 3): 43,
}
_LOWER_JOINT = {  # no P1 cell: used for requests, problems and changes
    (1, 2): 3, (1, 3): 1, (2, 1): 3, (2, 2): 11, (2, 3): 12,
    (3, 1): 3, (3, 2): 18, (3, 3): 49,
}
IMPACT_URGENCY_WEIGHTS = {
    "incident": _INCIDENT_JOINT,
    "service_request": _LOWER_JOINT,
    "problem": _LOWER_JOINT,
    "change": _LOWER_JOINT,
}

# The priority matrix. Rows are impact, columns are urgency.
PRIORITY_MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}
IMPACT_LABELS = {1: "High: site wide or many users", 2: "Medium: a team or department", 3: "Low: one person"}
URGENCY_LABELS = {1: "High: work stopped, no workaround", 2: "Medium: work slowed, workaround exists", 3: "Low: minor or can wait"}
PRIORITY_NAMES = {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}

# ticket_type, priority, response target (minutes), resolution target (minutes), clock basis.
# Example targets for the data set. They are not a recommendation for any organisation.
SLA_TARGETS = [
    ("incident", "P1", 15, 240, "24X7"),
    ("incident", "P2", 30, 480, "SUPPORT_HOURS"),
    ("incident", "P3", 120, 1200, "SUPPORT_HOURS"),
    ("incident", "P4", 240, 2400, "SUPPORT_HOURS"),
    ("service_request", "P2", 60, 960, "SUPPORT_HOURS"),
    ("service_request", "P3", 240, 2400, "SUPPORT_HOURS"),
    ("service_request", "P4", 480, 4800, "SUPPORT_HOURS"),
]

# Median response and resolution work in clock minutes (support hours unless P1) and the
# log-normal spread, by (type, priority).
RESPONSE_MODEL = {
    ("incident", "P1"): (5, 0.7), ("incident", "P2"): (12, 0.7),
    ("incident", "P3"): (35, 0.7), ("incident", "P4"): (85, 0.7),
    ("service_request", "P2"): (20, 0.7), ("service_request", "P3"): (60, 0.7),
    ("service_request", "P4"): (150, 0.7),
    ("problem", "P2"): (360, 0.6), ("problem", "P3"): (480, 0.6), ("problem", "P4"): (600, 0.6),
    ("change", "P2"): (240, 0.6), ("change", "P3"): (360, 0.6), ("change", "P4"): (480, 0.6),
}
RESOLUTION_MODEL = {
    ("incident", "P1"): (55, 0.8), ("incident", "P2"): (140, 0.9),
    ("incident", "P3"): (250, 1.0), ("incident", "P4"): (450, 1.1),
    ("service_request", "P2"): (280, 0.8), ("service_request", "P3"): (650, 0.9),
    ("service_request", "P4"): (1400, 1.0),
    ("problem", "P2"): (7200, 0.8), ("problem", "P3"): (9000, 0.8), ("problem", "P4"): (11000, 0.8),
    ("change", "P2"): (1800, 0.6), ("change", "P3"): (3000, 0.6), ("change", "P4"): (3600, 0.6),
}
TEAM_SPEED = {"SD": 1.0, "IAM": 0.9, "INF": 1.1, "APP": 1.2, "FLD": 1.1}

-- Schema for the service reporting database (SQLite).
--
-- Conventions
--   * Every timestamp is stored as UTC text in the form 'YYYY-MM-DD HH:MM:SS'. This
--     form sorts correctly as text, and SQLite date functions read it directly.
--   * Flags are integers, 0 or 1. Missing values are NULL, never empty strings.
--   * The loader (sql/loader.py) checks the CSV files and gives readable errors
--     before anything reaches these tables. The CHECK and FOREIGN KEY clauses
--     are a second line of defence.

PRAGMA foreign_keys = ON;

CREATE TABLE extract_info (
    group_name         TEXT NOT NULL,
    period_start       TEXT NOT NULL,     -- first local day in the extract (date)
    period_end         TEXT NOT NULL,     -- last local day in the extract (date)
    as_of_utc          TEXT NOT NULL,     -- time the extract was taken (UTC); used for open tickets
    seed               INTEGER,
    generator_version  TEXT
);

CREATE TABLE companies (
    company_id    TEXT PRIMARY KEY,
    company_name  TEXT NOT NULL,
    sector        TEXT NOT NULL
);

CREATE TABLE support_calendars (
    calendar_code  TEXT PRIMARY KEY,
    calendar_name  TEXT NOT NULL,
    time_zone      TEXT NOT NULL,
    open_local     TEXT NOT NULL,         -- opening time, local clock, 'HH:MM'
    close_local    TEXT NOT NULL,
    note           TEXT
);

-- One row per working day per calendar, already converted to UTC. Holidays and
-- daylight saving changes are handled when the rows are made, so the views need
-- no time zone logic.
CREATE TABLE support_windows (
    calendar_code  TEXT NOT NULL REFERENCES support_calendars (calendar_code),
    local_date     TEXT NOT NULL,
    open_utc       TEXT NOT NULL,
    close_utc      TEXT NOT NULL,
    PRIMARY KEY (calendar_code, local_date),
    CHECK (open_utc < close_utc)
);
CREATE INDEX ix_support_windows_close ON support_windows (calendar_code, close_utc);

CREATE TABLE sites (
    site_id           TEXT PRIMARY KEY,
    company_id        TEXT NOT NULL REFERENCES companies (company_id),
    site_name         TEXT NOT NULL,
    country           TEXT NOT NULL,
    time_zone         TEXT NOT NULL,
    support_calendar  TEXT NOT NULL REFERENCES support_calendars (calendar_code),
    headcount         INTEGER NOT NULL CHECK (headcount >= 0)
);

CREATE TABLE teams (
    team_id      TEXT PRIMARY KEY,
    team_name    TEXT NOT NULL,
    fte          REAL NOT NULL CHECK (fte > 0),
    description  TEXT
);

CREATE TABLE priority_matrix (
    impact         INTEGER NOT NULL CHECK (impact BETWEEN 1 AND 3),
    urgency        INTEGER NOT NULL CHECK (urgency BETWEEN 1 AND 3),
    priority       TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    priority_name  TEXT NOT NULL,
    PRIMARY KEY (impact, urgency)
);

CREATE TABLE sla_targets (
    ticket_type                TEXT NOT NULL CHECK (ticket_type IN ('incident', 'service_request')),
    priority                   TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    response_target_minutes    INTEGER NOT NULL CHECK (response_target_minutes > 0),
    resolution_target_minutes  INTEGER NOT NULL CHECK (resolution_target_minutes > 0),
    clock_basis                TEXT NOT NULL CHECK (clock_basis IN ('24X7', 'SUPPORT_HOURS')),
    PRIMARY KEY (ticket_type, priority)
);

CREATE TABLE dim_date (
    date_key            INTEGER PRIMARY KEY,   -- yyyymmdd
    date                TEXT NOT NULL UNIQUE,  -- yyyy-mm-dd
    year                INTEGER NOT NULL,
    quarter             INTEGER NOT NULL,
    month_number        INTEGER NOT NULL,
    month_name          TEXT NOT NULL,
    year_month          TEXT NOT NULL,         -- yyyy-mm, sorts correctly as text
    month_start         TEXT NOT NULL,
    week_start          TEXT NOT NULL,         -- the Monday of the week
    day_of_week         INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),  -- 1 is Monday
    day_name            TEXT NOT NULL,
    is_weekend          INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    is_uk_bank_holiday  INTEGER NOT NULL CHECK (is_uk_bank_holiday IN (0, 1)),
    is_uk_working_day   INTEGER NOT NULL CHECK (is_uk_working_day IN (0, 1))
);

CREATE TABLE tickets (
    ticket_id               TEXT PRIMARY KEY,
    ticket_type             TEXT NOT NULL CHECK (ticket_type IN ('incident', 'service_request', 'problem', 'change')),
    company_id              TEXT NOT NULL REFERENCES companies (company_id),
    site_id                 TEXT NOT NULL REFERENCES sites (site_id),
    category                TEXT NOT NULL,
    priority                TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    impact                  INTEGER NOT NULL CHECK (impact BETWEEN 1 AND 3),
    urgency                 INTEGER NOT NULL CHECK (urgency BETWEEN 1 AND 3),
    opened_at               TEXT NOT NULL,
    first_response_at       TEXT,
    resolved_at             TEXT,
    closed_at               TEXT,
    reopened                INTEGER NOT NULL CHECK (reopened IN (0, 1)),
    resolved_first_contact  INTEGER NOT NULL CHECK (resolved_first_contact IN (0, 1)),
    assignee_team           TEXT NOT NULL REFERENCES teams (team_id),
    csat                    INTEGER CHECK (csat BETWEEN 1 AND 5)
);
CREATE INDEX ix_tickets_opened ON tickets (opened_at);
CREATE INDEX ix_tickets_resolved ON tickets (resolved_at);
CREATE INDEX ix_tickets_company ON tickets (company_id);

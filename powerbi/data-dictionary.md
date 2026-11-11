# Data dictionary

Every column in the CSV files in [`data/`](../data) and in the Power BI fact table
[`model/fact_ticket.csv`](../model/fact_ticket.csv). All data is synthetic. Timestamps are UTC and written as
`YYYY-MM-DDTHH:MM:SSZ` in the files. Blank means no value, never zero.

Tests check that every column in every file is listed here (`tests/test_powerbi_spec.py`).

## tickets.csv (source extract)

One row per ticket, as a ticketing tool would export it.

| Column | Type | Meaning |
| --- | --- | --- |
| `ticket_id` | text | Unique reference. Prefix shows the type: INC, REQ, PRB, CHG, then a six digit number. |
| `ticket_type` | text | `incident`, `service_request`, `problem` or `change`. |
| `company_id` | text | Company that raised the ticket. Foreign key to `companies.csv`. |
| `site_id` | text | Site of the requester. Foreign key to `sites.csv`. The site decides the time zone and support calendar. |
| `category` | text | What the ticket is about, for example "Business application". Set by the service desk. |
| `priority` | text | `P1` (critical) to `P4` (low). Worked out from impact and urgency using `priority_matrix.csv`. |
| `impact` | integer | 1 high (site wide or many users), 2 medium (a team), 3 low (one person). |
| `urgency` | integer | 1 high (work stopped, no workaround), 2 medium, 3 low. |
| `opened_at` | UTC timestamp | When the ticket was logged. Start of every clock. |
| `first_response_at` | UTC timestamp | When a person first responded. Blank if not yet. |
| `resolved_at` | UTC timestamp | When the first resolution was recorded. Blank if still open. Stops the resolution clock. |
| `closed_at` | UTC timestamp | When the ticket was closed after resolution. Blank if not yet closed. |
| `reopened` | 0 or 1 | 1 if the ticket was reopened after resolution. |
| `resolved_first_contact` | 0 or 1 | 1 if first-line staff resolved it at first contact with no hand-off. |
| `assignee_team` | text | Team that resolved or holds the ticket. Foreign key to `teams.csv`. |
| `csat` | integer 1 to 5 or blank | Survey score, 5 best. Blank when the requester did not respond. |

## Reference files

### companies.csv

| Column | Type | Meaning |
| --- | --- | --- |
| `company_id` | text | Key. |
| `company_name` | text | Invented company name. |
| `sector` | text | Invented sector label. |

### sites.csv

| Column | Type | Meaning |
| --- | --- | --- |
| `site_id` | text | Key. |
| `company_id` | text | Owning company. |
| `site_name` | text | Site name. |
| `country` | text | Country. |
| `time_zone` | text | IANA time zone name of the site. Used by the generator only. |
| `support_calendar` | text | Support hours calendar used for this site's service level clock. Foreign key to `support_calendars.csv`. |
| `headcount` | integer | Number of staff at the site. Used to compare demand between companies. |

### teams.csv

| Column | Type | Meaning |
| --- | --- | --- |
| `team_id` | text | Key. |
| `team_name` | text | Team name. |
| `fte` | decimal | Full-time equivalent staff in the team. Used for tickets per FTE. |
| `description` | text | What the team does. |

### sla_targets.csv

Example targets for the data set. They are not a recommendation.

| Column | Type | Meaning |
| --- | --- | --- |
| `ticket_type` | text | `incident` or `service_request`. Problems and changes have no service level. |
| `priority` | text | `P1` to `P4`. |
| `response_target_minutes` | integer | Time allowed to first response, in clock minutes. |
| `resolution_target_minutes` | integer | Time allowed to resolution, in clock minutes. |
| `clock_basis` | text | `24X7` counts elapsed minutes. `SUPPORT_HOURS` counts minutes inside the site's support window only. |

### priority_matrix.csv

| Column | Type | Meaning |
| --- | --- | --- |
| `impact` | integer | 1 to 3. |
| `urgency` | integer | 1 to 3. |
| `priority` | text | Resulting priority. |
| `priority_name` | text | Critical, High, Medium or Low. |

### support_calendars.csv

| Column | Type | Meaning |
| --- | --- | --- |
| `calendar_code` | text | Key: `EMEA`, `AMER`, `APAC`. |
| `calendar_name` | text | Display name. |
| `time_zone` | text | IANA time zone the opening hours are written in. |
| `open_local` | text | Opening time, local clock, `HH:MM`. |
| `close_local` | text | Closing time, local clock, `HH:MM`. |
| `note` | text | Working days and holiday source. |

### support_windows.csv

One row per working day per calendar, already converted to UTC. This is what lets SQL count support-hours
minutes without any time zone logic.

| Column | Type | Meaning |
| --- | --- | --- |
| `calendar_code` | text | Calendar the window belongs to. |
| `local_date` | date | The working day in the calendar's local time. |
| `open_utc` | UTC timestamp | Opening moment. Moves by an hour when daylight saving changes. |
| `close_utc` | UTC timestamp | Closing moment. |

### dim_date.csv

| Column | Type | Meaning |
| --- | --- | --- |
| `date_key` | integer | `yyyymmdd`. |
| `date` | date | The calendar date. Unique, one row per day, no gaps. |
| `year` | integer | Year. |
| `quarter` | integer | 1 to 4. |
| `month_number` | integer | 1 to 12. |
| `month_name` | text | English month name. |
| `year_month` | text | `yyyy-mm`. Sorts correctly as text. |
| `month_start` | date | First day of the month. |
| `week_start` | date | Monday of the week. |
| `day_of_week` | integer | 1 is Monday, 7 is Sunday. |
| `day_name` | text | English day name. |
| `is_weekend` | 0 or 1 | 1 on Saturday and Sunday. |
| `is_uk_bank_holiday` | 0 or 1 | 1 on England and Wales bank holidays. |
| `is_uk_working_day` | 0 or 1 | 1 on a weekday that is not a bank holiday. |

### extract_info.csv

One row describing the extract.

| Column | Type | Meaning |
| --- | --- | --- |
| `group_name` | text | Name of the fictional group. |
| `period_start` | date | First local day covered. |
| `period_end` | date | Last local day covered. |
| `as_of_utc` | UTC timestamp | When the extract was taken. Open tickets are measured up to this moment. |
| `seed` | integer | Random seed that produced the data. |
| `generator_version` | text | Generator version. |

## fact_ticket.csv (Power BI fact table)

Produced by the SQL view [`fact_ticket`](../sql/views/01_fact_ticket.sql). It contains every ticket column
above, with the same meaning, plus these.

| Column | Type | Meaning |
| --- | --- | --- |
| `calendar_code` | text | Support calendar of the ticket's site. |
| `clock_basis` | text | `24X7` or `SUPPORT_HOURS` from the target. Blank for tickets with no service level. |
| `has_sla` | 0 or 1 | 1 if a target exists for the ticket's type and priority. |
| `timeline_ok` | 0 or 1 | 1 if timestamps run forwards (opened, response, resolved, closed). Rows with 0 are kept but not measured. |
| `response_target_minutes` | integer | Response target that applied. Blank if none. |
| `resolution_target_minutes` | integer | Resolution target that applied. Blank if none. |
| `response_elapsed_minutes` | integer | Wall-clock minutes from opening to first response. If no response is recorded, to resolution, and if the ticket is also open, to the extract time. |
| `response_support_minutes` | integer | The same, counting only minutes inside the support window. |
| `response_clock_minutes` | integer | Whichever of the two the target's `clock_basis` uses. This is the figure compared with the target. |
| `resolution_elapsed_minutes` | integer | Wall-clock minutes from opening to resolution, or to the extract time if the ticket is open. |
| `resolution_support_minutes` | integer | The same, counting only support-window minutes. |
| `resolution_clock_minutes` | integer | Whichever the target's `clock_basis` uses. |
| `response_state` | text | `met`, `breached`, `in_flight` or `not_measured`. |
| `resolution_state` | text | `met`, `breached`, `in_flight` or `not_measured`. |
| `response_measured` | 0 or 1 | 1 if the response outcome counts (met or breached). |
| `response_met` | 0 or 1 | 1 if the response target was met. |
| `resolution_measured` | 0 or 1 | 1 if the resolution outcome counts (met or breached). |
| `resolution_met` | 0 or 1 | 1 if the resolution target was met. |
| `opened_month` | text | `yyyy-mm` of `opened_at` (UTC). |
| `resolved_month` | text | `yyyy-mm` of `resolved_at` (UTC). Blank if open. |
| `is_open` | 0 or 1 | 1 if there is no resolution time. |
| `open_age_days` | integer | Whole days from opening to the extract time. Blank unless the ticket is open. |

Added in Power Query (not in the CSV): `opened_date` and `resolved_date`, the UTC calendar date of each event, used for
relationships with `DimDate`.

## Model tables built in Power Query

| Table | Built from | Notes |
| --- | --- | --- |
| `DimSite` | `sites.csv` joined to `companies.csv` | Adds `company_name` and `sector`, so that Company and Site filter through one table. |
| `DimPriority` | `priority_matrix.csv` | Distinct priority and name, with `sort_order` 1 to 4. |
| `DimTicketType` | typed in the query | `ticket_type`, `ticket_type_label`, `has_sla`, `sort_order`. |

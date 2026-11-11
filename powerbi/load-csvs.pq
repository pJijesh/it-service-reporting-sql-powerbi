// Power Query (M) for loading this repository's CSV files into Power BI Desktop.
//
// STATUS: NOT RUN IN POWER BI DESKTOP. Every function used here was checked against the Power Query M
// reference on Microsoft Learn (see powerbi/README.md), but the code has not been executed. Expect to fix
// small things on first use, and check each query's column types in the Power Query editor.
//
// How to use
//   1. In Power BI Desktop: Home, Transform data, Manage Parameters, New Parameter. Create two Text
//      parameters, each ending with a path separator:
//        DataFolder   for example  C:\work\it-service-reporting-sql-powerbi\data\
//        ModelFolder  for example  C:\work\it-service-reporting-sql-powerbi\model\
//      (Run `python run_pipeline.py` first so that both folders exist.)
//   2. For each "Query:" block below, add a Blank Query, open Advanced Editor, paste the text between
//      the markers, and rename the query to the name shown.
//   3. Load FactTicket, DimDate, DimSite, DimTeam, DimPriority, DimTicketType, SlaTarget and PriorityMatrix.
//      Do not load fnLoadCsv, fnParseUtc or fnParseDate; they are helper functions only.
//   4. Create the relationships described in powerbi/data-model.md, then add measures from measures.dax.
//
// Why timestamps are parsed by hand: all timestamps in the files are UTC text like 2025-03-04T09:15:00Z.
// Parsing them with explicit positions and #datetime avoids any dependence on the Windows regional
// settings of the person opening the file, and on whether a text parser accepts the trailing Z.

// ===== Query: fnLoadCsv =====
(path as text) as table =>
let
    Source   = Csv.Document(File.Contents(path), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // Treat empty text as null so that blank timestamps and blank scores become real blanks.
    Blanks   = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, Table.ColumnNames(Promoted))
in
    Blanks
// ===== end =====

// ===== Query: fnParseUtc =====
// Turns "2025-03-04T09:15:00Z" into a datetime holding the UTC clock time. Blank in, null out.
(t as nullable text) as nullable datetime =>
if t = null or t = "" then null else
    #datetime(
        Number.FromText(Text.Range(t, 0, 4), "en-US"),
        Number.FromText(Text.Range(t, 5, 2), "en-US"),
        Number.FromText(Text.Range(t, 8, 2), "en-US"),
        Number.FromText(Text.Range(t, 11, 2), "en-US"),
        Number.FromText(Text.Range(t, 14, 2), "en-US"),
        Number.FromText(Text.Range(t, 17, 2), "en-US"))
// ===== end =====

// ===== Query: fnParseDate =====
// Turns "2025-03-04" into a date. Blank in, null out.
(t as nullable text) as nullable date =>
if t = null or t = "" then null else
    #date(
        Number.FromText(Text.Range(t, 0, 4), "en-US"),
        Number.FromText(Text.Range(t, 5, 2), "en-US"),
        Number.FromText(Text.Range(t, 8, 2), "en-US"))
// ===== end =====

// ===== Query: FactTicket =====
// One row per ticket, with the service level clock already calculated by the SQL view fact_ticket.
let
    Source = fnLoadCsv(ModelFolder & "fact_ticket.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"ticket_id", type text}, {"ticket_type", type text}, {"company_id", type text},
        {"site_id", type text}, {"category", type text}, {"priority", type text},
        {"impact", Int64.Type}, {"urgency", Int64.Type},
        {"opened_at", type text}, {"first_response_at", type text},
        {"resolved_at", type text}, {"closed_at", type text},
        {"reopened", Int64.Type}, {"resolved_first_contact", Int64.Type},
        {"assignee_team", type text}, {"csat", Int64.Type},
        {"calendar_code", type text}, {"clock_basis", type text},
        {"has_sla", Int64.Type}, {"timeline_ok", Int64.Type},
        {"response_target_minutes", Int64.Type}, {"resolution_target_minutes", Int64.Type},
        {"response_elapsed_minutes", Int64.Type}, {"response_support_minutes", Int64.Type},
        {"response_clock_minutes", Int64.Type}, {"resolution_elapsed_minutes", Int64.Type},
        {"resolution_support_minutes", Int64.Type}, {"resolution_clock_minutes", Int64.Type},
        {"response_state", type text}, {"resolution_state", type text},
        {"response_measured", Int64.Type}, {"response_met", Int64.Type},
        {"resolution_measured", Int64.Type}, {"resolution_met", Int64.Type},
        {"opened_month", type text}, {"resolved_month", type text},
        {"is_open", Int64.Type}, {"open_age_days", Int64.Type}
    }, "en-US"),
    Stamps = Table.TransformColumns(Typed, {
        {"opened_at", fnParseUtc, type datetime}, {"first_response_at", fnParseUtc, type datetime},
        {"resolved_at", fnParseUtc, type datetime}, {"closed_at", fnParseUtc, type datetime}
    }),
    // Date columns for the relationships with DimDate (the UTC calendar date of each event).
    OpenedDate   = Table.AddColumn(Stamps, "opened_date", each if [opened_at] = null then null else DateTime.Date([opened_at]), type date),
    ResolvedDate = Table.AddColumn(OpenedDate, "resolved_date", each if [resolved_at] = null then null else DateTime.Date([resolved_at]), type date)
in
    ResolvedDate
// ===== end =====

// ===== Query: DimDate =====
let
    Source = fnLoadCsv(DataFolder & "dim_date.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"date_key", Int64.Type}, {"year", Int64.Type}, {"quarter", Int64.Type},
        {"month_number", Int64.Type}, {"month_name", type text}, {"year_month", type text},
        {"day_of_week", Int64.Type}, {"day_name", type text}, {"is_weekend", Int64.Type},
        {"is_uk_bank_holiday", Int64.Type}, {"is_uk_working_day", Int64.Type}
    }, "en-US"),
    Dates  = Table.TransformColumns(Typed, {
        {"date", fnParseDate, type date}, {"month_start", fnParseDate, type date},
        {"week_start", fnParseDate, type date}
    })
in
    Dates
// ===== end =====

// ===== Query: DimSite =====
// Sites with their company merged in, so that Company and Site filter the facts through one table.
let
    Sites     = fnLoadCsv(DataFolder & "sites.csv"),
    SitesTyped = Table.TransformColumnTypes(Sites, {
        {"site_id", type text}, {"company_id", type text}, {"site_name", type text},
        {"country", type text}, {"time_zone", type text}, {"support_calendar", type text},
        {"headcount", Int64.Type}}, "en-US"),
    Companies = Table.TransformColumnTypes(fnLoadCsv(DataFolder & "companies.csv"), {
        {"company_id", type text}, {"company_name", type text}, {"sector", type text}}, "en-US"),
    Merged    = Table.NestedJoin(SitesTyped, {"company_id"}, Companies, {"company_id"}, "company", JoinKind.LeftOuter),
    Expanded  = Table.ExpandTableColumn(Merged, "company", {"company_name", "sector"})
in
    Expanded
// ===== end =====

// ===== Query: DimTeam =====
let
    Source = fnLoadCsv(DataFolder & "teams.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"team_id", type text}, {"team_name", type text}, {"fte", type number}, {"description", type text}
    }, "en-US")
in
    Typed
// ===== end =====

// ===== Query: DimPriority =====
let
    Source   = fnLoadCsv(DataFolder & "priority_matrix.csv"),
    Distinct = Table.Distinct(Table.SelectColumns(Source, {"priority", "priority_name"})),
    Sorted   = Table.AddColumn(Distinct, "sort_order", each Number.FromText(Text.Range([priority], 1, 1), "en-US"), Int64.Type)
in
    Sorted
// ===== end =====

// ===== Query: DimTicketType =====
#table(
    type table [ticket_type = text, ticket_type_label = text, has_sla = Int64.Type, sort_order = Int64.Type],
    {
        {"incident", "Incident", 1, 1},
        {"service_request", "Service request", 1, 2},
        {"problem", "Problem", 0, 3},
        {"change", "Change", 0, 4}
    }
)
// ===== end =====

// ===== Query: SlaTarget =====
// Reference table for tooltips and a target table visual. Not related to FactTicket: the target that
// applied to each ticket is already stored on the ticket row.
let
    Source = fnLoadCsv(DataFolder & "sla_targets.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"ticket_type", type text}, {"priority", type text}, {"response_target_minutes", Int64.Type},
        {"resolution_target_minutes", Int64.Type}, {"clock_basis", type text}
    }, "en-US")
in
    Typed
// ===== end =====

// ===== Query: PriorityMatrix =====
// Reference table for a matrix visual that shows how impact and urgency give a priority. Not related.
let
    Source = fnLoadCsv(DataFolder & "priority_matrix.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"impact", Int64.Type}, {"urgency", Int64.Type}, {"priority", type text}, {"priority_name", type text}
    }, "en-US")
in
    Typed
// ===== end =====

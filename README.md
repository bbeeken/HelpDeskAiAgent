# HelpDesk AI Agent

This project exposes a FastAPI application for the Truck Stop MCP Helpdesk.

## Setup

1. **Install dependencies**

   ```bash
   pip install -e .
   ```

   The requirements include `aioodbc` for async ODBC connections and `requests` for standard HTTP calls; `pyodbc` is no longer required. The optional `sentry_sdk` package enables error tracking when `ERROR_TRACKING_DSN` is set.
2. **Environment variables**

   The application requires the following variables:

  - `DB_CONN_STRING` – SQLAlchemy connection string for your database. Use an async driver such as `mssql+aioodbc://`; synchronous `mssql+pyodbc` connections raise `InvalidRequestError` with `create_async_engine`.
    An example connection string is:

    ```bash
    DB_CONN_STRING="mssql+aioodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server"
    ```
   The `driver` name must match an ODBC driver installed on the host machine.
  - `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_TENANT_ID` – optional credentials used for Microsoft Graph
    lookups in `src.core.services.user_services`. When omitted, stub responses are returned.

  - `ENABLE_RATE_LIMITING` – enable the SlowAPI limiter middleware.
    Set to `false`, `0`, or `no` to disable it (default `true`).

  - `ERROR_TRACKING_DSN` – optional DSN for Sentry or another error tracking
    service. When set, the application initializes `sentry_sdk` on startup to
    capture unhandled exceptions.

  They can be provided in the shell environment or in a `.env` file in the project root.
  A template called `.env.example` lists the required and optional variables; copy it to `.env` and
  update the values for your environment. `config.py` automatically loads `.env` and then looks for
  `config_env.py` to provide Python-level overrides when needed.

  Unknown environment variables are ignored. They can be present in `.env` or the shell without
  causing validation errors.

3. **Ticket text length**

   Ticket bodies and resolutions may exceed 2000 characters. These fields are
   stored unmodified in the database using `TEXT`/`nvarchar(max)` columns so
   their full contents are preserved. There is no environment variable that
   limits their length; however, your `DB_CONN_STRING` should point to a driver
   and database that support these large text types.

4. **Python 3.12**

   When running the application or tests on Python 3.12 you may need to disable
   Pydantic's standard types shim:

   ```bash
   export PYDANTIC_DISABLE_STD_TYPES_SHIM=1
   ```

   Set this variable in your shell before starting the app or executing tests if
   you encounter import errors related to builtin collections.

## Running the API

Start the development server with Uvicorn:

```bash
uvicorn main:app --reload
```
## API Documentation

Detailed endpoint descriptions are provided in [docs/API.md](docs/API.md).

## Datetime Formatting

Timestamps must use UTC with millisecond precision (`YYYY-MM-DD HH:MM:SS.mmm`).
Use `format_db_datetime`, `parse_search_datetime`, and the `FormattedDateTime`
SQLAlchemy type to ensure values conform to this requirement. See
[docs/DATETIME_FORMAT.md](docs/DATETIME_FORMAT.md) for examples and common
pitfalls.

## Site Access Requirements

Non-admin callers must supply a `site_id` when querying or modifying tickets through the API or MCP tools. The system derives each user's site from the prompt and rejects attempts to create or update tickets for other locations. Only administrators may omit the `site_id` or work across multiple sites.
## Running tests

Install the dependencies from `requirements.txt` and the package itself before
running the linters and tests. A helper script is provided to automate this
setup:

```bash
# install packages and verify required tools are available
bash scripts/setup-tests.sh
```

The script installs everything with `pip install -r requirements.txt` and
`pip install -e .`, then prints the versions of `flake8`, `pytest` and
`httpx`. After running it (or manually installing the packages) execute:

```bash
flake8
pytest
```

## Docker Compose

Build the image and start the containers:

```bash
docker build -t helpdesk-agent .
docker-compose up
```

The MCP server will be available on `http://localhost:8008` when the
containers are running.

Compose reads variables from `.env`. Copy `.env.example` to `.env` and set
values for required options such as `DB_CONN_STRING`.
Optional Graph credentials may also be provided in this file. Add any
environment-specific Python overrides in a `config_env.py` file next to
`config.py`.

## Database Migrations

Alembic manages schema migrations. Common commands:

```bash
# create a new revision from models
alembic revision --autogenerate -m "message"
# apply migrations to the database
alembic upgrade head
```

Both the `Ticket_Body` and `Resolution` columns are defined using the SQL
`TEXT` (or `nvarchar(max)`) type so lengthy content can be stored without
truncation. Ensure any custom migrations preserve this unrestricted text type.

### Tickets_Master columns

The `Tickets_Master` table stores the primary ticket data. Columns include:

- `Ticket_ID`
- `Subject`
- `Ticket_Body`
- `Ticket_Status_ID`
- `Ticket_Contact_Name`
- `Ticket_Contact_Email`
- `Asset_ID`
- `Site_ID`
- `Ticket_Category_ID`
- `Version`
- `Created_Date`
- `Assigned_Name`
- `Assigned_Email`
- `Severity_ID`
- `Assigned_Vendor_ID`
- `Closed_Date`
- `LastModified`
- `LastModfiedBy`
- `Resolution`

### V_Ticket_Master_Expanded

The API uses the `V_Ticket_Master_Expanded` view to join tickets with
related labels such as status, asset, site, and vendor. Endpoints like
`/tickets/expanded` and `/tickets/search` rely on this view to return a
fully populated ticket record.

Create the view with SQL similar to the following (the full statement is also
available in `src.core.repositories.sql.py` as `CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL`):

```sql
CREATE VIEW V_Ticket_Master_Expanded AS
SELECT t.Ticket_ID,
       t.Subject,
       t.Ticket_Body,
       t.Ticket_Status_ID,
       ts.Label AS Ticket_Status_Label,
       t.Ticket_Contact_Name,
       t.Ticket_Contact_Email,
       t.Asset_ID,
       a.Label AS Asset_Label,
       t.Site_ID,
       s.Label AS Site_Label,
       t.Ticket_Category_ID,
       c.Label AS Ticket_Category_Label,
       t.Version,
       t.Created_Date,
       t.Assigned_Name,
       t.Assigned_Email,
       t.Severity_ID,
       t.Assigned_Vendor_ID,
       t.Closed_Date,
       t.LastModified,
       t.LastModfiedBy,
       t.Version,
       v.Name AS Assigned_Vendor_Name,
       t.Resolution,
       p.Label AS Priority_Level
FROM Tickets_Master t
LEFT JOIN Ticket_Status ts ON ts.ID = t.Ticket_Status_ID
LEFT JOIN Assets a ON a.ID = t.Asset_ID
LEFT JOIN Sites s ON s.ID = t.Site_ID
LEFT JOIN Ticket_Categories c ON c.ID = t.Ticket_Category_ID
LEFT JOIN Vendors v ON v.ID = t.Assigned_Vendor_ID
LEFT JOIN Priority_Levels p ON p.ID = t.Severity_ID;
```

### API Highlights

- `GET /health` - health check returning database status, uptime, and version
- `POST /ticket` - create a ticket
- `GET /tickets/expanded` - list tickets with related labels. Supports
  dynamic query parameters to filter by any column in
  `V_Ticket_Master_Expanded` and a `sort` parameter for ordering.
- `GET /ticket/search` - search tickets by subject or body. Query parameters:
`q` (required), `limit` (default `10`), optional `created_after`/`created_before` (ISO-8601 datetimes with timezone)
  and other `V_Ticket_Master_Expanded` columns for filtering, plus
  `sort=oldest|newest` to control ordering. The legacy `/tickets/search` path
  remains available.
- `POST /ticket/search` - JSON variant accepting the same fields as the GET
  endpoint via a `TicketSearchRequest` body.
- `GET /tickets/by_user` - list tickets where the user is the contact,
  assigned technician or has posted a message. Provide an `identifier` and
  optionally filter by `status` (open, closed or progress). Additional query
  parameters are applied as column filters on `V_Ticket_Master_Expanded`.
- Lookup endpoints (`/lookup/assets`, `/lookup/vendors`, `/lookup/sites`,
  `/lookup/categories`, `/lookup/statuses`) now accept arbitrary `filters`
  and a `sort` parameter to order by any column.
- `PUT /ticket/{id}` - update an existing ticket
- Ticket body and resolution fields now accept large text values; the previous
  2000-character limit has been removed.

#### Searching for tickets

Use `/ticket/search` for keyword queries. Provide `q` for the search text and
optionally specify `limit`, `created_after`, `created_before` (ISO-8601 datetimes with timezone) or any
`V_Ticket_Master_Expanded` column to filter results. Sorting by
`Created_Date` is controlled with `sort=oldest|newest`. A POST variant accepts a
`TicketSearchRequest` JSON body containing the same fields.

Example:

```bash
curl "http://localhost:8000/ticket/search?q=printer&limit=5&created_after=2024-01-01T00:00:00Z"
```

### Analytics Endpoints

- `GET /analytics/late_tickets` - list tickets that are past their expected resolution date. Returns a JSON array of objects containing the ticket ID, assigned technician and number of days late.

  Example:

  ```bash
  curl http://localhost:8000/analytics/late_tickets
  ```

  ```json
  [
    {
      "ticket_id": 123,
      "assigned_email": "tech@example.com",
      "days_late": 5
    }
  ]
  ```

- `GET /analytics/staff_report` - return summary statistics for each technician showing the number of open and overdue tickets assigned to them.

  Example:

  ```bash
  curl http://localhost:8000/analytics/staff_report
  ```

  ```json
  [
    {
      "assigned_email": "tech@example.com",
      "open": 7,
      "late": 2
    }
  ]
  ```

- `GET /analytics/open_by_site` - count open tickets grouped by site.

  Example:

  ```bash

  curl "http://localhost:8000/analytics/open_by_assigned_user?Assigned_Email=tech@example.com"

  curl http://localhost:8000/analytics/open_by_site
  ```

  ```json
  [
    {
      "site_id": 1,
      "site_label": "Main",
      "count": 3
    }
  ]
  ```

- `GET /analytics/open_by_assigned_user` - count open tickets grouped by assigned technician. Supports ticket filtering parameters.

  Example:

  ```bash
  curl http://localhost:8000/analytics/open_by_assigned_user
  ```

  ```json
  [
    {
      "assigned_email": "tech@example.com",
      "assigned_name": "Tech",
      "count": 2
    }
  ]

  ```

## CLI

`src.core.services.cli` provides a small command-line interface to the API. Set `API_BASE_URL` to the server URL (default `http://localhost:8000`).

Create a ticket:

```bash
echo '{"Subject":"Subj","Ticket_Body":"Body","Ticket_Contact_Name":"Name","Ticket_Contact_Email":"a@example.com"}' | \
python -m src.core.services.cli create-ticket
```

## MCP Streaming Interface

Connect to the built-in MCP endpoint to exchange JSON-RPC messages.

1. **Open the stream** with `GET /mcp`. It returns Server-Sent Events. The first
   `endpoint` event contains the URL for posting commands (e.g. `/mcp/abc123`).
2. **POST messages** to that URL. Each payload is echoed back on the stream as a
   `message` event.

Example:

```
# Send a command
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}' \

  http://localhost:8000$ENDPOINT

```

## Docker

Build the image and start the stack with Docker Compose:

```bash
docker compose build
docker compose up
```

The API listens on `http://localhost:8000`. The compose file reads environment
values from `.env`. `DB_CONN_STRING` is set automatically to connect to the
`postgres` container using the provided `POSTGRES_USER`, `POSTGRES_PASSWORD`, and
`POSTGRES_DB` values.

## Verifying Available Tools

Run `verify_tools.py` after deploying to ensure the server exposes the expected
set of tool endpoints. The `/tools` route returns an object with a `tools` key
listing the available operations. The verification script fetches this route
and compares the returned names against a predefined mapping. It exits with a
non-zero status when any tools are missing or unexpected. The default mapping
checks for the ``get_ticket`` and ``search_tickets`` endpoints. The route may
list additional operations such as ``sla_metrics`` and ``bulk_update_tickets``,
which the script reports as unexpected.

Verify the list of available tools with:

```bash
python verify_tools.py http://localhost:8000
```

### Tool Reference

The MCP server exposes several JSON-RPC tools. `get_tickets_by_user` returns
expanded ticket records for a user. It accepts an `identifier`, optional
`status` and arbitrary `filters`. Detailed descriptions for every tool are
available in [docs/MCP_TOOLS_GUIDE.md](docs/MCP_TOOLS_GUIDE.md).

```bash
curl "http://localhost:8000/get_tickets_by_user?identifier=user@example.com&status=open"
```

Tool endpoints validate request bodies against each tool's `inputSchema` using

JSON Schema. Invalid requests yield a `422 Unprocessable Entity` response. The
response body includes a `path` key showing which property failed validation and
now echoes back the submitted `payload`. When possible a `value` field contains
the specific invalid item.

`get_open_tickets` lists tickets filtered by status and age. Provide a
number of `days` and optional `status` such as `open` or `closed`.

```bash
curl -X POST http://localhost:8000/get_open_tickets \
  -d '{"status": "open", "days": 7, "limit": 5}'
```

Additional tools are available:

* `search_tickets` – run a detailed ticket search. The legacy
  `search_tickets_advanced` route has been removed in favor of this
  unified interface.
  ```bash
  curl -X POST http://localhost:8000/search_tickets \
    -d '{"text": "printer", "status": "open", "days": 0}'
  ```

  The response may include a `relevance_score` and a `highlights` object when a
  text query is provided. `relevance_score` uses TF‑IDF cosine similarity to rank
  results. `highlights` contains the subject and body with
  matching terms wrapped in `<em>` tags. Each ticket also includes a `metadata`
  object with fields like `age_days`, `is_overdue`, and `complexity_estimate`.
  A ticket is considered overdue once it has been open for more than 24 hours.
  Complexity is estimated as `"high"` if the body exceeds 500 characters or the
  subject exceeds 100 characters, `"medium"` for bodies over 200 characters or
  subjects over 50 characters, otherwise `"low"`.

* `update_ticket` – modify an existing ticket, including escalation. Updates
  may use semantic field names (e.g. `status`, `priority`) or raw column IDs
  (`Ticket_Status_ID`, `Severity_ID`) as defined in the ticket field mapping
  table.
  ```bash
  curl -X POST http://localhost:8000/update_ticket \
    -d '{"ticket_id": 123, "updates": {"status": "closed"}}'
  ```

* `sla_metrics` – retrieve SLA performance metrics.
  ```bash
  curl -X POST http://localhost:8000/sla_metrics -d '{}'
  ```
* `bulk_update_tickets` – apply updates to many tickets at once. The `updates`
  payload accepts the same semantic names or raw IDs as `update_ticket`.
  ```bash
  curl -X POST http://localhost:8000/bulk_update_tickets \
    -d '{"ticket_ids": [1,2,3], "updates": {"Ticket_Status_ID": 3}}'
  ```


The server exposes ten core JSON-RPC tools. Each expects a JSON body matching its schema.

1. `get_ticket` – `{"ticket_id": 123}`
2. `list_tickets` – `{"limit": 5}`
3. `create_ticket` – see `TicketCreate` schema
4. `update_ticket` – `{"ticket_id": 1, "updates": {}}` (semantic or raw fields)
5. `add_ticket_message` – `{"ticket_id": 1, "message": "Checking", "sender_name": "Agent"}`
6. `search_tickets` – `{"text": "printer", "status": 1, "days": 0}`
7. `get_tickets_by_user` – `{"identifier": "user@example.com"}`
8. `get_open_tickets` – `{"days": 30}`
9. `get_ticket_full_context` – `{"ticket_id": 123}` (no user history or nested related tickets)
10. `get_system_snapshot` – `{}`

The server exposes the following JSON-RPC tools defined in `ENHANCED_TOOLS`. Each expects a JSON body matching its schema.

- `get_ticket` – `{"ticket_id": 123}`
- `create_ticket` – see `TicketCreate` schema
- `update_ticket` – `{"ticket_id": 1, "updates": {}}` (supports semantic names or raw IDs)
- `bulk_update_tickets` – `{"ticket_ids": [1,2], "updates": {}}` (semantic or raw fields)
- `add_ticket_message` – `{"ticket_id": 1, "message": "Checking", "sender_name": "Agent"}`
- `get_ticket_messages` – `{"ticket_id": 123}`
- `get_ticket_attachments` – `{"ticket_id": 123}`
- `search_tickets` – `{"text": "printer", "status": "open", "days": 0}`
- `get_analytics` – `{"type": "overview"}`
- `get_reference_data` – `{"type": "sites"}`
- `get_ticket_full_context` – `{"ticket_id": 123}`
- `advanced_search` – `{"text_search": "printer issue"}`
- `search_tickets` – `{"text": "printer", "status": "open", "days": 0}`

- `get_tickets_by_user` – `{"identifier": "user@example.com"}`
- `get_ticket_full_context` – `{"ticket_id": 123}` (no user history or nested related tickets)
- `get_system_snapshot` – `{}`
- `get_ticket_stats` – `{}`
- `get_workload_analytics` – `{}`
- `sla_metrics` – `{"days": 30}`


See [docs/MCP_TOOLS_GUIDE.md](docs/MCP_TOOLS_GUIDE.md) for detailed descriptions.

## License

This project is licensed under the [MIT License](LICENSE).


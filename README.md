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
    lookups in `tools.user_tools`. When omitted, stub responses are returned.


  - `ENABLE_RATE_LIMITING` – enable the SlowAPI limiter middleware.
    Set to `false`, `0`, or `no` to disable it (default `true`).

  - `ERROR_TRACKING_DSN` – optional DSN for Sentry or another error tracking
    service. When set, the application initializes `sentry_sdk` on startup to
    capture unhandled exceptions.


  They can be provided in the shell environment or in a `.env` file in the project root.
  A template called `.env.example` lists the required and optional variables; copy it to `.env` and
  update the values for your environment. `config.py` automatically loads `.env` and then looks for
  `config_env.py` to provide Python-level overrides when needed.

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


### V_Ticket_Master_Expanded

The API uses the `V_Ticket_Master_Expanded` view to join tickets with
related labels such as status, asset, site, and vendor. Endpoints like
`/tickets/expanded` and `/tickets/search` rely on this view to return a
fully populated ticket record.

Create the view with SQL similar to the following (the full statement is also
available in `db/sql.py` as `CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL`):


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
       t.Created_Date,
       t.Assigned_Name,
       t.Assigned_Email,
       t.Priority_ID,
       t.Assigned_Vendor_ID,
       t.Closed_Date,
       t.LastModified,
       v.Name AS Assigned_Vendor_Name,
       t.Resolution,
       p.Level AS Priority_Level
FROM Tickets_Master t
LEFT JOIN Ticket_Status ts ON ts.ID = t.Ticket_Status_ID
LEFT JOIN Assets a ON a.ID = t.Asset_ID
LEFT JOIN Sites s ON s.ID = t.Site_ID
LEFT JOIN Ticket_Categories c ON c.ID = t.Ticket_Category_ID
LEFT JOIN Vendors v ON v.ID = t.Assigned_Vendor_ID
LEFT JOIN Priority_Levels p ON p.ID = t.Priority_ID;
```


### API Highlights

- `GET /health` - health check returning database status, uptime, and version
- `POST /ticket` - create a ticket
- `GET /tickets/expanded` - list tickets with related labels. Supports
  dynamic query parameters to filter by any column in
  `V_Ticket_Master_Expanded` and a `sort` parameter for ordering.
- `GET /tickets/search` - search tickets by subject or body. Accepts the same
  optional fields as `/tickets/expanded` plus `sort=oldest|newest` to control
  ordering
- `GET /tickets/smart_search` - perform a natural language search. Parameters:
  `q` for the query, `limit` for number of results (default `10`), and
  `include_closed` to search closed tickets. Returns structured results sorted
  by relevance.
- `GET /tickets/by_user` - list tickets where the user is the contact,
  assigned technician or has posted a message. Provide a name or email via the
  `identifier` query parameter.
- `PUT /ticket/{id}` - update an existing ticket
- Ticket body and resolution fields now accept large text values; the previous
  2000-character limit has been removed.

#### Smart search vs. regular search

Use `/tickets/search` for straightforward keyword queries or when you need to
filter and sort by specific columns in `V_Ticket_Master_Expanded`. The
`/tickets/smart_search` endpoint interprets natural language phrases (e.g.
"unassigned high priority emails") and returns results ranked by relevance. It
works best for quick human-friendly searches or when you don't know the exact
keywords to use.

Example:

```bash
curl "http://localhost:8000/tickets/smart_search?q=unassigned+critical&limit=5"
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

`tools.cli` provides a small command-line interface to the API. Set `API_BASE_URL` to the server URL (default `http://localhost:8000`).

Create a ticket:

```bash
echo '{"Subject":"Subj","Ticket_Body":"Body","Ticket_Contact_Name":"Name","Ticket_Contact_Email":"a@example.com"}' | \
python -m tools.cli create-ticket
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
set of tool endpoints. The `/tools` route now returns an object with a `tools`
key containing the available tools. The verification script fetches this route
and compares the returned names against a predefined mapping. It exits with a
non-zero status when any tools are missing or unexpected. The default mapping
checks for the ``g_ticket`` and ``l_tkts`` endpoints.

```bash
python verify_tools.py http://localhost:8000
```

Include this check in deployment pipelines to catch configuration issues early.

### Tool Reference

The MCP server exposes several JSON-RPC tools. `tickets_by_user` returns
expanded ticket records related to a specific user.

```bash
curl "http://localhost:8000/tickets/by_user?identifier=user@example.com"
```

`tickets_by_timeframe` lists tickets filtered by status and age. Provide a
number of `days` and optional `status` such as `open` or `closed`.

```bash
curl -X POST http://localhost:8000/tickets_by_timeframe \
  -d '{"status": "open", "days": 7, "limit": 5}'
```

## License

This project is licensed under the [MIT License](LICENSE).



# HelpDesk AI Agent

This project exposes a FastAPI application for the Truck Stop MCP Helpdesk.

## Setup

1. **Install dependencies**

   ```bash
   pip install -e .
   ```

   The requirements include `aioodbc` for async ODBC connections and `requests` for standard HTTP calls; `pyodbc` is no longer required.
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
  - `MCP_URL` – optional MCP server URL used by AI helper functions
    (default `http://localhost:8080`).
  - `MCP_STREAM_TIMEOUT` – timeout in seconds for streaming AI responses
    (default `30`).

  - `OPENAI_API_KEY` – API key used by OpenAI-based tools.

  - `ENABLE_ENHANCED_MCP` – set to `0` to disable the enhanced MCP tool server
    and use the basic implementation.


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

Install the testing dependencies and run `pytest`:

```bash
pip install -e .
pytest
```

## Docker Compose

Build the image and start the containers:

```bash
docker build -t helpdesk-agent .
docker-compose up
```

Compose reads variables from `.env`. Copy `.env.example` to `.env` and set
values for required options such as `DB_CONN_STRING` and `OPENAI_API_KEY`.
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
- `GET /tickets` - list tickets. Supports dynamic query parameters to filter by
  any column in `V_Ticket_Master_Expanded` and a `sort` parameter for ordering.
- `GET /tickets/expanded` - list tickets with related labels. Accepts the same
  filtering and sorting parameters as `/tickets`.
- `GET /tickets/search?q=term` - search tickets by subject or body
- `PUT /ticket/{id}` - update an existing ticket
- `DELETE /ticket/{id}` - remove a ticket
- `POST /ai/suggest_response` - generate an AI ticket reply
- `POST /ai/suggest_response/stream` - stream an AI reply as it is generated
- Ticket body and resolution fields now accept large text values; the previous
  2000-character limit has been removed.


## CLI

`tools.cli` provides a small command-line interface to the API. Set `API_BASE_URL` to the server URL (default `http://localhost:8000`).

Stream an AI-generated response:

```bash
echo '{"Ticket_ID":1,"Subject":"Subj","Ticket_Body":"Body","Ticket_Status_ID":1,"Ticket_Contact_Name":"Name","Ticket_Contact_Email":"a@example.com"}' | \
python -m tools.cli stream-response
```

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
set of tool endpoints. The script fetches the `/tools` route and compares the
returned tool names against a predefined mapping. It exits with a non-zero
status when any tools are missing or unexpected.

```bash
python verify_tools.py http://localhost:8000
```

Include this check in deployment pipelines to catch configuration issues early.

## License

This project is licensed under the [MIT License](LICENSE).



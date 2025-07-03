# HelpDesk AI Agent

This project exposes a FastAPI application for the Truck Stop MCP Helpdesk.

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   The requirements include `aioodbc` for async ODBC connections; `pyodbc` is no longer required.
2. **Environment variables**

   The application requires the following variables:

  - `DB_CONN_STRING` – SQLAlchemy connection string for your database. Use an async driver such as `mssql+aioodbc://`; synchronous `mssql+pyodbc` connections raise `InvalidRequestError` with `create_async_engine`.
    An example connection string is:

    ```bash
    DB_CONN_STRING="mssql+aioodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server"
    ```
   The `driver` name must match an ODBC driver installed on the host machine.
   - `OPENAI_API_KEY` – API key used by the OpenAI integration.
   - `CONFIG_ENV` – which config to load: `dev`, `staging`, or `prod` (default `dev`).
   - `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_TENANT_ID` – optional credentials used for Microsoft Graph
     lookups in `tools.user_tools`. When omitted, stub responses are returned.


  Optional Microsoft Graph credentials enable real user lookups:

   - `GRAPH_CLIENT_ID` – application (client) ID issued by Azure AD.
   - `GRAPH_CLIENT_SECRET` – client secret associated with the app registration.
   - `GRAPH_TENANT_ID` – tenant ID used when acquiring OAuth tokens.

  When these variables are not provided, the Graph helper functions fall back
  to stub implementations so tests can run without network access.


  They can be provided in the shell environment or in a `.env` file in the project root.
  A template called `.env.example` lists the required and optional variables; copy it to `.env` and
  update the values for your environment. `config.py` automatically loads `.env` and
  then imports `config_{CONFIG_ENV}.py` so the appropriate settings are applied at
  startup. OpenAI model parameters such as model name and timeouts are defined in the
  selected config file. The Graph credentials are optional; without them, the Graph
  helper functions return stub data so tests and development work without network
  access.

## Running the API

Start the development server with Uvicorn:

```bash
uvicorn main:app --reload
```

Select a configuration by setting `CONFIG_ENV`:

```bash
CONFIG_ENV=prod uvicorn main:app
```

## Running tests

Install the testing dependencies and run `pytest`:

```bash
pip install -r requirements.txt
pytest
```

## Database Migrations

Alembic manages schema migrations. Common commands:

```bash
# create a new revision from models
alembic revision --autogenerate -m "message"
# apply migrations to the database
alembic upgrade head
```


### V_Ticket_Master_Expanded

The API uses the `V_Ticket_Master_Expanded` view to join tickets with
related labels such as status, asset, site, and vendor. Endpoints like
`/tickets/expanded` and `/tickets/search` rely on this view to return a
fully populated ticket record.

Create the view with SQL similar to the following:


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
LEFT JOIN Priorities p ON p.ID = t.Priority_ID;
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

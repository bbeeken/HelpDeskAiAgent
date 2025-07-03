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

The revision `6d3242144893_create_ticket_expanded_view` adds the
`V_Ticket_Master_Expanded` view. Expanded ticket queries rely on this
view being present.

### API Highlights

- `GET /health` - health check returning database status, uptime, and version
- `POST /ticket` - create a ticket
- `GET /tickets` - list tickets
- `GET /tickets/search?q=term` - search tickets by subject or body
- `PUT /ticket/{id}` - update an existing ticket
- `DELETE /ticket/{id}` - remove a ticket

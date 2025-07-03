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

   They can be provided in the shell environment or in a `.env` file in the project root.
   `config.py` automatically loads `.env` and then imports `config_{CONFIG_ENV}.py`
   so the appropriate settings are applied at startup. OpenAI model parameters
   such as model name and timeouts are defined in the selected config file.

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

### API Highlights

- `GET /health` - health check returning database status, uptime, and version
- `POST /ticket` - create a ticket
- `GET /tickets` - list tickets
- `GET /tickets/search?q=term` - search tickets by subject or body
- `PUT /ticket/{id}` - update an existing ticket
- `DELETE /ticket/{id}` - remove a ticket

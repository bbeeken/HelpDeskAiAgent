# HelpDesk AI Agent

This project exposes a FastAPI application for the Truck Stop MCP Helpdesk.

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Environment variables**

   The application requires the following variables:

   - `DB_CONN_STRING` – SQLAlchemy connection string for your database.
   - `OPENAI_API_KEY` – API key used by the OpenAI integration.
   - `CONFIG_ENV` – which config to load: `dev`, `staging`, or `prod` (default `dev`).

   They can be provided in the shell environment or in a `.env` file in the project root.  
   OpenAI model parameters such as model name and timeouts are defined in the selected config file.

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

### API Highlights

- `GET /health` - health check returning uptime and version
- `POST /ticket` - create a ticket
- `GET /tickets` - list tickets
- `GET /tickets/search?q=term` - search tickets by subject or body
- `PUT /ticket/{id}` - update an existing ticket
- `DELETE /ticket/{id}` - remove a ticket

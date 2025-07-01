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

   They can be provided in the shell environment or in a `.env` file in the project root.

## Running the API

Start the development server with Uvicorn:

```bash
uvicorn main:app --reload
```

## Running tests

Install the testing dependencies and run `pytest`:

```bash
pip install -r requirements.txt
pytest
```

### API Highlights

- `POST /ticket` - create a ticket
- `GET /tickets` - list tickets
- `GET /tickets/search?q=term` - search tickets by subject or body
- `PUT /ticket/{id}` - update an existing ticket
- `DELETE /ticket/{id}` - remove a ticket

# HelpDesk AI Agent

This project exposes a FastAPI service for managing help desk tickets and querying OpenAI for suggested responses.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set environment variables:
   - `DB_CONN_STRING` - SQLAlchemy connection string for the MS SQL database.
   - `OPENAI_API_KEY` - API key for OpenAI.

3. Run the API:
   ```bash
   uvicorn main:app --reload
   ```

### API Highlights

- `POST /ticket` - create a ticket
- `GET /tickets` - list tickets
- `GET /tickets/search?q=term` - search tickets by subject or body
- `PUT /ticket/{id}` - update an existing ticket
- `DELETE /ticket/{id}` - remove a ticket

## Tests

Tests use `pytest`. Run them with:

```bash
pytest
```

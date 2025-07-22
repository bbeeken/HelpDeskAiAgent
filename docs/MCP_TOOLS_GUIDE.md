# MCP Tools Guide

This document describes the JSON-RPC tools exposed by the MCP server. Each section lists the purpose of the tool, the parameters expected in the request body and an example invocation.

## get_ticket
Fetch a ticket by ID.

Example:
```bash
curl -X POST http://localhost:8000/get_ticket \
  -d '{"ticket_id": 1}'
```

## list_tickets
List tickets with optional filters.

Example:
```bash
curl -X POST http://localhost:8000/list_tickets \
  -d '{"limit": 5, "filters": {"status": "open"}}'
```

## create_ticket
Create a new ticket. Parameters match the `TicketCreate` schema described in [API.md](API.md).

Example:
```bash
curl -X POST http://localhost:8000/create_ticket \
  -d '{"Subject": "Printer issue", "Ticket_Contact_Name": "Alice"}'
```

## update_ticket
Update an existing ticket by ID.

Parameters:
- `ticket_id` – integer ID of the ticket.
- `updates` – object of fields to modify.

Example:
```bash
curl -X POST http://localhost:8000/update_ticket \
  -d '{"ticket_id": 5, "updates": {"Assigned_Email": "tech@example.com"}}'
```

## close_ticket
Close a ticket with a resolution.

Parameters:
- `ticket_id` – integer ticket ID.
- `resolution` – resolution text.
- `status_id` – optional status (defaults to 4).

Example:
```bash
curl -X POST http://localhost:8000/close_ticket \
  -d '{"ticket_id": 5, "resolution": "Replaced toner"}'
```

## assign_ticket
Assign a ticket to a technician.

Parameters:
- `ticket_id` – integer ID.
- `assignee_email` – technician email.
- `assignee_name` – optional technician name.

Example:
```bash
curl -X POST http://localhost:8000/assign_ticket \
  -d '{"ticket_id": 5, "assignee_email": "tech@example.com"}'
```

## add_ticket_message
Append a message to a ticket thread.

Parameters:
- `ticket_id` – integer ticket ID.
- `message` – text body.
- `sender_name` – name of the poster.
- `sender_code` – optional code for the sender.

Example:
```bash
curl -X POST http://localhost:8000/add_ticket_message \
  -d '{"ticket_id": 5, "message": "Checking the printer", "sender_name": "Alice"}'
```

## search_tickets
Keyword search across tickets.

Parameters:
- `query` – text query.
- `limit` – optional result limit (default 10).

Example:
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{"query": "printer"}'
```

## get_tickets_by_user
Retrieve tickets associated with a user.

Parameters:
- `identifier` – email or other user identifier.
- `skip` – optional offset (default 0).
- `limit` – optional maximum number (default 100).
- `status` – optional status filter.
- `filters` – optional additional filters.

Example:
```bash
curl -X POST http://localhost:8000/get_tickets_by_user \
  -d '{"identifier": "user@example.com", "status": "open"}'
```

## get_ticket_full_context
Return a ticket along with related labels and history.

Parameters:
- `ticket_id` – integer ID.

Example:
```bash
curl -X POST http://localhost:8000/get_ticket_full_context \
  -d '{"ticket_id": 5}'
```

## get_system_snapshot
Return a snapshot of overall system metrics.

Parameters: none.

Example:
```bash
curl -X POST http://localhost:8000/get_system_snapshot -d '{}'
```

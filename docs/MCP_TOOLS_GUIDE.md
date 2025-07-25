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

`updates` can include semantic fields such as `status`, `priority`,
`assignee_email`, `assignee_name`, `severity_id` or `resolution` to
close, assign or escalate a ticket in a single call.

Example:
```bash
curl -X POST http://localhost:8000/update_ticket \
  -d '{"ticket_id": 5, "updates": {"Assigned_Email": "tech@example.com"}}'
```


`updates` can include semantic fields such as `status`, `priority`,
`assignee_email`, `assignee_name`, `severity_id` or `resolution` to
close, assign or escalate a ticket in a single call. The former
`close_ticket` and `assign_ticket` tools have been removed; use these
fields with `update_ticket` instead.

Example – assign a technician:
```bash
curl -X POST http://localhost:8000/update_ticket \
  -d '{"ticket_id": 5, "updates": {"Assigned_Email": "tech@example.com"}}'
```

Example – close a ticket:
```bash
curl -X POST http://localhost:8000/update_ticket \
  -d '{"ticket_id": 5, "updates": {"Ticket_Status_ID": 4, "Resolution": "Replaced toner"}}'
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
- `created_after` – only tickets created on or after this ISO date.
- `created_before` – only tickets created on or before this ISO date.

Example:
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{"query": "printer", "created_after": "2024-01-01"}'
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

## get_open_tickets
List open tickets with optional filters.

Parameters:
- `days` – look back period (default 3650).
- `limit` – result limit (default 10).
- `skip` – result offset (default 0).
- `filters` – optional filter mapping.
- `sort` – optional list of columns to sort by.

Example:
```bash
curl -X POST http://localhost:8000/get_open_tickets \
  -d '{"days": 30, "limit": 20, "sort": ["Priority_Level"]}'
```

## get_analytics
Return analytics information. The `type` field selects the report.

Allowed types include:
- `status_counts`
- `site_counts`
- `technician_workload`
- `sla_breaches`
- `trends`

Parameters:
- `type` – report type.
- `params` – optional additional parameters for the chosen report.

Example:
```bash
curl -X POST http://localhost:8000/get_analytics \
  -d '{"type": "site_counts"}'
```

## get_reference_data
Return reference data such as sites, assets, vendors, categories, priorities, or statuses.

Parameters:
- `type` – one of `sites`, `assets`, `vendors`, `categories`, `priorities`, `statuses`.
- `limit` – optional limit (default 10).
- `skip` – optional offset (default 0).
- `filters` – optional filter mapping.
- `sort` – optional list of sort columns.
- `include_counts` – set to `true` to include open/total ticket counts.

Example:
```bash
curl -X POST http://localhost:8000/get_reference_data \
  -d '{"type": "sites", "include_counts": true}'
```


## get_ticket_full_context
Return a ticket along with messages and metadata.
User history and nested related tickets are omitted.

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


## advanced_search
Run a detailed ticket search with advanced options.

Parameters:
- `text_search` – optional text to search for.
- `search_fields` – list of fields to scan (default `["Subject", "Ticket_Body"]`).
- `created_after` – only tickets created on or after this timestamp.
- `created_before` – only tickets created on or before this timestamp.
- `status_filter` – list of statuses to include.
- `priority_filter` – list of priority IDs.
- `assigned_to` – restrict to these assignee emails or names.
- `unassigned_only` – set to `true` to return only unassigned tickets.
- `site_filter` – list of site IDs.
- `limit` – maximum results to return (default 100).
- `offset` – result offset (default 0).

Example:
```bash
curl -X POST http://localhost:8000/advanced_search \
  -d '{"text_search": "printer", "limit": 10}'
```

## escalate_ticket (removed)
Use `update_ticket` to change `Severity_ID` or assignment.

Example:
```bash
curl -X POST http://localhost:8000/update_ticket \
  -d '{"ticket_id": 123, "updates": {"Severity_ID": 1}}'
```


## sla_metrics
Retrieve SLA performance metrics for the helpdesk.

Parameters: none.

Example:
```bash
curl -X POST http://localhost:8000/sla_metrics -d '{}'
```

## bulk_update_tickets
Apply updates to multiple tickets.

Parameters:
- `ticket_ids` – list of ticket IDs.
- `updates` – fields to apply to each ticket.

Example:
```bash
curl -X POST http://localhost:8000/bulk_update_tickets \
  -d '{"ticket_ids": [1,2,3], "updates": {"Assigned_Email": "tech@example.com"}}'
```


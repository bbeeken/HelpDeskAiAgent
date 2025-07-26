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
Comprehensive ticket search with AI-optimized features and semantic filtering. Supports text queries, user filtering, date ranges, and intelligent result ranking.

### Parameters

#### Core Search
- `text` – Text to search for in ticket subject and body (supports partial matching)
- `query` – Alias for `text` parameter (backward compatibility)
- `user` – Filter by user email/name (searches contact, assignee, or message sender)
- `user_identifier` – Alias for `user` parameter (backward compatibility)

#### Time Filtering
- `days` – Limit to tickets created in the last N days (default: 30, 0 = all time)
- `created_after` – Only tickets created on or after this ISO datetime
- `created_before` – Only tickets created on or before this ISO datetime

#### Semantic Filters (AI-Friendly)
- `status` – Ticket status: `"open"`, `"closed"`, `"in_progress"`, `"resolved"`, `"waiting"`
- `priority` – Priority level: `"critical"`, `"high"`, `"medium"`, `"low"`
- `site_id` – Filter by site ID (1=Vermillion, 2=Steele, 3=Summit, etc.)
- `assigned_to` – Filter by assignee email address
- `unassigned_only` – If true, only return unassigned tickets (default: false)

#### Advanced Options
- `filters` – Additional filters object for complex scenarios
- `limit` – Maximum results to return (default: 10, max: 100)
- `skip` – Number of results to skip for pagination (default: 0)
- `sort` – Array of sort fields, prefix with "-" for descending (default: ["-Created_Date"])
- `include_relevance_score` – Include relevance scoring for text searches (default: true)
- `include_highlights` – Include search term highlighting (default: true)

### Response Fields

When a text query is used the response includes extra context:

- `relevance_score` – numeric ranking based on how well the query matches the
  ticket subject, body and category.
- `highlights` – object with `subject` and `body` snippets where matched terms
  are wrapped in `<em>` tags. Only returned when `include_highlights` is true.
- `metadata` – additional ticket info:
  - `age_days` – age of the ticket in days.
  - `is_overdue` – `true` if the ticket has been open for more than 24 hours.
  - `complexity_estimate` – `"high"` when the body exceeds 500 characters or the
    subject exceeds 100 characters, `"medium"` for bodies over 200 characters or
    subjects over 50 characters, otherwise `"low"`.

### Examples

#### Basic Text Search
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{"text": "printer error", "status": "open", "limit": 5}'
```

#### User-Specific Search
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{"user": "alice@heinzcorps.com", "status": "open"}'
```

#### Site and Priority Filtering
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{"site_id": 1, "priority": "high", "days": 7}'
```

#### Unassigned Ticket Triage
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{"status": "open", "unassigned_only": true, "sort": ["-Priority_Level"]}'
```

#### Date Range Search
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{
    "text": "network outage",
    "created_after": "2024-01-01T00:00:00Z",
    "created_before": "2024-12-31T23:59:59Z"
  }'
```

### Semantic Filter Mapping

Status Values

"open" → Maps to status IDs [1,2,4,5,6,8] (Open, In Progress, Waiting, etc.)
"closed" → Maps to status ID [3] (Closed/Resolved)
"in_progress" → Maps to status ID [2] (In Progress)
"waiting" → Maps to status ID [4] (Waiting on User)

Priority Values

"critical" → Severity_ID 1 (4-hour SLA)
"high" → Severity_ID 2 (24-hour SLA)
"medium" → Severity_ID 3 (3-day SLA)
"low" → Severity_ID 4 (1-week SLA)

Site Reference

| Site ID | Location        | Store ID |
| ------- | --------------- | -------- |
| 1       | Vermillion      | 1006     |
| 2       | Steele          | 1002     |
| 3       | Summit          | 1001     |
| 4       | SummitShop      | 1021     |
| 5       | Hot Springs     | 1009     |
| 6       | Corporate       | 1000     |
| 7       | Heinz Retail Estate | 2000 |

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

## advanced_search (removed)


Use `search_tickets` with a text string.


Example:
```bash
curl -X POST http://localhost:8000/search_tickets \
  -d '{"text": "printer", "limit": 10}'

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


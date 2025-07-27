# HelpDesk API Endpoints

This document lists the available HTTP endpoints provided by the HelpDesk service. Each endpoint includes a brief description and the HTTP method used.

## Ticket Endpoints

All ticket operations are prefixed with `/ticket` (singular). The old `/tickets`
paths remain for backwards compatibility but are no longer documented here.

- `GET /ticket/search` – search for tickets using query parameters.
- `POST /ticket/search` – search using a JSON payload.
- `GET /ticket/{ticket_id}` – retrieve a single ticket.
- `GET /ticket` – list tickets with optional filters.
- `GET /ticket/expanded` – alias for listing expanded tickets.
- `GET /ticket/by_user` – list tickets related to a user.
- `POST /ticket` – create a ticket.
- `POST /ticket/json` – create a ticket from JSON.
- `PUT /ticket/{ticket_id}` – update an existing ticket.
- `PUT /ticket/json/{ticket_id}` – update a ticket using JSON.
- `GET /ticket/{ticket_id}/messages` – list ticket messages.
- `POST /ticket/{ticket_id}/messages` – add a message to a ticket.

## Lookup Endpoints

- `GET /lookup/assets` – list assets.
- `GET /lookup/asset/{asset_id}` – retrieve an asset.
- `GET /lookup/vendors` – list vendors.
- `GET /lookup/vendor/{vendor_id}` – retrieve a vendor.
- `GET /lookup/sites` – list sites.
- `GET /lookup/site/{site_id}` – retrieve a site.
- `GET /lookup/categories` – list ticket categories.
- `GET /lookup/statuses` – list ticket statuses.
- `GET /lookup/ticket/{ticket_id}/attachments` – list ticket attachments.

## Analytics Endpoints

- `GET /analytics/status` – count tickets by status.
- `GET /analytics/open_by_site` – count open tickets by site.
- `GET /analytics/open_by_assigned_user` – count open tickets by technician.
- `GET /analytics/staff_report` – summary report for a technician.
- `GET /analytics/waiting_on_user` – tickets waiting on users.
- `GET /analytics/sla_breaches` – tickets breaching the SLA.
- `GET /analytics/trend` – ticket trend data.

## Agent Enhanced Endpoints

- `GET /agent/ticket/{ticket_id}/full-context` – full context for a ticket.
- `GET /agent/system/snapshot` – system state snapshot.
- `GET /agent/user/{user_email}/complete-profile` – user profile information.
- `POST /agent/tickets/query-advanced` – execute an advanced ticket query.
- `POST /agent/operation/validate` – validate an operation.
- `POST /agent/ticket/{ticket_id}/execute-operation` – run a ticket operation.

## On-Call

- `GET /oncall` – return the current on‑call shift.

## Miscellaneous

- `GET /tools` – list available MCP tools.
- `GET /health` – service health check.
- `GET /health/mcp` – MCP subsystem health.
- `GET /` – API root.

### MCP Tool Routes

The following POST endpoints are generated from the MCP tools. Each expects a
JSON body matching the tool's schema. See
[MCP_TOOLS_GUIDE.md](MCP_TOOLS_GUIDE.md) for a full description of each tool.

- `POST /get_ticket` – Get a ticket by ID. Example: `{"ticket_id": 123}`
- `POST /list_tickets` – List recent tickets. Example: `{"limit": 5}`
- `POST /create_ticket` – Create a ticket. Example: see `TicketCreate` schema
- `POST /update_ticket` – Update a ticket. Example: `{"ticket_id": 1, "updates": {}}`
- `POST /add_ticket_message` – Add a message to a ticket.
- `POST /search_tickets` – Search tickets. Example: `{"text": "printer", "created_after": "2024-01-01"}`. The deprecated
  `/search_tickets_advanced` route was removed.
- `POST /update_ticket` – Update a ticket or close/assign by modifying fields.
- `POST /get_tickets_by_user` – Tickets for a user. Example: `{"identifier": "user@example.com"}`

- `POST /get_open_tickets` – List open tickets. Example: `{"days": 30}`
- `POST /get_analytics` – Analytics reports. Example: `{"type": "site_counts"}`
- `POST /get_reference_data` – Reference data lookup. Example: `{"type": "sites"}`

- `POST /get_ticket_full_context` – Full context for a ticket without user history or nested related tickets. Example: `{"ticket_id": 123}`
- `POST /get_system_snapshot` – System snapshot. Example: `{}`

- `POST /advanced_search` – Advanced ticket search. Example: `{"text_search": "printer"}`

- `POST /sla_metrics` – SLA metrics summary. Example: `{}`
- `POST /bulk_update_tickets` – Bulk ticket updates. Example: `{"ticket_ids": [1,2], "updates": {}}`


Endpoints under `/mcp-tools` are also exposed as HTTP routes with the same names as the MCP tools. Refer to the OpenAPI schema or `/docs` endpoint when running the application for the full specification.

## Ticket Schemas

### TicketCreate

Use this schema when creating a ticket. The server automatically populates `Created_Date` so it should be omitted from the payload. All other fields match the database columns and most are optional. If `Ticket_Status_ID` is not supplied it defaults to `1` (Open).

Example:

```json
{
  "Subject": "Printer not working",
  "Ticket_Body": "The office printer is jammed and displays error code 34.",
  "Ticket_Contact_Name": "Jane Doe",
  "Ticket_Contact_Email": "jane@example.com",
  "Asset_ID": 5,
  "Site_ID": 2,
  "Ticket_Category_ID": 1
}
```

Another example showing assignment and severity:

```json
{
  "Subject": "Website down",
  "Ticket_Body": "The main website returns a 500 Internal Server Error.",
  "Ticket_Contact_Name": "Alice Admin",
  "Ticket_Contact_Email": "alice@example.com",
  "Assigned_Name": "Bob Ops",
  "Assigned_Email": "bob.ops@example.com",
  "Ticket_Status_ID": 1,
  "Site_ID": 3,
  "Severity_ID": 3
}
```

### TicketUpdate

This schema is used to partially update an existing ticket. Provide only the fields you want to change; omitted fields remain unchanged. Unknown fields are rejected and `Created_Date` cannot be updated.

Example payloads:

```json
{"Subject": "Updated"}
```

```json
{"Assigned_Name": "Agent", "Ticket_Status_ID": 2}
```

```json
{"Ticket_Status_ID": 3}
```

### TicketExpandedOut

`TicketExpandedOut` extends `TicketOut` with additional labels and timestamps.
Fields include:

- `status_label` (maps to `Ticket_Status_Label`)
- `Site_Label`
- `Site_ID`
- `Asset_Label`
- `category_label` (maps to `Ticket_Category_Label`)
- `Assigned_Vendor_Name`
- `Priority_Level`
- `Closed_Date`
- `LastModified`
- `LastModfiedBy`

Example:

```json
{
  "Ticket_ID": 1,
  "Subject": "Printer not working",
  "status_label": "Open",
  "Site_Label": "HQ",
  "Site_ID": 2,
  "Priority_Level": "High",
  "Closed_Date": null,
  "LastModified": null,
  "LastModfiedBy": null
}
```

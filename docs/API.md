# HelpDesk API Endpoints

This document lists the available HTTP endpoints provided by the HelpDesk service. Each endpoint includes a brief description and the HTTP method used.

## Ticket Endpoints

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
JSON body matching the tool's schema.

- `POST /get_ticket` – Get a ticket by ID. Example: `{"ticket_id": 123}`
- `POST /list_tickets` – List recent tickets. Example: `{"limit": 5}`
- `POST /tickets_by_user` – List tickets for a user. Example: `{"identifier": "user@example.com"}`
- `POST /by_user` – Alias of `tickets_by_user`.
- `POST /open_by_site` – Open tickets by site. Example: `{}`
- `POST /open_by_assigned_user` – Open tickets by technician. Example: `{"filters": {}}`
- `POST /tickets_by_status` – Ticket counts by status. Example: `{}`
- `POST /ticket_trend` – Ticket trend information. Example: `{"days": 7}`
- `POST /waiting_on_user` – Tickets waiting on user. Example: `{}`
- `POST /sla_breaches` – Count SLA breaches. Example: `{"days": 2}`
- `POST /staff_report` – Technician ticket report. Example: `{"assigned_email": "tech@example.com"}`
- `POST /get_open_tickets` – List open tickets. Example: `{"days": 30, "limit": 20, "skip": 0, "sort": ["Priority_Level"]}`
- `POST /tickets_by_timeframe` – Tickets filtered by status and age. Example: `{"days": 7}`
- `POST /search_tickets` – Search tickets. Example: `{"query": "printer"}`
- `POST /list_sites` – List sites. Example: `{"limit": 10, "filters": {}, "sort": ["Label"]}`
- `POST /list_assets` – List assets. Example: `{"limit": 10, "filters": {}, "sort": ["Label"]}`
- `POST /list_vendors` – List vendors. Example: `{"limit": 10, "filters": {}, "sort": ["Name"]}`
- `POST /list_categories` – List categories. Example: `{"filters": {}}`
- `POST /get_ticket_full_context` – Full context for a ticket. Example: `{"ticket_id": 123}`
- `POST /get_system_snapshot` – System snapshot. Example: `{}`

Endpoints under `/mcp-tools` are also exposed as HTTP routes with the same names as the MCP tools. Refer to the OpenAPI schema or `/docs` endpoint when running the application for the full specification.

## Ticket Schemas

### TicketCreate

Use this schema when creating a ticket. The server automatically populates `Created_Date` so it should be omitted from the payload. All other fields match the database columns and most are optional.

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

This schema is used to partially update an existing ticket. Provide only the fields you want to change; omitted fields remain unchanged. `Created_Date` cannot be updated.

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

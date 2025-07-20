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

Endpoints under `/mcp-tools` are also exposed as HTTP routes with the same names as the MCP tools. Refer to the OpenAPI schema or `/docs` endpoint when running the application for the full specification.

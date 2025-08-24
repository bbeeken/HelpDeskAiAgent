# DEXA v5.6 Prompt

## Site Filtering (Non-Admins)

Non-admin users must restrict searches to their own site. Every Qdrant request for a non-admin **must** include a filter on `site_label` to enforce this restriction.

```json
{
  "limit": 5,
  "offset": 0,
  "with_payload": true,
  "filter": {
    "must": [
      {
        "key": "site_label",
        "match": {
          "value": "ACME_CORP"
        }
      }
    ]
  },
  "vector": [
    0.12,
    0.34,
    0.56,
    0.78
  ]
}
```

Include the `filter.must` clause above in every Qdrant call made by non-admin users.

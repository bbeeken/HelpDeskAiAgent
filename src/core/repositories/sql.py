CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL = """
CREATE VIEW V_Ticket_Master_Expanded AS
SELECT t.Ticket_ID,
       t.Subject,
       t.Ticket_Body,
       t.Ticket_Status_ID,
       ts.Label AS Ticket_Status_Label,
       t.Ticket_Contact_Name,
       t.Ticket_Contact_Email,
       t.Asset_ID,
       a.Label AS Asset_Label,
       t.Site_ID,
       s.Label AS Site_Label,
       t.Ticket_Category_ID,
       c.Label AS Ticket_Category_Label,
       t.Created_Date,
       t.Version,
       t.Assigned_Name,
       t.Assigned_Email,
       t.Severity_ID,
       t.Assigned_Vendor_ID,
       t.Closed_Date,
       t.LastModified,
       t.LastModfiedBy,
       v.Name AS Assigned_Vendor_Name,
       t.Resolution,
       p.Level AS Priority_Level
FROM Tickets_Master t
LEFT JOIN Ticket_Status ts ON ts.ID = t.Ticket_Status_ID
LEFT JOIN Assets a ON a.ID = t.Asset_ID
LEFT JOIN Sites s ON s.ID = t.Site_ID
LEFT JOIN Ticket_Categories c ON c.ID = t.Ticket_Category_ID
LEFT JOIN Vendors v ON v.ID = t.Assigned_Vendor_ID
LEFT JOIN Priority_Levels p ON p.ID = t.Severity_ID
"""

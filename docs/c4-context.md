# Etsy Panel C4 Context Diagram

## Purpose

This document shows the system context for Etsy Panel. It explains who uses the system and which external systems Etsy Panel depends on.

## System Context

```mermaid
C4Context
    title Etsy Panel - System Context

    Person(shop_owner, "Shop Owner", "Uses Etsy Panel to monitor listings, orders, customers, shipments, and inventory.")
    Person(admin_user, "Admin User", "Maintains inventory mappings, stock buckets, recipes, and operational data through Django admin.")

    System(etsy_panel, "Etsy Panel", "Django web application for Etsy shop operations, order tracking, listing sync, customer tracking, and inventory deduction.")

    System_Ext(etsy_api, "Etsy API", "Provides shop, active listing, listing inventory, receipt, order item, buyer, and shipment data.")
    System_Ext(shipentegra_api, "Shipentegra API", "Provides shipment tracking activity and delivery status by tracking number.")

    Rel(shop_owner, etsy_panel, "Uses through browser")
    Rel(admin_user, etsy_panel, "Maintains data through Django admin")

    Rel(etsy_panel, etsy_api, "Fetches listings, listing variations, receipts, orders, and OAuth tokens", "HTTPS / OAuth")
    Rel(etsy_panel, shipentegra_api, "Fetches shipment tracking status", "HTTPS")
```

## System Context Flowchart

This version is easier to render in standard Mermaid preview tools.

```mermaid
flowchart LR
    shop_owner["Shop Owner<br/>Uses Etsy Panel to monitor listings, orders, customers, shipments, and inventory."]
    admin_user["Admin User<br/>Maintains inventory mappings, stock buckets, recipes, and operational data through Django admin."]

    etsy_panel["Etsy Panel<br/>Django web application for Etsy shop operations, order tracking, listing sync, customer tracking, and inventory deduction."]

    etsy_api["Etsy API<br/>Provides shop, active listing, listing inventory, receipt, order item, buyer, and shipment data."]
    shipentegra_api["Shipentegra API<br/>Provides shipment tracking activity and delivery status by tracking number."]

    shop_owner -->|"Uses through browser"| etsy_panel
    admin_user -->|"Maintains data through Django admin"| etsy_panel

    etsy_panel -->|"Fetches listings, listing variations, receipts, orders, and OAuth tokens<br/>HTTPS / OAuth"| etsy_api
    etsy_panel -->|"Fetches shipment tracking status<br/>HTTPS"| shipentegra_api
```

## Main Responsibilities

Etsy Panel is responsible for:

- Connecting a user account to Etsy.
- Syncing active Etsy listings and listing variations.
- Syncing Etsy receipts into local orders and order items.
- Tracking buyers and shipment information.
- Matching order items to inventory products and variations.
- Deducting stock from inventory buckets when shipped orders qualify.
- Recording stock changes in stock movement history.

## External Systems

### Etsy API

Used by:

- `etsy.client.EtsyClient`
- `listings.services.sync_active_listings`
- `orders.services.sync_orders`

Data fetched:

- User shops
- Active listings
- Listing images
- Listing inventory and variation data
- Shop receipts and order transactions
- OAuth access and refresh tokens

### Shipentegra API

Used by:

- `orders.shipentegra.ShipentegraClient`
- `orders.services.fetch_ship_status`

Data fetched:

- Shipment activity
- Carrier status
- Delivery status
- Delivery date or last activity date

## Important Notes

- Inventory product records are local application data, not automatically created by the current Etsy order sync flow.
- Stock deduction depends on inventory mapping being complete: product, variation, recipe, and stock bucket must exist.
- Stock movement records are the audit trail for automatic and manual inventory changes.

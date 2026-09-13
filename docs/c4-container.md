# Etsy Panel C4 Container Diagram

## Purpose

This document shows the main deployable/runtime containers inside the Etsy Panel system boundary and the external systems they communicate with.

## Container Diagram

```mermaid
C4Container
    title Etsy Panel - Container Diagram

    Person(shop_owner, "Shop Owner", "Uses Etsy Panel through a browser.")
    Person(admin_user, "Admin User", "Maintains operational data through Django admin.")

    System_Boundary(etsy_panel_boundary, "Etsy Panel") {
        Container(web_app, "Django Web Application", "Python / Django", "Serves HTML pages, handles authentication, sync actions, listing views, order tracking, customer views, and inventory operations.")
        ContainerDb(database, "Application Database", "SQLite locally / DATABASE_URL in deployed environments", "Stores users, Etsy accounts, listings, listing variations, customers, orders, shipments, inventory products, stock buckets, recipes, and stock movements.")
        Container(cache, "Django Cache", "Django cache backend", "Caches Shipentegra access token for shipment tracking requests.")
        Container(static_assets, "Static Assets", "Django staticfiles / WhiteNoise when installed", "Serves CSS, JavaScript, images, and frontend assets.")
    }

    System_Ext(etsy_api, "Etsy API", "OAuth and Etsy shop/listing/order APIs.")
    System_Ext(shipentegra_api, "Shipentegra API", "Shipment tracking and logistics status API.")

    Rel(shop_owner, web_app, "Uses", "HTTPS")
    Rel(admin_user, web_app, "Uses Django admin", "HTTPS")

    Rel(web_app, database, "Reads and writes application data", "Django ORM")
    Rel(web_app, cache, "Stores and reads shipment API token", "Django cache API")
    Rel(web_app, static_assets, "Serves frontend files")

    Rel(web_app, etsy_api, "Connects account, refreshes OAuth token, syncs listings and orders", "HTTPS / OAuth")
    Rel(web_app, shipentegra_api, "Fetches shipment tracking activity", "HTTPS")
```

## Container Diagram Flowchart

This version is easier to render in standard Mermaid preview tools.

```mermaid
flowchart LR
    shop_owner["Shop Owner"]
    admin_user["Admin User"]

    subgraph etsy_panel["Etsy Panel"]
        web_app["Django Web Application<br/>Python / Django<br/>HTML pages, auth, sync actions, listings, orders, customers, inventory"]
        database[("Application Database<br/>SQLite locally / DATABASE_URL in deployed environments<br/>Users, Etsy accounts, listings, orders, shipments, inventory, stock movements")]
        cache[("Django Cache<br/>Caches Shipentegra access token")]
        static_assets["Static Assets<br/>Django staticfiles / WhiteNoise when installed"]
    end

    etsy_api["Etsy API<br/>OAuth, shop, listing, inventory, receipt APIs"]
    shipentegra_api["Shipentegra API<br/>Shipment tracking activity"]

    shop_owner -->|"Uses through browser"| web_app
    admin_user -->|"Uses Django admin"| web_app

    web_app -->|"Django ORM"| database
    web_app -->|"Django cache API"| cache
    web_app -->|"Serves frontend files"| static_assets

    web_app -->|"Sync listings, variations, receipts, orders<br/>HTTPS / OAuth"| etsy_api
    web_app -->|"Fetch tracking status<br/>HTTPS"| shipentegra_api
```

## Web Application Responsibilities

The Django web application contains these application modules:

- `accounts`: User account and authentication-related app structure.
- `etsy`: Etsy OAuth connection, token handling, and API client.
- `listings`: Active listing sync, listing image sync, and listing variation sync.
- `orders`: Receipt sync, order item sync, shipment tracking, and order status management.
- `customers`: Buyer/customer views and customer records.
- `inventory`: Inventory products, stock buckets, variation recipes, stock movements, and manual stock adjustment.
- `core`: Project settings, root URLs, dashboard, WSGI, and ASGI entrypoints.

## Database Responsibilities

The application database stores the persistent business state:

- Auth users and sessions.
- Connected Etsy account credentials and shop identifiers.
- Synced listings and listing variations.
- Buyers and customer data.
- Orders, order items, and shipments.
- Inventory products, stock buckets, variation recipes, and stock movements.

## Important Boundaries

- Etsy Panel owns the local operational state. Etsy remains the source for listing and receipt data.
- Inventory mapping is local business data. The current order sync flow does not automatically create missing inventory products.
- Shipment tracking status comes from Shipentegra, but order and shipment records are stored locally.
- Stock deduction is performed inside the Django web application and persisted through `StockBucket` and `StockMovement`.

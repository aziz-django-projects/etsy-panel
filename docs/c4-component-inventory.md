# Etsy Panel C4 Component Diagram — Inventory

Bu diyagram, [container diyagramındaki](c4-container.md) `Django Web Application` container'ının yalnızca stok yönetimiyle ilgili bileşenlerini gösterir. `Inventory` bağımsız bir container değildir; Django uygulaması içindeki bir işlev alanıdır. Yönlendirme ve sipariş eşitleme, bu alanla etkileşen aynı container içindeki bileşenlerdir.

```mermaid
C4Component
    title Etsy Panel — Inventory Component Diagram

    Person(shop_owner, "Shop Owner", "Stokları görüntüler ve elle değiştirir.")
    ContainerDb(database, "Application Database", "SQLite / DATABASE_URL", "İlan, sipariş, envanter ve stok hareketi kayıtlarını tutar.")

    Container_Boundary(web_app, "Django Web Application") {
        Component(root_routing, "Root Routing", "core.urls + inventory.urls", "Stok sayfası ve ayarlama isteklerini yönlendirir.")
        Component(inventory_home, "Inventory Page View", "inventory.views.inventory_home", "Kullanıcıya ait aktif ürünleri ve stok kovalarını listeler; ilan görsellerini ekler.")
        Component(manual_adjustment, "Manual Stock Adjustment View", "inventory.views.adjust_bucket", "Artı/eksi birimlik stok değişikliğini ve manuel hareket kaydını işler.")
        Component(stock_transition, "Order Stock Transition Service", "inventory.services.apply_stock_for_order_transition", "Sipariş durumuna göre reçete eşleşmelerinden stok düşer veya iptalde iade eder.")
        Component(order_sync, "Order Sync Service", "orders.services", "Sipariş eşitlemesi sonrasında stok geçişini tetikler.")
        Component(listing_sync, "Listing Sync Service", "listings.services.sync_active_listings", "Etsy katalog verisini eşitler ve etkinse envanter eşlemesini tetikler.")
        Component(catalog_sync, "Inventory Catalogue Reconciliation", "inventory.catalog_sync.reconcile_listing", "Ürün ve varyasyon adları/kimliklerini günceller; reçeteleri korur.")
        Component(inventory_template, "Inventory Template", "templates/inventory/home.html", "Ürünleri, stok kovalarını ve ayarlama kontrollerini HTML olarak sunar.")
    }

    Rel(shop_owner, root_routing, "Stok sayfasını açar veya miktarı değiştirir", "HTTPS GET / POST")
    Rel(root_routing, inventory_home, "GET /inventory/ isteğini yönlendirir")
    Rel(root_routing, manual_adjustment, "Stok ayarlama POST isteğini yönlendirir")
    Rel(inventory_home, database, "InventoryProduct, StockBucket ve Listing görselini okur", "Django ORM")
    Rel(inventory_home, inventory_template, "Stok sayfasını oluşturur", "Django render")
    Rel(listing_sync, catalog_sync, "Etkinse başarılı ilan eşitlemesinden sonra çağırır")
    Rel(catalog_sync, database, "InventoryProduct ve InventoryVariation eşlemelerini yazar", "Django ORM / transaction")
    Rel(manual_adjustment, database, "StockBucket miktarını günceller; manual StockMovement oluşturur", "Django ORM / transaction")
    Rel(order_sync, stock_transition, "Sipariş durumu değişimini bildirir")
    Rel(stock_transition, database, "InventoryVariation ve InventoryRecipeItem eşleştirir; StockBucket ve StockMovement günceller", "Django ORM / transaction")
```

## Akış

1. Kullanıcı `GET /inventory/` isteği gönderdiğinde `inventory_home`, o kullanıcıya ait aktif `InventoryProduct` ve `StockBucket` kayıtlarını okur. İlgili yerel `Listing` görsellerini ekleyip `inventory/home.html` sayfasını oluşturur.
2. Kullanıcı `POST /inventory/adjust/<bucket_id>/` ile `+1` veya `-1` gönderdiğinde `adjust_bucket`, kullanıcının aktif stok kovasını bulur. Geçerli değişiklikte miktarı günceller ve aynı işlem içinde `manual` nedenli bir `StockMovement` oluşturur. İstek türüne göre JSON yanıtı verir veya stok sayfasına yönlendirir.
3. `orders.services` sipariş eşitlemesi sonrasında `apply_stock_for_order_transition` hizmetini çağırır. Sipariş `shipped` durumuna yeni geçtiğinde hizmet, sipariş kalemini aktif envanter varyasyonuyla ve reçete satırlarıyla eşleştirir; ilgili kovalardan stok düşüp `ship_deduct` hareketlerini kaydeder. Sipariş yeni iptal edildiğinde önceden düşülmüş miktarı `cancel_restock` hareketleriyle geri ekler.
4. İlan eşitlemesi başarılı olduğunda ve `INVENTORY_CATALOG_SYNC_ENABLED=1` ise katalog eşleştirme hizmeti envanter adlarını ve Etsy kimliklerini günceller. Yeni varyasyonlar reçetesiz oluşturulur ve envanter sayfasında eşleme beklediği gösterilir; kovalar ve reçeteler otomatik oluşturulmaz.

Manuel stok ayarı doğrudan view içinde yapılır; otomatik sipariş geçişleri `inventory.services` içindedir. Sipariş kalemi için uygun varyasyon veya reçete bulunmazsa otomatik stok düşümü yapılmaz.

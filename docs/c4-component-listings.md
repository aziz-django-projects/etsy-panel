# Etsy Panel C4 Component Diagram — Listings

Bu diyagram, [container diyagramındaki](c4-container.md) `Django Web Application` container'ının yalnızca ilan yönetimiyle ilgili bileşenlerini gösterir. `Listings` bağımsız bir container değildir; Django uygulaması içindeki bir işlev alanıdır. Diyagramdaki yönlendirme ve Etsy istemcisi aynı container'ın, ilan akışında kullanılan ortak bileşenleridir.

```mermaid
C4Component
    title Etsy Panel — Listings Component Diagram

    Person(shop_owner, "Shop Owner", "İlanları görüntüler ve eşitlemeyi başlatır.")
    ContainerDb(database, "Application Database", "SQLite / DATABASE_URL", "EtsyAccount, Listing ve ListingVariation kayıtlarını tutar.")
    System_Ext(etsy_api, "Etsy API", "Mağaza, aktif ilan, görsel ve ilan envanteri verilerini sağlar.")

    Container_Boundary(web_app, "Django Web Application") {
        Component(root_routing, "Root Routing", "core.urls + listings.urls", "/listings/ isteğini ListingsHomeView'a yönlendirir.")
        Component(listings_view, "Listings View", "listings.views.ListingsHomeView", "Kullanıcının ilanlarını gösterir; POST isteğinde eşitlemeyi başlatır.")
        Component(tracking_view, "Stock Tracking Selection", "listings.views.set_inventory_tracking", "Seçilen ilanın yerel stok takibini açar veya kapatır.")
        Component(listing_sync, "Listing Sync Service", "listings.services.sync_active_listings", "Aktif ilanları, görselleri ve varyasyonları Etsy'den alıp yerel kayıtlarla eşitler.")
        Component(inventory_catalog_sync, "Inventory Catalogue Reconciliation", "inventory.catalog_sync.reconcile_listing", "Etkinse ilan adını ve varyasyon kimliklerini yerel envanter eşlemelerine taşır.")
        Component(etsy_client, "Etsy Client", "etsy.client.EtsyClient", "Etsy API çağrılarını ve erişim tokenı yenilemeyi yönetir.")
        Component(listings_template, "Listings Template", "templates/listings/home.html", "İlan listesini ve işlem mesajlarını HTML olarak sunar.")
    }

    Rel(shop_owner, root_routing, "İlan sayfasını açar veya eşitlemeyi başlatır", "HTTPS GET / POST")
    Rel(root_routing, listings_view, "İsteği yönlendirir")
    Rel(root_routing, tracking_view, "İlana ait stok takibi POST isteğini yönlendirir")
    Rel(tracking_view, database, "InventoryProduct kaydını oluşturur veya etkinliğini değiştirir", "Django ORM")
    Rel(listings_view, database, "Kullanıcıya ait Listing ve ListingVariation kayıtlarını okur", "Django ORM")
    Rel(listings_view, listings_template, "İlan listesini oluşturur", "Django render")
    Rel(listings_view, listing_sync, "POST ile eşitlemeyi çağırır")
    Rel(listing_sync, database, "EtsyAccount okur/günceller; Listing ve ListingVariation yazar", "Django ORM")
    Rel(listing_sync, etsy_client, "Mağaza, aktif ilan, görsel ve envanter verilerini ister")
    Rel(listing_sync, inventory_catalog_sync, "Başarılı ilan eşitlemesinden sonra çağırır")
    Rel(inventory_catalog_sync, database, "InventoryProduct ve InventoryVariation eşlemelerini günceller", "Django ORM")
    Rel(etsy_client, etsy_api, "API çağrıları ve token yenileme", "HTTPS / OAuth")
    Rel(etsy_client, database, "Yenilenen EtsyAccount tokenlarını kaydeder", "Django ORM")
```

## Akış

1. Kullanıcı `GET /listings/` isteği gönderdiğinde `ListingsHomeView`, yalnızca o kullanıcıya ait yerel ilanları ve görünür varyasyonları okuyup `listings/home.html` ile gösterir.
2. Kullanıcı aynı adrese `POST` isteği gönderdiğinde view, `sync_active_listings` hizmetini çağırır. Hizmet, gerekirse mağaza kimliğini bulur; aktif ilanları sayfalar halinde, görselleri ve envanteri toplu olarak Etsy istemcisi üzerinden çeker.
3. Hizmet `Listing` ve `ListingVariation` kayıtlarını günceller veya oluşturur. Varyasyon eşitleme hatalarını ilan bazında kaydedip diğer ilanlarla devam eder; sonucu view'a döndürür. View kullanıcıya işlem mesajı göstererek ilan sayfasına yönlendirir.
4. Kullanıcı bir ilanda stok takibini başlattığında `InventoryProduct` oluşturulur veya yeniden etkinleştirilir. Takip durdurulduğunda kayıt pasif olur; stok kovaları, reçeteler ve hareket geçmişi korunur.
5. `INVENTORY_CATALOG_SYNC_ENABLED=1` olduğunda aynı Etsy verisiyle yalnızca stok takibi açık ürünlerin ve varyasyonların adları/kimlikleri eşitlenir. Stok kovaları, reçeteler ve stok hareketleri değiştirilmez. Eksik Etsy envanter yanıtı mevcut varyasyonları silmez.

Bu eşitleme, Etsy'de artık aktif olmayan ilanları yerel veritabanından silmez ve Etsy tarafındaki stok miktarını değiştirmez.

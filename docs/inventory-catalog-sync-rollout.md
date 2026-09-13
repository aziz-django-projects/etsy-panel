# Inventory catalogue sync: development, release and rollback

`Sync Now` on the Listings page updates all active Etsy listings, but reconciles
`InventoryProduct` and `InventoryVariation` only for listings explicitly selected
for stock tracking. This catalogue reconciliation is **off by default**.
Set `INVENTORY_CATALOG_SYNC_ENABLED=1` in the application's environment and
restart the application to enable it; set the value to `0` and restart to stop
future inventory catalogue updates. Disabling it does not undo past updates.

Choose **Stok takibini başlat** on a listing card to create or reactivate its
local `InventoryProduct`, then run **Sync Now** to copy its variations. Existing
active inventory products remain selected. Choose **Stok takibini durdur** to
deactivate a product: future catalogue updates and new order stock deductions
for it stop, while its buckets, recipes, quantities and movement history remain
in the database. Reactivating it resumes tracking and reuses those records.
The global switch controls catalogue reconciliation; it does not override the
per-product stock-tracking selection.

For selected products, sync updates catalogue names and Etsy variation IDs,
creates missing variations, and marks missing Etsy variations unavailable.
Unselected listings never create inventory products during Sync Now.
It never creates recipes or stock buckets and never changes quantities or stock
movements. A new variation without a recipe is shown as needing stock setup.
Existing variation records and recipes are retained when Etsy no longer sends
the variation. The legacy `sync_inventory_variation_ids` command is kept during
the rollout; remove it only after existing mappings have been checked in
production.

## Development and staging

1. Confirm that `DATABASE_URL` points to a disposable development or staging
   database. The repository's local `.env` may point to PostgreSQL; do not
   assume it is a local database. Activate the project's virtual environment,
   then run `python manage.py test` and
   `python manage.py makemigrations --check --dry-run`.
2. Make a restorable copy of that development/staging database. Apply the new
   migration with `python manage.py migrate` only after confirming the target.
3. Enable `INVENTORY_CATALOG_SYNC_ENABLED=1` and restart. On Listings, select a
   sample listing with **Stok takibini başlat**. Change its Etsy title and
   variation label, then use **Sync Now**.
   Check that inventory names update and that its bucket quantities and recipes
   are unchanged.
4. Add a new Etsy variation. Sync again; verify it appears on the inventory
   page as needing a recipe. Run Sync Now a second time and check that no
   duplicate product or variation is created. Complete the recipe in admin.
5. Test a shipped order and a canceled order against a mapped variation. Verify
   that stock is deducted once and restored once. An unmapped variation should
   not deduct stock.
6. Leave another listing unselected, sync it and confirm no inventory product
   is created for it. Stop tracking the sample product and confirm its stock
   records remain intact; reactivate it if tracking is still needed.

## Production release

1. Keep the migration in version control and keep the feature switch at `0`.
   Before deployment, take a production database backup and confirm how it
   would be restored. Deploy the migration and code while the switch is off.
2. Check that the site, Listings Sync Now, and inventory page still work. Then
   set the switch to `1`, restart, select a sample product, and sync one account.
   Review product and variation counts, pending recipes, and unchanged stock
   quantities. If an earlier version already created unwanted products, stop
   tracking each one from Listings; this retains its history for review.
3. Keep the old migration history and legacy mapping command through the
   observation period. Remove obsolete code in a later release after the new
   mapping is verified.

## If something goes wrong

1. Set `INVENTORY_CATALOG_SYNC_ENABLED=0` and restart. This immediately stops
   further catalogue-to-inventory reconciliation without touching stock.
2. Fix wrong names or mappings in a follow-up change. If code rollback is
   needed, revert the logic change through a GitHub pull request and deploy
   that revision, while **retaining the already-applied migration**. An easy
   GitHub rollback needs the schema migration and feature logic in separate
   pull requests or commits.
3. GitHub does not restore database contents. Use the database backup only
   after assessing any orders or stock changes made since it was taken; a full
   restore would also discard those later changes.

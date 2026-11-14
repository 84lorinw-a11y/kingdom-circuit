# Selective daily publication

The daily workflow still discovers shows, preserves accepted records, archives completed dates and recalculates the current calendar. It reuses unchanged rendering work to avoid repeatedly generating the same pages and encoding the same artwork.

## Reusable work

1. Event and artist page generation uses a cache at its original rendering stage. Keys cover current event facts, artist details, ordered relationships, canonical and legacy paths, rendering context and code. Current page inventories are always recomputed.
2. Approved SEO rendering reuses unchanged page bodies and cards. Page heads, related links, date filtering and route inventories still run with current data.
3. Image derivatives use the full original image hash and encoding recipe. Recipe identity includes sizes, quality, portrait configuration, implementation and encoder versions. Every reused derivative is checked for its hash, size and decoded dimensions.

The cache is disposable. Missing, damaged or unavailable entries cause ordinary generation. A template, relevant record or image change invalidates its previous result. A final published site is never used as input to an earlier presentation stage.

## Production controls

The workflow restores the cache outside the source checkout and public artifact with `KC_BUILD_CACHE_DIR`. Local builds must also use a cache directory outside the checkout because the existing source copier includes general project files. It saves reusable work only after the exact live release and published calendar checks pass. Cache service failures do not block normal generation.

All existing source, Canadian booking, private admission, URL continuity, image completeness, event schema, current count and artist Next Show checks remain active. The complete final artifact is audited and published together through GitHub Pages. Reusing generated work does not change public URLs or claim that every page was updated today.

## Evidence

`incremental-page-build.json` records cache usage by rendering stage. `image-cache-report.json`, stored beside the image cache outside the site, records source counts, reused derivatives, misses, invalid entries and duration. Both reports are retained with publication evidence. The public image manifest continues to describe the complete output inventory.

Before a change to this mechanism ships, compare a fresh build with a build using a populated cache. Pages, images, data and navigation must agree. Test relevant record changes, date rollover, removed routes, changed artwork, changed recipes and corrupt entries. Cache hits never replace the final publication checks.

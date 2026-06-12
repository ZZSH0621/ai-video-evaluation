# Archived Files

## `gen_signed_urls.py`
**Archived**: 2026-06-12  
**Reason**: Replaced by Cloudflare Worker dynamic signing scheme.

Previously this script regenerated 1-year OSS signed URLs directly in `video_map.js` and `index.html` using `oss2` SDK. This exposed OSS credentials in the HTML source.

Now replaced by:
- `worker/index.js` — Cloudflare Worker that generates 10-minute signed URLs on the fly
- `generate_video_map.py` — Now generates Worker proxy URLs instead of OSS direct URLs

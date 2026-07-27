# Caddx Ground Configuration — local downloads

Windows release assets from [Caddx_Ground_Configuration_Release](https://github.com/CaddxFPV-Tech/Caddx_Ground_Configuration_Release/releases).

```bash
# Refresh manifest + download all releases
python3 fpv-library/scripts/sync_caddx_ground_config.py --download

# Check GitHub for new releases (CI runs this daily)
python3 fpv-library/scripts/sync_caddx_ground_config.py --check-only
```

Layout: `v0.3.3/CaddxGroundConfiguration-win-Setup.exe`, etc.

Manifest: `fpv-library/manifests/Caddx_Ground_Configuration_Release.json`  
Status: `fpv-library/manifests/Caddx_Ground_Configuration_Release.status.json`

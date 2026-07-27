# extract-ascent-otra

Rebuild partitions and unpack supported filesystem volumes from Walksnail / Artosyn OTRA firmware images.

## Requirements

- Python 3.12+
- `uv`
- `curl`, used by `download.sh`

## Download Firmware

```bash
./download.sh
```

The downloaded firmware image is saved as:

```text
Ascent_G_Gnd_16_5_7.img
```

## Extract

```bash
uv run python extract_ascent_otra.py Ascent_G_Gnd_16_5_7.img -o extracted_otra
```

The script rebuilds firmware partitions and unpacks supported UBI, UBIFS, and SquashFS volumes.

Common output paths:

```text
extracted_otra/userapp0.ubi
extracted_otra/userapp0_files/userapp/
extracted_otra/usr_data0_files/usr_data/
extracted_otra/fpv_data_files/fpv_data/
```

## Options

Rebuild partition images without unpacking filesystems:

```bash
uv run python extract_ascent_otra.py Ascent_G_Gnd_16_5_7.img -o extracted_otra --no-unpack
```

Also write `.bin` copies for UBI partitions:

```bash
uv run python extract_ascent_otra.py Ascent_G_Gnd_16_5_7.img -o extracted_otra --write-all-bin
```

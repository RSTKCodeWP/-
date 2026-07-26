#!/usr/bin/env python3
"""
TerraForge CLI Tool
Command-line interface for TerraForge Studio API

Usage:
    terraforge generate --bbox "48.8566,48.8466,2.3522,2.3422" --resolution 30
    terraforge export gen_abc123 --format godot --output terrain.tres
    terraforge history --limit 10
"""

import json
import time
from pathlib import Path

import click
import requests


class TerraForgeAPI:
    def __init__(self, api_key: str, base_url: str = "https://api.terraforge.studio/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def generate_terrain(self, bbox: dict, resolution: int, source: str = "srtm"):
        """Generate terrain"""
        response = self.session.post(
            f"{self.base_url}/terrain/generate",
            json={
                "bbox": bbox,
                "resolution": resolution,
                "source": source
            }
        )
        response.raise_for_status()
        return response.json()

    def get_generation_status(self, generation_id: str):
        """Get generation status"""
        response = self.session.get(f"{self.base_url}/terrain/generate/{generation_id}")
        response.raise_for_status()
        return response.json()

    def export_terrain(self, generation_id: str, format: str, options: dict = None):
        """Export terrain"""
        payload = {
            "generation_id": generation_id,
            "format": format
        }
        if options:
            payload["options"] = options

        response = self.session.post(f"{self.base_url}/export", json=payload)
        response.raise_for_status()
        return response.json()

    def get_export_status(self, export_id: str):
        """Get export status"""
        response = self.session.get(f"{self.base_url}/export/{export_id}")
        response.raise_for_status()
        return response.json()

    def download_file(self, url: str, output_path: Path):
        """Download file from URL"""
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def get_history(self, limit: int = 10, offset: int = 0):
        """Get generation history"""
        response = self.session.get(
            f"{self.base_url}/history",
            params={"limit": limit, "offset": offset}
        )
        response.raise_for_status()
        return response.json()


@click.group()
@click.option('--api-key', envvar='TERRAFORGE_API_KEY', help='TerraForge API key')
@click.pass_context
def cli(ctx, api_key):
    """TerraForge Studio CLI"""
    if not api_key:
        click.echo("Error: API key required. Set TERRAFORGE_API_KEY environment variable or use --api-key")
        ctx.exit(1)

    ctx.obj = TerraForgeAPI(api_key)


@cli.command()
@click.option('--bbox', required=True, help='Bounding box: "north,south,east,west"')
@click.option('--resolution', type=int, default=30, help='Resolution in meters')
@click.option('--source', default='srtm', help='Data source (srtm, aster, nasadem)')
@click.option('--wait/--no-wait', default=True, help='Wait for completion')
@click.pass_obj
def generate(api: TerraForgeAPI, bbox, resolution, source, wait):
    """Generate terrain from bounding box"""
    try:
        # Parse bbox
        coords = [float(x.strip()) for x in bbox.split(',')]
        if len(coords) != 4:
            raise ValueError("Bbox must have 4 coordinates")

        bbox_dict = {
            "north": coords[0],
            "south": coords[1],
            "east": coords[2],
            "west": coords[3]
        }

        click.echo("🌍 Generating terrain...")
        click.echo(f"   Bbox: {bbox}")
        click.echo(f"   Resolution: {resolution}m")

        result = api.generate_terrain(bbox_dict, resolution, source)
        generation_id = result['id']

        click.echo(f"✅ Generation started: {generation_id}")

        if wait:
            click.echo("⏳ Waiting for completion...")
            with click.progressbar(length=100, label='Progress') as bar:
                while True:
                    status = api.get_generation_status(generation_id)
                    bar.update(status.get('progress', 0) - bar.pos)

                    if status['status'] == 'completed':
                        click.echo("\n✅ Generation completed!")
                        click.echo(f"   Heightmap: {status['result']['heightmap_url']}")
                        break
                    elif status['status'] == 'failed':
                        click.echo(f"\n❌ Generation failed: {status.get('error')}")
                        break

                    time.sleep(2)
        else:
            click.echo(f"Use 'terraforge status {generation_id}' to check progress")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


@cli.command()
@click.argument('generation_id')
@click.pass_obj
def status(api: TerraForgeAPI, generation_id):
    """Check generation status"""
    try:
        result = api.get_generation_status(generation_id)
        click.echo(f"Status: {result['status']}")
        click.echo(f"Progress: {result.get('progress', 0)}%")

        if result['status'] == 'completed':
            click.echo(f"Heightmap: {result['result']['heightmap_url']}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


@cli.command()
@click.argument('generation_id')
@click.option('--format', required=True, help='Export format (godot, unity, unreal)')
@click.option('--output', type=click.Path(), help='Output file path')
@click.option('--wait/--no-wait', default=True, help='Wait for completion')
@click.pass_obj
def export(api: TerraForgeAPI, generation_id, format, output, wait):
    """Export terrain to game engine format"""
    try:
        click.echo(f"📦 Exporting to {format}...")

        result = api.export_terrain(generation_id, format)
        export_id = result['id']

        click.echo(f"✅ Export started: {export_id}")

        if wait:
            click.echo("⏳ Waiting for completion...")
            while True:
                status = api.get_export_status(export_id)

                if status['status'] == 'completed':
                    download_url = status['download_url']
                    click.echo("✅ Export completed!")

                    if output:
                        click.echo(f"⬇️  Downloading to {output}...")
                        api.download_file(download_url, Path(output))
                        click.echo("✅ Downloaded successfully!")
                    else:
                        click.echo(f"Download: {download_url}")
                    break
                elif status['status'] == 'failed':
                    click.echo(f"❌ Export failed: {status.get('error')}")
                    break

                time.sleep(2)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


@cli.command()
@click.option('--limit', type=int, default=10, help='Number of items')
@click.option('--format', type=click.Choice(['json', 'table']), default='table')
@click.pass_obj
def history(api: TerraForgeAPI, limit, format):
    """View generation history"""
    try:
        result = api.get_history(limit=limit)

        if format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"\n📜 Generation History ({result['total']} total)\n")
            for item in result['items']:
                status_emoji = {
                    'completed': '✅',
                    'processing': '⏳',
                    'failed': '❌',
                    'pending': '📋'
                }.get(item['status'], '❓')

                click.echo(f"{status_emoji} {item['id']}")
                click.echo(f"   Status: {item['status']}")
                click.echo(f"   Created: {item['created_at']}")
                click.echo()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


if __name__ == '__main__':
    cli()

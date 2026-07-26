/**
 * Script to generate PWA icons from SVG
 * Requires: npm install sharp
 * Usage: node scripts/generate-icons.js
 */

import sharp from 'sharp';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sizes = [
  { size: 16, name: 'favicon-16x16.png' },
  { size: 32, name: 'favicon-32x32.png' },
  { size: 192, name: 'icon-192.png' },
  { size: 512, name: 'icon-512.png' },
  { size: 180, name: 'apple-touch-icon.png' },
];

const svgPath = join(__dirname, '../public/icon.svg');
const publicDir = join(__dirname, '../public');

async function generateIcons() {
  console.log('🎨 Generating PWA icons...\n');

  const svgBuffer = readFileSync(svgPath);

  for (const { size, name } of sizes) {
    try {
      await sharp(svgBuffer)
        .resize(size, size, {
          fit: 'contain',
          background: { r: 37, g: 99, b: 235, alpha: 1 }, // #2563eb
        })
        .png()
        .toFile(join(publicDir, name));
      
      console.log(`✅ Generated ${name} (${size}x${size})`);
    } catch (error) {
      console.error(`❌ Failed to generate ${name}:`, error.message);
    }
  }

  console.log('\n🎉 Icon generation complete!');
}

generateIcons().catch(console.error);

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { visualizer } from 'rollup-plugin-visualizer'
import { splitVendorChunkPlugin } from 'vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    splitVendorChunkPlugin(),
    // Bundle analyzer - generates stats.html after build
    visualizer({
      filename: './dist/stats.html',
      open: false,
      gzipSize: true,
      brotliSize: true,
    }) as any,
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // Optimize chunks
    rollupOptions: {
      output: {
        manualChunks: {
          // Separate CesiumJS into its own chunk (large library)
          'cesium': ['cesium', 'resium'],
          // Separate Leaflet into its own chunk
          'leaflet': ['leaflet', 'react-leaflet', 'leaflet-draw'],
          // React core
          'react-vendor': ['react', 'react-dom'],
          // UI libraries
          'ui-vendor': ['framer-motion', 'lucide-react', 'react-hot-toast'],
        },
      },
    },
    // Increase chunk size warning limit for large libraries
    chunkSizeWarningLimit: 1000,
    // Enable minification
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // Remove console.logs in production
        drop_debugger: true,
      },
    },
  },
  define: {
    // Fix for CesiumJS
    CESIUM_BASE_URL: JSON.stringify('/cesium'),
  },
})


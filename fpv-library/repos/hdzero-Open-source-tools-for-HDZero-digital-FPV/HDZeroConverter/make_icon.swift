#!/usr/bin/env swift
import AppKit

// Renders a 1024×1024 app icon PNG to icon_1024.png
let size = 1024
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
let ctx = NSGraphicsContext.current!.cgContext
let rect = CGRect(x: 0, y: 0, width: size, height: size)

// Rounded-rect background with diagonal gradient (FPV "indigo → cyan")
let radius: CGFloat = 230
let path = CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil)
ctx.addPath(path)
ctx.clip()
let colors = [NSColor(calibratedRed: 0.36, green: 0.20, blue: 0.92, alpha: 1).cgColor,
              NSColor(calibratedRed: 0.13, green: 0.66, blue: 0.95, alpha: 1).cgColor] as CFArray
let grad = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1])!
ctx.drawLinearGradient(grad, start: CGPoint(x: 0, y: size), end: CGPoint(x: size, y: 0), options: [])

// Subtle scanlines to evoke a video feed
ctx.setFillColor(NSColor.white.withAlphaComponent(0.05).cgColor)
var y = 0
while y < size { ctx.fill(CGRect(x: 0, y: y, width: size, height: 6)); y += 22 }

// White play triangle
let cx = CGFloat(size) / 2, cy = CGFloat(size) / 2
let tri = CGMutablePath()
let w: CGFloat = 300
tri.move(to: CGPoint(x: cx - w*0.45, y: cy + w*0.6))
tri.addLine(to: CGPoint(x: cx - w*0.45, y: cy - w*0.6))
tri.addLine(to: CGPoint(x: cx + w*0.7, y: cy))
tri.closeSubpath()
ctx.setShadow(offset: CGSize(width: 0, height: -14), blur: 40, color: NSColor.black.withAlphaComponent(0.25).cgColor)
ctx.addPath(tri)
ctx.setFillColor(NSColor.white.cgColor)
ctx.fillPath()

img.unlockFocus()

guard let tiff = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: tiff),
      let png = rep.representation(using: .png, properties: [:]) else {
    fputs("failed to render\n", stderr); exit(1)
}
try! png.write(to: URL(fileURLWithPath: "icon_1024.png"))
print("wrote icon_1024.png")

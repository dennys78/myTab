#!/usr/bin/env python3
"""Estrae l'icona cartella dal logo e genera PNG trasparenti per web e PWA."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
SOURCE = Path(__file__).resolve().parents[2].parent / '.cursor/projects/Users-daniele-Documents-myTaba/assets'
SOURCE_CANDIDATES = [
    Path('/Users/daniele/.cursor/projects/Users-daniele-Documents-myTaba/assets/Gemini_Generated_Image_w6v92fw6v92fw6v9-600d03e2-01ee-4371-8f25-6a49224d650e.png'),
    ROOT.parent / 'assets' / 'logo-source.png',
]


def find_source() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError('Logo sorgente non trovato')


def is_near_white(r: int, g: int, b: int, threshold: int = 238) -> bool:
    return r >= threshold and g >= threshold and b >= threshold


def flood_remove_white(img: Image.Image, threshold: int = 238) -> Image.Image:
    img = img.convert('RGBA')
    pixels = img.load()
    w, h = img.size
    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()

    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        if (x, y) in visited:
            continue
        visited.add((x, y))
        r, g, b, a = pixels[x, y]
        if not is_near_white(r, g, b, threshold):
            continue
        pixels[x, y] = (255, 255, 255, 0)
        queue.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    return img


def trim_transparent(img: Image.Image, padding: int = 0) -> Image.Image:
    bbox = img.getbbox()
    if not bbox:
        return img
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(img.width, right + padding)
    bottom = min(img.height, bottom + padding)
    return img.crop((left, top, right, bottom))


def extract_folder_icon(src: Image.Image) -> Image.Image:
    w, h = src.size
    # Ritaglio superiore: cartella sopra, testo "myTab" sotto
    crop_h = int(h * 0.58)
    crop_w = crop_h
    left = (w - crop_w) // 2
    icon = src.crop((left, 0, left + crop_w, crop_h))
    icon = flood_remove_white(icon)
    return trim_transparent(icon, padding=4)


def pad_square(img: Image.Image, size: int, margin_ratio: float = 0.12) -> Image.Image:
    margin = int(size * margin_ratio)
    inner = size - margin * 2
    scale = min(inner / img.width, inner / img.height)
    nw = max(1, int(img.width * scale))
    nh = max(1, int(img.height * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    ox = (size - nw) // 2
    oy = (size - nh) // 2
    canvas.paste(resized, (ox, oy), resized)
    return canvas


def main() -> None:
    src_path = find_source()
    src = Image.open(src_path).convert('RGBA')
    icon = extract_folder_icon(src)

    PUBLIC.mkdir(parents=True, exist_ok=True)
    icon.save(PUBLIC / 'logo-icon.png', optimize=True)

    # Logo UI web: icona trasparente (altezza ~72px equivalente)
    ui_h = 144
    ui_scale = ui_h / icon.height
    ui_w = max(1, int(icon.width * ui_scale))
    icon_ui = icon.resize((ui_w, ui_h), Image.Resampling.LANCZOS)
    icon_ui.save(PUBLIC / 'logo.png', optimize=True)

    sizes = {
        'pwa-512x512.png': 512,
        'pwa-192x192.png': 192,
        'apple-touch-icon.png': 180,
        'favicon-32.png': 32,
    }
    for name, size in sizes.items():
        pad_square(icon, size).save(PUBLIC / name, optimize=True)

    print(f'Generated icons from {src_path}')


if __name__ == '__main__':
    main()

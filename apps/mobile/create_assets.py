"""Script to create placeholder PNG assets for the mobile app."""
import base64
import os

# 1x1 transparent PNG
TRANSPARENT_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

assets_dir = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(assets_dir, exist_ok=True)

for filename in ["icon.png", "adaptive-icon.png", "splash-icon.png"]:
    path = os.path.join(assets_dir, filename)
    with open(path, "wb") as f:
        f.write(TRANSPARENT_1x1)
    print(f"Created: {path}")

print("Done — replace placeholder PNGs with real assets before publishing.")

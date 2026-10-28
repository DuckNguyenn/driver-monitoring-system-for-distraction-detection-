"""Generate the geometric app icon without downloading image assets."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "mobile" / "assets"
SIZE = 1024
SCALE = 2
GREEN = "#23634f"
WHITE = "#edf8f3"


def icon(transparent: bool) -> Image.Image:
    image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0) if transparent else GREEN)
    draw = ImageDraw.Draw(image)
    def box(values):
        return tuple(int(v * SCALE) for v in values)
    shield = [(512, 230), (744, 318), (720, 594), (652, 704), (512, 794), (372, 704), (304, 594), (280, 318), (512, 230)]
    draw.line([(x * SCALE, y * SCALE) for x, y in shield], fill=WHITE, width=20 * SCALE, joint="curve")
    draw.ellipse(box((357, 419, 667, 601)), outline=WHITE, width=16 * SCALE)
    draw.ellipse(box((461, 459, 563, 561)), fill=WHITE)
    draw.ellipse(box((493, 480, 521, 508)), fill=GREEN)
    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon(False).save(ASSETS / "icon.png")
    icon(True).save(ASSETS / "adaptive-icon.png")
    print("Generated mobile icons")


if __name__ == "__main__":
    main()

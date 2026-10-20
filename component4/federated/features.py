"""Turn one conjunctiva (inner-eyelid) photo into 10 colour numbers.

Idea: anaemia makes the conjunctiva paler (less red). Instead of a large image
network, each image is summarised by its average colour and "redness", which a
small model can learn from and which works with Opacus differential privacy.
"""

import numpy as np

FEATURE_NAMES = [
    "mean_red", "mean_green", "mean_blue",       # average colour (0-1)
    "std_red", "std_green",                      # colour variation across the eyelid
    "red_share", "green_share",                  # R/(R+G+B), G/(R+G+B): colour balance, ignores brightness
    "erythema_index",                            # log10(R) - log10(G): standard redness (pallor) measure
    "saturation",                                # how vivid vs washed-out the colour is
    "red_minus_green",                           # simple redness difference
]

EPS = 1 / 255   # avoids dividing by zero / log of zero


def colour_features(image_path):
    """Return the 10 features (same order as FEATURE_NAMES) for one image."""
    # Imported here, not at the top: training only needs FEATURE_NAMES, so the
    # federated nodes (and the Docker image) do not need Pillow installed.
    from PIL import Image

    rgba =np.asarray(Image.open(image_path).convert("RGBA"), dtype=np.float64) / 255.0
    rgb, alpha = rgba[..., :3], rgba[..., 3]

    # Keep only eyelid pixels: drop the transparent background and any near-white border
    tissue = (alpha > 0.5) & (rgb.min(axis=2) < 0.94)
    pixels = rgb[tissue]                         # shape: (number of eyelid pixels, 3)
    if len(pixels) < 50:
        raise ValueError(f"too few eyelid pixels in {image_path}")

    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    total = r + g + b + EPS
    brightest, darkest = pixels.max(axis=1), pixels.min(axis=1)

    return [
        r.mean(), g.mean(), b.mean(),
        r.std(), g.std(),
        (r / total).mean(), (g / total).mean(),
        (np.log10(r + EPS) - np.log10(g + EPS)).mean(),
        ((brightest - darkest) / (brightest + EPS)).mean(),
        (r - g).mean(),
    ]


# AyurAI Component 1 - Database-driven Image Dataset

from pathlib import Path
import sqlite3

import pandas as pd
import torch
from PIL import Image, ImageOps
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

# Local database outside the Git repository
REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT.parent / "datasets" / "ayurai_image_catalog.sqlite3"

IMAGE_TRANSFORM = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


class AyurAIImageDataset(Dataset):

    def __init__(self, source):
        if not DB_PATH.is_file():
            raise FileNotFoundError(DB_PATH)

        with sqlite3.connect(DB_PATH) as conn:
            self.records = pd.read_sql_query(
                """
                SELECT file_path, filename, anaemia_label,
                       filename_family
                FROM image_records
                WHERE source = ?
                  AND anaemia_label IS NOT NULL
                ORDER BY filename
                """,
                conn,
                params=(source,)
            )

        if self.records.empty:
            raise ValueError(f"No labelled images for: {source}")

        missing = [
            path for path in self.records["file_path"]
            if not Path(path).is_file()
        ]

        if missing:
            raise FileNotFoundError(
                f"{len(missing)} image files are missing"
            )

        self.source = source

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        row = self.records.iloc[index]

        with Image.open(row["file_path"]) as original:
            rgba = original.convert("RGBA")

            background = Image.new(
                "RGBA", rgba.size, (255, 255, 255, 255)
            )
            background.alpha_composite(rgba)

            image = background.convert("RGB")

        image = ImageOps.pad(
            image,
            (224, 224),
            method=Image.Resampling.BILINEAR,
            color=(255, 255, 255)
        )

        image = IMAGE_TRANSFORM(image)

        label = torch.tensor(
            int(row["anaemia_label"]),
            dtype=torch.long
        )

        return image, label


if __name__ == "__main__":

    sources = [
        "cp_anemic_v2",
        "ghana_conjunctiva",
        "ghana_fingernail"
    ]

    print("AYURAI - DATABASE IMAGE LOADER")
    print("-" * 40)

    for source in sources:
        dataset = AyurAIImageDataset(source)

        loader = DataLoader(
            dataset,
            batch_size=4,
            shuffle=False,
            num_workers=0
        )

        images, labels = next(iter(loader))

        print(f"\nSource: {source}")
        print("Total records:", len(dataset))
        print("Batch shape:", images.shape)
        print("Batch labels:", labels.tolist())

    print("\nAll image loaders working successfully!")


# AyurAI - Database-driven training DataLoaders

from pathlib import Path

import pandas as pd
from torch.utils.data import DataLoader, Subset

from catalog_dataset import AyurAIImageDataset, REPO_ROOT

SPLIT_DIR = REPO_ROOT.parent / "datasets" / "splits"


def create_loaders(source, batch_size=16):

    # Load images and labels through SQLite
    dataset = AyurAIImageDataset(source)

    # Read the previously saved split assignments
    split_file = SPLIT_DIR / f"{source}_split.csv"
    splits = pd.read_csv(split_file)

    # Match split records with SQLite dataset records
    path_to_index = {
        str(path): index
        for index, path in enumerate(
            dataset.records["file_path"]
        )
    }

    if (
        splits["file_path"].duplicated().any()
        or set(splits["file_path"]) != set(path_to_index)
    ):
        raise ValueError("Split files do not match the database.")

    if set(splits["split"]) != {"train", "validation", "test"}:
        raise ValueError("Invalid dataset split names.")

    # Verify that saved labels match database labels
    for row in splits.itertuples():
        index = path_to_index[str(row.file_path)]
        db_label = int(
            dataset.records.iloc[index]["anaemia_label"]
        )

        if int(row.anaemia_label) != db_label:
            raise ValueError("Conflicting image labels detected.")

    # Verify filename families remain in one split
    if splits.groupby("filename_family")["split"].nunique().max() > 1:
        raise ValueError("Filename family leakage detected.")

    loaders = {}

    for split_name in ["train", "validation", "test"]:

        subset_rows = splits[
            splits["split"] == split_name
        ]

        indices = [
            path_to_index[str(path)]
            for path in subset_rows["file_path"]
        ]

        subset = Subset(dataset, indices)

        loaders[split_name] = DataLoader(
            subset,
            batch_size=batch_size,
            shuffle=(split_name == "train"),
            num_workers=0
        )

    return loaders


if __name__ == "__main__":

    for source in [
        "ghana_conjunctiva",
        "ghana_fingernail"
    ]:
        print(f"\nDataset: {source}")

        loaders = create_loaders(source)

        for split_name, loader in loaders.items():
            images, labels = next(iter(loader))

            print(
                f"{split_name}: "
                f"{len(loader.dataset)} images | "
                f"Batch: {tuple(images.shape)}"
            )

    print("\nAll training DataLoaders are working!")

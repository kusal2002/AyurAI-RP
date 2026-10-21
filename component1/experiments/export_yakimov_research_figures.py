"""AyurAI C1: export GitHub-friendly validation figures and a summary for Yakimov Experiments A and B.

Reads ONLY saved validation outputs (no models, images or test data):
  ../datasets/trained_model_artifacts/experiments/yakimov_hb_2024/whole_frame_ft_v1/history.csv
  ../datasets/trained_model_artifacts/experiments/yakimov_hb_2024/nail_crop_ft_v1/{history.csv, summary.json,
      validation_comparison_patient_level.csv, validation_patient_predictions.csv}
Participant IDs are dropped on read; outputs hold aggregate metrics and anonymous points only.

Run from the repository root (after `yakimov_nail_crop_ft --compare`):
    python -m component1.experiments.export_yakimov_research_figures
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = REPO_ROOT.parent / "datasets" / "trained_model_artifacts" / "experiments" / "yakimov_hb_2024"
RUN_A, RUN_B = RUNS / "whole_frame_ft_v1", RUNS / "nail_crop_ft_v1"
OUT = REPO_ROOT / "component1" / "evaluation" / "experiments" / "yakimov_hb_2024"
SEED, BOOTSTRAPS = 42, 5000

# Validated categorical slots 1-3 (all-pairs safe); the baseline is a neutral reference, not a series.
MODELS = [  # key in predictions CSV, display name, colour, marker
    ("original_whole_frame", "Original (whole frame)", "#2a78d6", "o"),
    ("experiment_a_whole_frame_ft", "Experiment A (whole-frame fine-tune)", "#eb6834", "s"),
    ("experiment_b_nail_crop_ft", "Experiment B (nail crops, research only)", "#1baf7a", "^"),
]
BASELINE = ("train_mean_baseline", "Training-mean baseline", "#9a9893")
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#ffffff"
SUBTITLE = "Validation set, n = 37 patients (NOT the held-out test set) · Yakimov Hb 2024"


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK, "axes.titlecolor": INK, "xtick.color": MUTED,
        "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
        "legend.frameon": False,
    })


def metrics(actual, predicted):
    return {
        "patients": int(len(actual)),
        "mae_g_dl": float(mean_absolute_error(actual, predicted)),
        "rmse_g_dl": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
        "mean_signed_error_g_dl": float(np.mean(predicted - actual)),
    }


def paired(actual, model, reference, boot):
    """Paired patient-level comparison of absolute errors (negative = model better)."""
    error_m, error_r = np.abs(model - actual), np.abs(reference - actual)
    diff = error_m - error_r
    resampled = diff[boot].mean(axis=1)
    return {
        "mae_difference_g_dl": float(diff.mean()),
        "exploratory_95ci_g_dl": [float(np.percentile(resampled, 2.5)), float(np.percentile(resampled, 97.5))],
        "ci_includes_zero": bool(np.percentile(resampled, 2.5) <= 0 <= np.percentile(resampled, 97.5)),
        "patients_model_better": int((diff < 0).sum()),
        "patients_model_worse": int((diff > 0).sum()),
        "patients_tied": int((diff == 0).sum()),
        "median_per_patient_difference_g_dl": float(np.median(diff)),
    }


def finish(fig, name, title):
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.text(0.01, 0.90, SUBTITLE, ha="left", fontsize=9, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)


def bar_chart(summary, key, name, title, label):
    rows = [(n, summary[k][key], c) for k, n, c, _ in MODELS] + [(BASELINE[1], summary[BASELINE[0]][key], BASELINE[2])]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    y = np.arange(len(rows))[::-1]
    ax.barh(y, [r[1] for r in rows], color=[r[2] for r in rows], height=0.6, edgecolor=SURFACE, linewidth=2)
    for yi, (_, value, _) in zip(y, rows):
        ax.text(value + 0.015, yi, f"{value:.4f}", va="center", color=INK, fontsize=10)
    ax.set_yticks(y, [r[0] for r in rows])
    ax.set_xlim(0, max(r[1] for r in rows) * 1.15)
    ax.set_xlabel(f"{label} (g/dL) — lower is better")
    ax.grid(axis="y", visible=False)
    finish(fig, name, title)


def curves(history, name, title, selected, epoch0_label, references):
    fig, (left, right) = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw={"width_ratios": [1, 1.15]})
    trained = history[history.epoch > 0]
    left.plot(trained.epoch, trained.train_loss, color=MODELS[0][2], linewidth=2, marker="o", markersize=6)
    left.set(title="Training loss (SmoothL1, normalised Hb)", xlabel="Epoch", ylabel="Loss")
    mae_col = "val_mae_g_dl" if "val_mae_g_dl" in history else "mae_g_dl"
    rmse_col = "val_rmse_g_dl" if "val_rmse_g_dl" in history else "rmse_g_dl"
    right.plot(history.epoch, history[mae_col], color=MODELS[0][2], linewidth=2, marker="o", markersize=6, label="Validation MAE")
    right.plot(history.epoch, history[rmse_col], color=MODELS[1][2], linewidth=2, marker="s", markersize=6, label="Validation RMSE")
    for value, text, style_ in references:
        right.axhline(value, color=BASELINE[2], linestyle=style_, linewidth=1.5, label=f"{text} ({value:.4f})")
    best = history.loc[history.epoch == selected, mae_col].iloc[0]
    right.scatter([selected], [best], s=140, facecolors="none", edgecolors=INK, linewidths=1.5, zorder=5)
    right.annotate(f"selected epoch {selected}\nMAE {best:.4f}", (selected, best), textcoords="offset points",
                   xytext=(-14, 22), ha="right", fontsize=8, color=INK,
                   arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8})
    right.set(title="Validation error (g/dL)", ylabel="g/dL")
    right.set_xlabel(f"Epoch\n(epoch 0 = {epoch0_label})", fontsize=9)
    right.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8)
    finish(fig, name, title)


def main():
    style()
    OUT.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(RUN_B / "validation_patient_predictions.csv").drop(columns=["participant_id"])
    table = pd.read_csv(RUN_B / "validation_comparison_patient_level.csv").set_index("model")
    summary_b = json.loads((RUN_B / "summary.json").read_text(encoding="utf-8"))
    history_a = pd.read_csv(RUN_A / "history.csv")
    history_b = pd.read_csv(RUN_B / "history.csv")
    if len(predictions) != 37:
        raise ValueError("Expected 37 validation patients")
    actual = predictions.actual_hb_g_dl.to_numpy()
    pred = {k: predictions[f"pred_{k}"].to_numpy() for k in [m[0] for m in MODELS] + [BASELINE[0]]}

    summary = {k: metrics(actual, v) for k, v in pred.items()}
    for key, values in summary.items():  # must agree with --compare output and the training summaries
        if not np.isclose(values["mae_g_dl"], table.loc[key, "mae_g_dl"]) or not np.isclose(values["r2"], table.loc[key, "r2"]):
            raise ValueError(f"Recomputed metrics disagree with --compare for {key}")
    if not np.isclose(summary["experiment_b_nail_crop_ft"]["mae_g_dl"], summary_b["best_patient_val_mae_g_dl"]):
        raise ValueError("Experiment B MAE disagrees with its training summary")
    # Training validated in batches of 16, --compare in batches of 32: GPU float32 results differ by <1e-3 g/dL.
    if not np.isclose(summary["experiment_a_whole_frame_ft"]["mae_g_dl"], history_a.val_mae_g_dl.min(), rtol=0, atol=5e-4):
        raise ValueError("Experiment A MAE disagrees with its training history")
    if not np.isclose(summary["original_whole_frame"]["mae_g_dl"], history_a.loc[history_a.epoch == 0, "val_mae_g_dl"].iloc[0], rtol=0, atol=5e-4):
        raise ValueError("Original model MAE disagrees with the recorded epoch-0 value")

    boot = np.random.default_rng(SEED).integers(0, len(actual), size=(BOOTSTRAPS, len(actual)))
    comparisons = {
        "B_vs_original": paired(actual, pred["experiment_b_nail_crop_ft"], pred["original_whole_frame"], boot),
        "B_vs_A": paired(actual, pred["experiment_b_nail_crop_ft"], pred["experiment_a_whole_frame_ft"], boot),
        "A_vs_original": paired(actual, pred["experiment_a_whole_frame_ft"], pred["original_whole_frame"], boot),
    }

    bar_chart(summary, "mae_g_dl", "validation_mae_comparison.png", "Validation MAE by model", "Mean absolute error")
    bar_chart(summary, "rmse_g_dl", "validation_rmse_comparison.png", "Validation RMSE by model", "Root mean squared error")
    baseline_mae = summary[BASELINE[0]]["mae_g_dl"]
    curves(history_a, "experiment_a_training_curves.png", "Experiment A: whole-frame fine-tuning (training history)",
           int(history_a.loc[history_a.val_mae_g_dl.idxmin(), "epoch"]), "original production model",
           [(baseline_mae, "training-mean baseline MAE", "--")])
    curves(history_b, "experiment_b_training_curves.png", "Experiment B: nail-crop fine-tuning (training history, research only)",
           int(summary_b["best_epoch"]), "original whole-frame weights evaluated on nail crops (reference)",
           [(baseline_mae, "training-mean baseline MAE", "--"),
            (summary["original_whole_frame"]["mae_g_dl"], "original whole-frame model MAE", ":")])

    lims = (min(actual.min(), min(v.min() for v in pred.values())) - 0.5, max(actual.max(), max(v.max() for v in pred.values())) + 0.5)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharex=True, sharey=True)
    for ax, (key, label, colour, marker) in zip(axes, MODELS):
        ax.plot(lims, lims, color=MUTED, linestyle="--", linewidth=1, label="perfect agreement")
        ax.axhline(pred[BASELINE[0]][0], color=BASELINE[2], linestyle=":", linewidth=1.2, label="training-mean prediction")
        ax.scatter(actual, pred[key], s=36, color=colour, marker=marker, edgecolors=SURFACE, linewidths=1, label=label)
        ax.set(title=f"{label}\nMAE {summary[key]['mae_g_dl']:.3f} · R² {summary[key]['r2']:.3f}",
               xlabel="Laboratory Hb (g/dL)", xlim=lims, ylim=lims)
        ax.title.set_fontsize(9)
    axes[0].set_ylabel("Estimated Hb (g/dL)")
    axes[0].legend(handles=axes[0].get_legend_handles_labels()[0][:2], fontsize=8, loc="upper left")
    finish(fig, "validation_actual_vs_predicted.png", "Estimated vs laboratory haemoglobin (validation)")

    fig, ax = plt.subplots(figsize=(10, 4.6))
    order = MODELS + [(BASELINE[0], BASELINE[1], BASELINE[2], "D")]
    errors = [np.abs(pred[k] - actual) for k, *_ in order]
    box = ax.boxplot(errors, orientation="horizontal", widths=0.5, patch_artist=True, showfliers=False,
                     medianprops={"color": INK, "linewidth": 1.5}, whiskerprops={"color": MUTED}, capprops={"color": MUTED})
    rng = np.random.default_rng(SEED)
    for i, ((_, _, colour, marker), patch, values) in enumerate(zip(order, box["boxes"], errors), start=1):
        patch.set(facecolor=colour, alpha=0.25, edgecolor=colour)
        ax.scatter(values, i + rng.uniform(-0.12, 0.12, len(values)), s=22, color=colour, marker=marker,
                   edgecolors=SURFACE, linewidths=0.8, zorder=3)
        ax.text(np.median(values), i - 0.32, f"median {np.median(values):.2f}", ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_yticks(range(1, len(order) + 1), [label for _, label, *_ in order])
    ax.invert_yaxis()
    ax.set_xlabel("Absolute error per patient |estimated − laboratory Hb| (g/dL)")
    ax.grid(axis="y", visible=False)
    finish(fig, "validation_error_distribution.png", "Patient-level absolute error distribution (validation)")

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharex=True, sharey=True)
    for ax, (key, label, colour, marker) in zip(axes, MODELS):
        residual = pred[key] - actual
        ax.axhline(0, color=MUTED, linewidth=1)
        ax.scatter(actual, residual, s=36, color=colour, marker=marker, edgecolors=SURFACE, linewidths=1)
        ax.set(title=f"{label}\nmean signed error {summary[key]['mean_signed_error_g_dl']:+.3f} g/dL", xlabel="Laboratory Hb (g/dL)")
        ax.title.set_fontsize(9)
    axes[0].set_ylabel("Residual: estimated − laboratory Hb (g/dL)")
    finish(fig, "validation_residuals.png", "Residuals vs laboratory haemoglobin (validation)")

    record = {
        "experiment": "AyurAI C1 · Yakimov Hb 2024 nail-bed Hb regression · Experiments A and B",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_set": "validation (37 patients); also used for checkpoint selection, so results are optimistic",
        "split_patients": {"train": 175, "validation": 37, "test": 38},
        "test_set_evaluated": False,
        "production_checkpoint_promoted": False,
        "metrics_g_dl": {**summary},
        "paired_patient_level_comparisons": {
            "method": f"paired patient-level bootstrap of per-patient absolute-error differences, {BOOTSTRAPS} resamples, seed {SEED}",
            "status": "EXPLORATORY: validation patients were also used for model selection (selection bias); not a significance test",
            **comparisons,
        },
        "experiment_b_selected_epoch": int(summary_b["best_epoch"]),
        "experiment_a_selected_epoch": int(history_a.loc[history_a.val_mae_g_dl.idxmin(), "epoch"]),
        "source_runs": {"experiment_a": RUN_A.name, "experiment_b": RUN_B.name},
    }
    (OUT / "validation_summary.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({k: {m: round(v, 4) if isinstance(v, float) else v for m, v in d.items()} for k, d in summary.items()}, indent=1))
    print(json.dumps(comparisons, indent=1))
    print("Wrote:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()

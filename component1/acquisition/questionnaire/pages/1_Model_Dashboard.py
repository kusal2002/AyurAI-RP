"""AyurAI research-model dashboard (read-only Streamlit multipage view).

Install beside questionnaire_assistant_app.py in its ``pages`` directory:
    component1/acquisition/questionnaire/pages/1_Model_Dashboard.py

Uses real saved evaluation files. Does NOT train, recalculate, or claim
clinical-risk validity. Displays demo session summaries without file paths.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


def find_repo_root(script_path: Path) -> Path:
    for directory in script_path.resolve().parents:
        if (directory / "component1" / "evaluation" / "images").is_dir():
            return directory
    raise FileNotFoundError("AyurAI-RP/component1/evaluation/images not found")


ROOT = find_repo_root(Path(__file__))
REPORTS = ROOT / "component1" / "evaluation" / "images"
DATASETS = ROOT.parent / "datasets"
SOURCES = {
    "CP-AnemiC V2 (initial classification)": "cp_anemic_v2",
    "Ghana conjunctiva (classification)": "ghana_conjunctiva",
    "Ghana fingernails (classification)": "ghana_fingernail",
    "Yakimov fingernails (Hb regression)": "yakimov_hb_2024",
}


def csv_or_none(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    try:
        df = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.EmptyDataError) as exc:
        st.warning(f"Could not read {path.name}: {exc}")
        return None
    return df if not df.empty else None


def json_or_none(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, UnicodeError, ValueError):
        st.warning(f"Could not load {path.name}")
        return None


def metric_of(row, *keys) -> float | None:
    for key in keys:
        val = row.get(key)
        try:
            if pd.notna(val):
                return float(val)
        except (ValueError, TypeError):
            pass
    return None


def pct(value) -> str:
    return f"{100 * value:.2f}%" if value is not None else "Not available"


def friendly_numeric_table(data: pd.DataFrame, percent_fields: tuple[str, ...] = ()) -> pd.DataFrame:
    copy = data.copy()
    for field in percent_fields:
        if field in copy:
            copy[field] = pd.to_numeric(copy[field], errors="coerce").map(
                lambda v: f"{v:.2%}" if pd.notna(v) else "—"
            )
    return copy


def classification_row(dataset: str, stage: str, row) -> dict:
    return {
        "Dataset": dataset,
        "Stage": stage,
        "Model": str(row.get("Model", "Unknown")),
        "Accuracy": metric_of(row, "Accuracy", "Val_Accuracy", "Test_Accuracy"),
        "Balanced accuracy": metric_of(row, "Balanced_Accuracy", "Val_Balanced_Accuracy", "Test_Balanced_Accuracy"),
        "Sensitivity": metric_of(row, "Sensitivity", "Val_Sensitivity", "Test_Sensitivity"),
        "Specificity": metric_of(row, "Specificity", "Val_Specificity", "Test_Specificity"),
        "F1": metric_of(row, "F1", "Val_F1", "Test_F1"),
        "AUROC": metric_of(row, "AUROC", "Test_AUROC"),
    }


def collect_classification_rows() -> list[dict]:
    records = []
    for source in ("ghana_conjunctiva", "ghana_fingernail"):
        report_dir = REPORTS / source
        for filename, stage in (
            ("validation_comparison.csv", "Validation (model selection)"),
            ("test_metrics.csv", "Held-out test"),
        ):
            df = csv_or_none(report_dir / filename)
            if df is not None:
                records.extend(
                    classification_row(source.replace("ghana_", "Ghana "), stage, row)
                    for row in df.to_dict("records")
                )
    # The initial CP-AnemiC notebook saved its reports at the root of images/.
    for filename, stage in (
        ("image_model_comparison.csv", "Validation (model selection)"),
        ("efficientnet_test_metrics.csv", "Held-out test"),
    ):
        df = csv_or_none(REPORTS / filename)
        if df is not None:
            records.extend(
                classification_row("CP-AnemiC V2", stage, row)
                for row in df.to_dict("records")
            )
    return records


def read_local_index_counts(db_path: Path) -> list[dict]:
    """Read image-record counts without modifying the existing SQLite catalogue."""
    if not db_path.is_file():
        return []
    rows = []
    try:
        with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
            for table in ("image_records", "hb_image_records"):
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                for source, modality, count, hb_count in conn.execute(
                    f"SELECT source, modality, COUNT(*), "
                    f"SUM(CASE WHEN hb_g_dl IS NOT NULL THEN 1 ELSE 0 END) "
                    f"FROM {table} GROUP BY source, modality ORDER BY source, modality"
                ):
                    rows.append({
                        "Dataset": source, "Anatomical region": modality,
                        "Images": int(count), "Numeric Hb labels": int(hb_count or 0),
                        "Record table": table,
                    })
    except (sqlite3.DatabaseError, OSError):
        return []
    return rows


def read_questionnaire_summary(db_path: Path) -> dict | None:
    """Return counts only; never expose stored health answers in a research dashboard."""
    if not db_path.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
            total, demo = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN is_fictional_demo = 1 THEN 1 ELSE 0 END) "
                "FROM questionnaire_responses"
            ).fetchone()
            return {"total": int(total), "demo": int(demo or 0)}
    except (sqlite3.DatabaseError, OSError):
        return None


def show_model_page() -> None:
    st.set_page_config(page_title="AyurAI | Model Dashboard", page_icon="📊", layout="wide")
    st.title("📊 AyurAI — Model Performance Dashboard")
    st.caption("Component 1 · Local, read-only research evaluation and demo-session evidence")
    st.warning(
        "Experimental public-dataset results, not clinical diagnostic accuracy. "
        "Ghana labels are filename-derived and participant independence is unverified. "
        "Webcam scores are uncalibrated; no validated final risk category is available yet."
    )

    overview, experiments, webcam, ppg, inventory = st.tabs(
        ["Overview", "Model comparisons", "Webcam sessions", "PPG replay", "Data & workflow"]
    )

    with overview:
        rows = collect_classification_rows()
        tests = [r for r in rows if r["Stage"] == "Held-out test"]
        validation = [r for r in rows if r["Stage"].startswith("Validation")]
        yakimov = csv_or_none(REPORTS / "yakimov_hb_2024" / "validation_comparison.csv")

        a, b, c, d = st.columns(4)
        a.metric("Classifiers compared", len(validation))
        b.metric("Held-out classification tests", len(tests))
        c.metric("Hb regression models compared", len(yakimov) if yakimov is not None else 0)
        d.metric("Live PPG Hb model", "Pending")

        st.subheader("Held-out classification results")
        if tests:
            df = pd.DataFrame(tests)
            st.dataframe(
                friendly_numeric_table(
                    df,
                    ("Accuracy", "Balanced accuracy", "Sensitivity", "Specificity", "F1", "AUROC"),
                ),
                hide_index=True,
                use_container_width=True,
            )
            st.download_button(
                "Export classification results (CSV)",
                pd.DataFrame(rows).to_csv(index=False),
                "ayurai_research_classification_metrics.csv",
                mime="text/csv",
            )
        else:
            st.info("No held-out classification test CSVs were found yet.")

        st.subheader("Yakimov Hb regression — validation")
        if yakimov is None:
            st.info("Yakimov validation report not found yet.")
        else:
            cols = [c for c in (
                "Model", "Best_Epoch", "Val_MAE_g_dl", "Val_RMSE_g_dl",
                "Naive_Val_MAE_g_dl",
            ) if c in yakimov]
            st.dataframe(yakimov[cols].round(3), hide_index=True, use_container_width=True)
            st.caption("For Hb regression, lower MAE/RMSE is better. This is validation error, not a classification accuracy percentage. The held-out regression test is pending.")

        st.info("Next model branches: tongue segmentation/quality, PPG signal modelling, questionnaire integration and validated reliability-aware fusion.")

    with experiments:
        choice = st.selectbox("Choose experiment", list(SOURCES))
        source = SOURCES[choice]
        if source == "cp_anemic_v2":
            folder = REPORTS
            comparison_path = folder / "image_model_comparison.csv"
            history_path = folder / "image_model_training_history.csv"
            test_path = folder / "efficientnet_test_metrics.csv"
        else:
            folder = REPORTS / source
            comparison_path = folder / "validation_comparison.csv"
            history_path = folder / "training_history.csv"
            test_path = folder / "test_metrics.csv"
        comparison = csv_or_none(comparison_path)
        history = csv_or_none(history_path)
        test = csv_or_none(test_path)

        st.subheader("Validation comparison")
        if comparison is None:
            st.info(f"Missing report: {comparison_path.relative_to(ROOT)}")
        else:
            st.dataframe(comparison.round(4), hide_index=True, use_container_width=True)
            if "Model" in comparison.columns:
                if "Val_Balanced_Accuracy" in comparison:
                    st.bar_chart(comparison.set_index("Model")["Val_Balanced_Accuracy"])
                    st.caption("Validation balanced accuracy; higher is better.")
                elif "Val_MAE_g_dl" in comparison:
                    st.bar_chart(comparison.set_index("Model")["Val_MAE_g_dl"])
                    st.caption("Validation Hb mean absolute error (g/dL); lower is better.")

        st.subheader("Training history")
        if history is None or not {"Model", "Epoch"}.issubset(history.columns):
            st.info("Training history chart not available.")
        else:
            possible = [c for c in (
                "Val_Balanced_Accuracy", "Val_F1", "Val_Accuracy",
                "Val_MAE_g_dl", "Val_RMSE_g_dl", "Train_Loss",
            ) if c in history.columns]
            if possible:
                selected = st.selectbox("Plot metric", possible)
                try:
                    pivot = history.pivot_table(index="Epoch", columns="Model", values=selected)
                    st.line_chart(pivot)
                except ValueError:
                    st.info("Could not plot history; raw values are available below.")
            with st.expander("Show all epoch records"):
                st.dataframe(history.round(4), hide_index=True, use_container_width=True)

        st.subheader("Held-out test")
        if test is None:
            st.info("Test report has not been generated for this experiment. Do not substitute validation scores for test results.")
        else:
            st.dataframe(test.round(4), hide_index=True, use_container_width=True)
            image_path = (folder / "efficientnet_test_confusion_matrix.png"
                          if source == "cp_anemic_v2" else folder / "test_confusion_matrix.png")
            if image_path.is_file():
                st.image(str(image_path), caption="Held-out test confusion matrix", width=500)
            txt_path = folder / "test_classification_report.txt"
            if txt_path.is_file():
                with st.expander("Classification report"):
                    st.code(txt_path.read_text(encoding="utf-8"), language="text")

        if source == "cp_anemic_v2":
            st.caption("Initial image-level CP-AnemiC experiment: small sample, held-out testing already completed; participant independence unverified.")
        elif source == "ghana_conjunctiva":
            st.caption("Ghana conjunctiva uses different images and label provenance from CP-AnemiC. Do not pool their held-out metrics.")

    with webcam:
        st.subheader("Recorded webcam demonstration")
        st.caption("Read-only summaries. Photos, absolute file paths, and questionnaire answers are intentionally not displayed.")
        session_root = DATASETS / "live_sessions"
        sessions = sorted(
            [p.name for p in session_root.glob("demo_*")
             if p.is_dir() and (p / "image_model_results.json").is_file()],
            reverse=True,
        ) if session_root.is_dir() else []

        if not sessions:
            st.info("No processed demo session found. Run evaluate_webcam_session.py first.")
        else:
            sid = st.selectbox("Demo session", sessions)
            data = json_or_none(session_root / sid / "image_model_results.json")
            quality = json_or_none(session_root / sid / "quality_report.json")
            if quality is not None:
                quality_rows = quality.get("results", [])
                if isinstance(quality_rows, list):
                    passed = sum(x.get("status") == "technical_checks_passed" for x in quality_rows if isinstance(x, dict))
                    st.caption(f"Technical checks passed: {passed}/{len(quality_rows)}; anatomical validity not established.")

            if data is not None:
                st.caption(f"Session: {sid} · Captures processed: {data.get('processed_image_count', 0)}")
                result_rows = []
                image_entries = data.get("images", [])
                for idx, item in enumerate(image_entries, start=1):
                    if not isinstance(item, dict):
                        continue
                    common = {
                        "Capture": idx,
                        "Modality": item.get("modality", "unknown"),
                        "Status": item.get("status", "unknown"),
                    }
                    evidence = item.get("regional_evidence") or {}
                    for entry in evidence.get("classification_evidence", []):
                        result_rows.append({
                            **common,
                            "Source": entry.get("source"),
                            "Output": "Class vote (0=non-anaemic, 1=anaemic)",
                            "Value": str(entry.get("class_vote_at_0_5")),
                            "Uncalibrated class score": entry.get("score_uncalibrated"),
                        })
                    for entry in evidence.get("experimental_hb_estimates_g_dl", []):
                        result_rows.append({
                            **common,
                            "Source": entry.get("source"),
                            "Output": "Experimental Hb estimate (g/dL)",
                            "Value": entry.get("estimate_g_dl"),
                            "Uncalibrated class score": None,
                        })
                    if not evidence.get("classification_evidence") and not evidence.get("experimental_hb_estimates_g_dl"):
                        result_rows.append({**common, "Source": "—", "Output": "No anaemia prediction", "Value": "—"})
                st.dataframe(pd.DataFrame(result_rows), hide_index=True, use_container_width=True)
                st.info("Regional results are individual experimental model outputs. These are not the final Low/Moderate/High screening-risk categories.")

    with ppg:
        st.subheader("PPG signal-processing evidence")
        st.caption("Public BIDMC waveform replay only. This is not a live MAX30102 measurement or Hb prediction.")
        processed_dir = ROOT / "component1" / "data" / "processed"
        ppg_csv = processed_dir / "ppg_filtered.csv"
        ppg_chart = processed_dir / "ppg_filter_comparison.png"
        if ppg_csv.is_file():
            try:
                sample = pd.read_csv(ppg_csv, nrows=2400)
                cols = [c for c in ("raw_ppg", "filtered_ppg") if c in sample.columns]
                if cols:
                    if "time" in sample.columns:
                        sample = sample.set_index("time")
                    st.line_chart(sample[cols])
                    st.caption("Waveform amplitude is relative; no laboratory Hb prediction or test performance is available for this PPG processing example.")
                else:
                    st.info("Found the PPG CSV, but expected raw_ppg / filtered_ppg columns are missing.")
            except (OSError, ValueError, pd.errors.ParserError) as exc:
                st.warning(f"Could not read PPG replay CSV: {exc}")
        elif ppg_chart.is_file():
            st.image(str(ppg_chart), caption="BIDMC raw vs filtered PPG")
        else:
            st.info("No processed PPG replay found. Run filter_ppg.py to create component1/data/processed/ppg_filtered.csv.")
        st.info("ESP32-S3/MAX30102 USB acquisition: not yet linked to this dashboard. Hb-labelled PPG model: not yet trained/evaluated.")

    with inventory:
        st.subheader("Indexed image datasets")
        catalog = DATASETS / "ayurai_image_catalog.sqlite3"
        image_rows = read_local_index_counts(catalog)
        if image_rows:
            st.dataframe(pd.DataFrame(image_rows), hide_index=True, use_container_width=True)
            st.caption("Image counts are records, not independent participants. ImageHB sample contains multiple anatomical views per participant.")
        else:
            st.info("Local image catalogue not found or unavailable.")

        st.subheader("Questionnaire and demo-session storage")
        questionnaire_db = DATASETS / "screening_sessions.sqlite3"
        q_counts = read_questionnaire_summary(questionnaire_db)
        if q_counts is None:
            st.info("No questionnaire database found yet. Complete and save a fictional questionnaire demo first.")
        else:
            a, b = st.columns(2)
            a.metric("Stored questionnaire records", q_counts["total"])
            b.metric("Fictional demo records", q_counts["demo"])
            st.caption("Patient answers and medication/allergy details are intentionally not displayed in this dashboard.")
        st.divider()
        st.subheader("Component 1 engineering status")
        status_rows = [
            {"Module": "CNN experiments", "Status": "Research evaluations saved", "Evidence": "Validation / held-out test CSVs"},
            {"Module": "Hb-labelled nail regression", "Status": "Validation completed", "Evidence": "Yakimov MAE comparison; test pending"},
            {"Module": "Webcam + image quality", "Status": "Working demo", "Evidence": "Saved session manifests and technical quality reports"},
            {"Module": "Adaptive questionnaire", "Status": "Prototype working", "Evidence": "Separate questionnaire page + SQLite demo"},
            {"Module": "PPG preprocessing", "Status": "Public waveform replay", "Evidence": "BIDMC processing data"},
            {"Module": "Live ESP32-S3 + MAX30102", "Status": "Pending integration", "Evidence": "No live device link yet"},
            {"Module": "Reliability-aware final fusion", "Status": "Pending", "Evidence": "No validated low/moderate/high outcome yet"},
        ]
        st.dataframe(pd.DataFrame(status_rows), hide_index=True, use_container_width=True)
        st.caption("Dashboard reads local files; it does not alter any models, train checkpoints, or disclose real patient data.")

    st.divider()
    st.caption("AyurAI Component 1 · Prototype · Public-dataset experiments · Clinical validation and deployment approvals pending")


if __name__ == "__main__":
    show_model_page()

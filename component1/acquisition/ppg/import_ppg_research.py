"""Import MAX30102 Hb-labelled public RED/IR recordings into AyurAI's SQLite catalogue.

The original files have no reliable sample timestamps, so stored indices are NOT seconds.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
DATA = REPO.parent / 'datasets'
PPG = DATA / 'PPG' / 'Hb_PPG_MAX30102'
DB = DATA / 'ayurai_image_catalog.sqlite3'
SOURCE = 'hb_ppg_max30102'
RED, IR, HB = 'Red (a.u)', 'Infra Red (a.u)', 'Hemoglobin (g/dL)'


def subject_files(root, folder_name):
    files = {}
    for p in root.rglob('*.csv'):
        if p.stem.isdecimal() and folder_name in (part.lower() for part in p.parts):
            key = int(p.stem)
            if key in files:
                raise ValueError(f'Duplicate subject {key}: {p}')
            files[key] = p
    return files


def read_recording(path, age_col):
    frame = pd.read_csv(path)
    columns = [RED, IR, HB, 'Gender', age_col]
    if frame.empty or not set(columns).issubset(frame.columns):
        raise ValueError(f'Empty or invalid subject CSV: {path}')
    for col in (RED, IR, HB, age_col):
        frame[col] = pd.to_numeric(frame[col], errors='raise')
    if not np.isfinite(frame[[RED, IR, HB, age_col]].to_numpy(dtype=float)).all():
        raise ValueError(f'Invalid numeric data: {path}')
    if any(frame[c].nunique() != 1 for c in (HB, 'Gender', age_col)):
        raise ValueError(f'Conflicting participant metadata: {path}')
    return frame


def inspect_dataset(root):
    raw = subject_files(root, 'raw dataset per subject')
    processed = subject_files(root, 'preprocessing dataset per subject')
    if not raw or set(raw) != set(processed):
        raise ValueError('Extract both per-subject ZIPs; raw/processed subject IDs must match')

    subjects, samples, proc_frames = [], [], []
    for sid in sorted(raw):
        r = read_recording(raw[sid], 'Age')
        p = read_recording(processed[sid], 'Age (year)')
        hb = float(r[HB].iloc[0])
        raw_age = float(r['Age'].iloc[0])
        processed_age = float(p['Age (year)'].iloc[0])
        sex = str(r['Gender'].iloc[0]).strip()
        if (not np.isclose(hb, float(p[HB].iloc[0]))
                or sex.lower() != str(p['Gender'].iloc[0]).strip().lower()):
            raise ValueError(f'Mismatched Hb or sex for participant {sid}')
        age_conflict = int(not np.isclose(raw_age, processed_age))
        # Do NOT guess a patient's age when two source files disagree.
        agreed_age = None if age_conflict else raw_age
        if age_conflict:
            print(f'WARNING: subject {sid} age conflict raw={raw_age:g}, processed={processed_age:g}; stored age=NULL')
        subjects.append((SOURCE, sid, sex, agreed_age, raw_age, processed_age, age_conflict,
                         hb, len(r), len(p), str(raw[sid].resolve()), str(processed[sid].resolve())))
        for variant, frame in [('raw', r), ('processed', p)]:
            for i, (red, ir) in enumerate(zip(frame[RED], frame[IR])):
                samples.append((SOURCE, sid, variant, i, float(red), float(ir)))
        proc_frames.append(p)

    combined_paths = [f for f in root.rglob('*.csv') if f.name.lower() == 'final dataset hb ppg.csv']
    if len(combined_paths) != 1:
        raise ValueError(f'Expected one Final Dataset Hb PPG.csv; found {len(combined_paths)}')
    combined = pd.read_csv(combined_paths[0])
    expected = pd.concat(proc_frames, ignore_index=True)
    if len(combined) != len(expected):
        raise ValueError('Combined CSV row count does not match per-subject processed files')
    for col in (RED, IR, HB, 'Age (year)'):
        if not np.allclose(pd.to_numeric(combined[col]), pd.to_numeric(expected[col]),
                           rtol=1e-8, atol=1e-4):
            raise ValueError(f'Combined CSV does not match subject-order records: {col}')
    if not combined['Gender'].astype(str).equals(expected['Gender'].astype(str)):
        raise ValueError('Combined CSV gender column differs from participant records')
    return subjects, samples


def main():
    if not PPG.is_dir() or not DB.is_file():
        raise FileNotFoundError(f'Expected dataset {PPG} and database {DB}')
    subjects, samples = inspect_dataset(PPG)  # Validate everything before writing.
    backup = DB.with_name(f'{DB.stem}.before_ppg_{datetime.now():%Y%m%d_%H%M%S}.sqlite3')
    with sqlite3.connect(DB) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    with sqlite3.connect(DB) as conn:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('''CREATE TABLE IF NOT EXISTS ppg_subjects (
            source TEXT, subject_id INTEGER, gender TEXT, age_years REAL,
            raw_age_years REAL, processed_age_years REAL, age_conflict INTEGER,
            hb_g_dl REAL, raw_samples INTEGER, processed_samples INTEGER,
            raw_file_path TEXT, processed_file_path TEXT,
            PRIMARY KEY(source, subject_id))''')
        conn.execute('''CREATE TABLE IF NOT EXISTS ppg_signal_samples (
            source TEXT, subject_id INTEGER, variant TEXT,
            sample_index INTEGER, red_signal REAL, ir_signal REAL,
            PRIMARY KEY(source, subject_id, variant, sample_index),
            FOREIGN KEY(source, subject_id) REFERENCES ppg_subjects(source, subject_id)
            ON DELETE CASCADE)''')
        conn.execute('DELETE FROM ppg_signal_samples WHERE source=?', (SOURCE,))
        conn.execute('DELETE FROM ppg_subjects WHERE source=?', (SOURCE,))
        conn.executemany('INSERT INTO ppg_subjects VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', subjects)
        conn.executemany('INSERT INTO ppg_signal_samples VALUES (?,?,?,?,?,?)', samples)
        sub_count = conn.execute('SELECT COUNT(*) FROM ppg_subjects WHERE source=?', (SOURCE,)).fetchone()[0]
        sample_counts = dict(conn.execute(
            'SELECT variant, COUNT(*) FROM ppg_signal_samples WHERE source=? GROUP BY variant',
            (SOURCE,)).fetchall())
        old_images = conn.execute('SELECT COUNT(*) FROM image_records').fetchone()[0]
        hb_images = conn.execute('SELECT COUNT(*) FROM hb_image_records').fetchone()[0]
        if sub_count != len(subjects) or sum(sample_counts.values()) != len(samples) or not old_images or not hb_images:
            raise RuntimeError('Import verification failed; rolling back data changes')
    print('AYURAI PPG SQLITE IMPORT VERIFIED')
    print(f'Participants: {sub_count}')
    print(f'Raw RED/IR samples: {sample_counts.get("raw", 0)}')
    print(f'Processed RED/IR samples: {sample_counts.get("processed", 0)}')
    print(f'Age conflicts flagged: {sum(row[6] for row in subjects)}')
    print(f'Existing image_records preserved: {old_images}')
    print(f'Existing hb_image_records preserved: {hb_images}')
    print(f'SQLite database: {DB}')
    print(f'Backup: {backup}')
    print('Sampling timestamps/frequency are NOT provided by this import.')


if __name__ == '__main__':
    main()

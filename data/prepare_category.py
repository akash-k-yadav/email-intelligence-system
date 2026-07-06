# File: data/prepare_category.py
# Builds category training data using the synthetic CSV.
# Labels: Primary, Promotions, Social, Updates
# Output: data/category_train.csv  with feature columns + label

import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import (
    extract_features_from_csv_row,
    FEATURE_COLUMNS,
)


def prepare_category_dataset():
    print("=" * 60)
    print("Preparing Category Dataset — Feature-Based")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ── Step 1: Load CSV ───────────────────────────────────────
    print("\nStep 1: Loading synthetic CSV...")
    csv_path = os.path.join(base_dir, 'data', 'raw', 'category',
                            'email_classification_1M.csv')
    if not os.path.exists(csv_path):
        print(f"ERROR: Not found: {csv_path}")
        return

    df_csv = pd.read_csv(csv_path)
    print(f"Loaded {len(df_csv)} rows")
    print(f"All labels in CSV: {df_csv['label'].unique().tolist()}")

    # ── Step 2: Map labels ─────────────────────────────────────
    # Map CSV label names → display label names
    # We only use 4 category labels here (spam/phishing handled separately)
    label_map = {
        'primary':   'Primary',
        'promotion': 'Promotions',
        'social':    'Social',
        'updates':   'Updates',
    }

    # Filter to only category rows
    df_cat = df_csv[df_csv['label'].isin(label_map.keys())].copy()
    print(f"\nCategory rows found: {len(df_cat)}")
    print(df_cat['label'].value_counts())

    # ── Step 3: Sample & extract features ─────────────────────
    print("\nStep 2: Extracting features...")
    SAMPLES_PER_CLASS = 15000
    all_data = []

    for raw_label, mapped_label in label_map.items():
        df_class = df_cat[df_cat['label'] == raw_label].copy()
        n = min(SAMPLES_PER_CLASS, len(df_class))

        if n == 0:
            print(f"  WARNING: No rows found for label '{raw_label}' — check CSV label names!")
            continue

        df_sample = df_class.sample(n=n, random_state=42)
        for _, row in df_sample.iterrows():
            feat = extract_features_from_csv_row(row)
            feat['label'] = mapped_label
            all_data.append(feat)

        print(f"  {mapped_label}: {n} samples added")

    # ── Step 4: Build DataFrame ────────────────────────────────
    print("\nStep 3: Building final dataset...")
    df = pd.DataFrame(all_data)
    df = df.dropna()
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"\nFinal label distribution:")
    print(df['label'].value_counts())
    print(f"Total: {len(df)} samples")
    print(f"Features used: {FEATURE_COLUMNS}")

    output_path = os.path.join(base_dir, 'data', 'category_train.csv')
    df.to_csv(output_path, index=False)
    print(f"\n✅ Saved to {output_path}")


if __name__ == '__main__':
    prepare_category_dataset()
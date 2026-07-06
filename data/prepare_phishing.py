# File: data/prepare_phishing.py
# Builds phishing training data using ONLY real email datasets.
# Phishing: CEAS_08, Nigerian_Fraud, Nazario, Ling (label=1)
# Legitimate: CEAS_08, Enron, Ling (label=0)
# Output: data/phishing_train.csv  with feature columns + label

import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import (
    extract_features_from_text,
    FEATURE_COLUMNS,
)


def extract_features_from_row(row, has_sender=True) -> dict:
    """
    Extract features from a dataset row.
    Handles both datasets with sender/subject/body/urls
    and datasets with only subject/body.
    """
    subject = str(row.get('subject', '') or '')
    body    = str(row.get('body', '') or '')

    # Sender domain — only available in CEAS_08, Nigerian_Fraud, Nazario
    sender_domain = ''
    if has_sender:
        sender = str(row.get('sender', '') or '')
        if '@' in sender:
            sender_domain = sender.split('@')[-1].strip().strip('>')

    # URLs — count from urls column if available, else regex handles it
    num_links_override = None
    if has_sender and 'urls' in row and row['urls']:
        try:
            # urls column is a string of space/comma separated URLs
            urls_raw = str(row['urls']).strip()
            if urls_raw and urls_raw != 'nan':
                num_links_override = len([u for u in urls_raw.replace(',', ' ').split() if u.startswith('http')])
        except Exception:
            pass

    features = extract_features_from_text(
        subject=subject,
        body=body,
        sender_domain=sender_domain,
        num_attachments=0,
    )

    # Override num_links with actual extracted URLs from urls column if available
    if num_links_override is not None:
        features['num_links'] = num_links_override

    # Zero out is_reply and is_forward — these have no discriminative signal
    # for phishing vs legitimate and cause the model to use them as a shortcut.
    # Spam and category models are NOT affected — separate training pipelines.
    features['is_reply']   = 0
    features['is_forward'] = 0

    return features


def load_dataset(path, label_col, phishing_val, legit_val,
                 has_sender, phishing_limit, legit_limit, all_data):
    """Load one CSV, extract features, append to all_data."""
    if not os.path.exists(path):
        print(f"  WARNING: Not found: {path}")
        return 0, 0

    df = pd.read_csv(path, on_bad_lines='skip')
    print(f"  Loaded {len(df)} rows from {os.path.basename(path)}")

    phishing_added = 0
    legit_added = 0

    # Phishing rows
    if phishing_val is not None and phishing_limit > 0:
        df_phish = df[df[label_col] == phishing_val].dropna(subset=['body'])
        df_phish = df_phish.sample(n=min(phishing_limit, len(df_phish)), random_state=42)
        for _, row in df_phish.iterrows():
            feat = extract_features_from_row(row, has_sender=has_sender)
            feat['label'] = 'phishing'
            all_data.append(feat)
        phishing_added = len(df_phish)

    # Legitimate rows
    if legit_val is not None and legit_limit > 0:
        df_legit = df[df[label_col] == legit_val].dropna(subset=['body'])
        df_legit = df_legit.sample(n=min(legit_limit, len(df_legit)), random_state=42)
        for _, row in df_legit.iterrows():
            feat = extract_features_from_row(row, has_sender=has_sender)
            feat['label'] = 'legitimate'
            all_data.append(feat)
        legit_added = len(df_legit)

    return phishing_added, legit_added


def prepare_phishing_dataset():
    print("=" * 60)
    print("Preparing Phishing Dataset — Real Emails Only")
    print("=" * 60)

    base_dir    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    phishing_dir = os.path.join(base_dir, 'data', 'raw', 'phishing')
    all_data    = []

    # ── Step 1: CEAS_08 — phishing + legitimate ────────────────
    print("\nStep 1: CEAS_08.csv (phishing + legitimate)...")
    p, l = load_dataset(
        path           = os.path.join(phishing_dir, 'CEAS_08.csv'),
        label_col      = 'label',
        phishing_val   = 1,
        legit_val      = 0,
        has_sender     = True,
        phishing_limit = 8000,
        legit_limit    = 8000,
        all_data       = all_data,
    )
    print(f"  Phishing: {p}  |  Legitimate: {l}")

    # ── Step 2: Nigerian_Fraud — phishing only ─────────────────
    print("\nStep 2: Nigerian_Fraud.csv (phishing only)...")
    p, l = load_dataset(
        path           = os.path.join(phishing_dir, 'Nigerian_Fraud.csv'),
        label_col      = 'label',
        phishing_val   = 1,
        legit_val      = None,
        has_sender     = True,
        phishing_limit = 3332,
        legit_limit    = 0,
        all_data       = all_data,
    )
    print(f"  Phishing: {p}")

    # ── Step 3: Nazario — phishing only ───────────────────────
    print("\nStep 3: Nazario.csv (phishing only)...")
    p, l = load_dataset(
        path           = os.path.join(phishing_dir, 'Nazario.csv'),
        label_col      = 'label',
        phishing_val   = 1,
        legit_val      = None,
        has_sender     = True,
        phishing_limit = 1565,
        legit_limit    = 0,
        all_data       = all_data,
    )
    print(f"  Phishing: {p}")

    # ── Step 4: Ling — phishing + legitimate ──────────────────
    print("\nStep 4: Ling.csv (phishing + legitimate)...")
    p, l = load_dataset(
        path           = os.path.join(phishing_dir, 'Ling.csv'),
        label_col      = 'label',
        phishing_val   = 1,
        legit_val      = 0,
        has_sender     = False,
        phishing_limit = 458,
        legit_limit    = 2401,
        all_data       = all_data,
    )
    print(f"  Phishing: {p}  |  Legitimate: {l}")

    # ── Step 5: Enron — legitimate only ───────────────────────
    # NOTE: Only using label=0 rows — Enron label=1 is unreliable
    print("\nStep 5: Enron.csv (legitimate only, label=0)...")
    p, l = load_dataset(
        path           = os.path.join(phishing_dir, 'Enron.csv'),
        label_col      = 'label',
        phishing_val   = None,
        legit_val      = 0,
        has_sender     = False,
        phishing_limit = 0,
        legit_limit    = 8000,
        all_data       = all_data,
    )
    print(f"  Legitimate: {l}")

    # ── Step 6: SpamAssasin ham — legitimate only ──────────────
    # label=0 rows are real ham emails — newsletters, mailing lists,
    # developer digests. Fixes false positives on legitimate emails
    # with technical/security language.
    print("\nStep 6: SpamAssasin.csv (ham only, label=0)...")
    p, l = load_dataset(
        path           = os.path.join(phishing_dir, 'SpamAssasin.csv'),
        label_col      = 'label',
        phishing_val   = None,
        legit_val      = 0,
        has_sender     = True,
        phishing_limit = 0,
        legit_limit    = 4091,
        all_data       = all_data,
    )
    print(f"  Legitimate: {l}")

    # ── Step 7: Build final DataFrame ─────────────────────────
    print("\nStep 7: Building final dataset...")
    df = pd.DataFrame(all_data)
    df = df.dropna()
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"\nFinal label distribution:")
    print(df['label'].value_counts())
    print(f"Total: {len(df)} samples")
    print(f"Features: {FEATURE_COLUMNS}")

    output_path = os.path.join(base_dir, 'data', 'phishing_train.csv')
    df.to_csv(output_path, index=False)
    print(f"\n✅ Saved to {output_path}")


if __name__ == '__main__':
    prepare_phishing_dataset()
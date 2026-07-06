# File: data/prepare_spam.py
# Builds spam training data using:
#   1. Synthetic CSV  (spam / ham labels)
#   2. SpamAssassin   (spam / easy_ham / hard_ham folders)
# Output: data/spam_train.csv  with feature columns + label

import os
import sys
import email
from email import policy
from email.parser import BytesParser
from datetime import datetime
import pandas as pd

# Allow importing feature_extractor from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import extract_features_from_csv_row, extract_features_from_text, FEATURE_COLUMNS


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_spamassassin_email(filepath):
    """Parse a raw SpamAssassin email file and return feature dict."""
    try:
        with open(filepath, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)

        subject = msg.get('Subject', '') or ''
        from_addr = msg.get('From', '') or ''
        date_str = msg.get('Date', '') or ''

        # Extract sender domain
        sender_domain = ''
        if '@' in from_addr:
            sender_domain = from_addr.split('@')[-1].strip().strip('>')

        # Extract body
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except Exception:
                        body += str(part.get_payload())
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except Exception:
                body = str(msg.get_payload())

        # Parse date for hour / day_of_week
        hour, day_of_week = 12, 0
        try:
            dt = email.utils.parsedate_to_datetime(date_str)
            hour = dt.hour
            day_of_week = dt.weekday()
        except Exception:
            pass

        # Attachment count from content-disposition
        num_attachments = sum(
            1 for part in msg.walk()
            if 'attachment' in str(part.get('Content-Disposition', ''))
        )

        subject_lower = subject.lower().strip()
        is_reply = 1 if subject_lower.startswith('re:') else 0
        is_forward = 1 if subject_lower.startswith(('fwd:', 'fw:')) else 0

        features = extract_features_from_text(
            subject=subject,
            body=body,
            sender_domain=sender_domain,
            num_attachments=num_attachments,
            is_reply=is_reply,
            is_forward=is_forward,
            hour=hour,
            day_of_week=day_of_week,
        )
        return features

    except Exception as e:
        return None


def load_spamassassin_folder(folder_path, label, limit=None):
    """Load all emails from a SpamAssassin folder and return list of feature dicts."""
    data = []
    if not os.path.exists(folder_path):
        print(f"  WARNING: Not found: {folder_path}")
        return data

    files = [f for f in os.listdir(folder_path)
             if not f.startswith('.') and f != 'cmds']
    if limit:
        files = files[:limit]

    print(f"  Processing {len(files)} files from {os.path.basename(folder_path)}...")

    for filename in files:
        filepath = os.path.join(folder_path, filename)
        if not os.path.isfile(filepath):
            continue
        features = parse_spamassassin_email(filepath)
        if features:
            features['label'] = label
            data.append(features)

    return data


# ── Main ───────────────────────────────────────────────────────────────────────

def prepare_spam_dataset():
    print("=" * 60)
    print("Preparing Spam Dataset — Feature-Based")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    all_data = []

    # ── Step 1: Synthetic CSV ──────────────────────────────────
    print("\nStep 1: Loading synthetic CSV...")
    csv_path = os.path.join(base_dir, 'data', 'raw', 'category',
                            'email_classification_1M.csv')
    if not os.path.exists(csv_path):
        print(f"  WARNING: CSV not found at {csv_path}")
    else:
        df_csv = pd.read_csv(csv_path)
        print(f"  Loaded {len(df_csv)} rows. Labels: {df_csv['label'].unique().tolist()}")

        # spam rows
        df_spam = df_csv[df_csv['label'] == 'spam'].copy()
        df_spam_sample = df_spam.sample(n=min(8000, len(df_spam)), random_state=42)
        for _, row in df_spam_sample.iterrows():
            feat = extract_features_from_csv_row(row)
            feat['label'] = 'spam'
            all_data.append(feat)
        print(f"  CSV spam rows added: {len(df_spam_sample)}")

        # ham rows — primary, social, updates, promotion are all legitimate
        df_ham_csv = df_csv[df_csv['label'].isin(
            ['primary', 'promotion', 'social', 'updates'])].copy()
        df_ham_sample = df_ham_csv.sample(n=min(8000, len(df_ham_csv)), random_state=42)
        for _, row in df_ham_sample.iterrows():
            feat = extract_features_from_csv_row(row)
            feat['label'] = 'ham'
            all_data.append(feat)
        print(f"  CSV ham rows added: {len(df_ham_sample)}")

    # ── Step 2: SpamAssassin spam ──────────────────────────────
    print("\nStep 2: Loading SpamAssassin spam...")
    for folder_name in ['spam', 'spam_2']:
        folder = os.path.join(base_dir, 'data', 'raw', 'spam', folder_name)
        data = load_spamassassin_folder(folder, label='spam')
        all_data.extend(data)
        print(f"  Added {len(data)} spam from {folder_name}")

    # ── Step 3: SpamAssassin ham ───────────────────────────────
    print("\nStep 3: Loading SpamAssassin ham...")
    for folder_name in ['easy_ham', 'hard_ham']:
        folder = os.path.join(base_dir, 'data', 'raw', 'ham', folder_name)
        data = load_spamassassin_folder(folder, label='ham')
        all_data.extend(data)
        print(f"  Added {len(data)} ham from {folder_name}")

    # ── Step 4: Build DataFrame ────────────────────────────────
    print("\nStep 4: Building final dataset...")
    df = pd.DataFrame(all_data)
    df = df.dropna()
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"\nFinal label distribution:")
    print(df['label'].value_counts())
    print(f"Total: {len(df)} samples")
    print(f"Features: {FEATURE_COLUMNS}")

    output_path = os.path.join(base_dir, 'data', 'spam_train.csv')
    df.to_csv(output_path, index=False)
    print(f"\n✅ Saved to {output_path}")


if __name__ == '__main__':
    prepare_spam_dataset()
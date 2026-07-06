# File: models/predict.py
# Runtime classifier — extracts features from real parsed emails
# and runs them through the three feature-based models.
# No TF-IDF. No text cleaning. Pure numerical features.

import os
import sys
import json
import joblib
import numpy as np
from typing import Dict
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import (
    extract_features_from_text,
    FEATURE_COLUMNS,
)


class EmailClassifier:
    def __init__(self, models_dir='models'):
        self.models_dir = models_dir

        self.spam_model = None
        self.spam_metadata = None

        self.phishing_model = None
        self.phishing_metadata = None

        self.category_model = None
        self.category_metadata = None

        self.otp_metadata = None

        self._load_models()

    def _load_models(self):
        """Load all trained models from disk."""
        try:
            spam_path = os.path.join(self.models_dir, 'spam', 'model.pkl')
            if os.path.exists(spam_path):
                self.spam_model = joblib.load(spam_path)
                with open(os.path.join(self.models_dir, 'spam', 'metadata.json')) as f:
                    self.spam_metadata = json.load(f)
                print(f"Spam model loaded     v{self.spam_metadata.get('version')}")
            else:
                print("WARNING: Spam model not found")

            phishing_path = os.path.join(self.models_dir, 'phishing', 'model.pkl')
            if os.path.exists(phishing_path):
                self.phishing_model = joblib.load(phishing_path)
                with open(os.path.join(self.models_dir, 'phishing', 'metadata.json')) as f:
                    self.phishing_metadata = json.load(f)
                print(f"Phishing model loaded v{self.phishing_metadata.get('version')}")
            else:
                print("WARNING: Phishing model not found")

            category_path = os.path.join(self.models_dir, 'category', 'model.pkl')
            if os.path.exists(category_path):
                self.category_model = joblib.load(category_path)
                with open(os.path.join(self.models_dir, 'category', 'metadata.json')) as f:
                    self.category_metadata = json.load(f)
                print(f"Category model loaded v{self.category_metadata.get('version')}")
            else:
                print("WARNING: Category model not found")

            otp_path = os.path.join(self.models_dir, 'otp', 'metadata.json')
            if os.path.exists(otp_path):
                with open(otp_path) as f:
                    self.otp_metadata = json.load(f)

        except Exception as e:
            print(f"Error loading models: {e}")
            import traceback
            traceback.print_exc()

    def _extract_features(self, parsed_email) -> np.ndarray:
        """
        Extract the 15 numerical features from a parsed email object.
        Returns a numpy array shaped (1, 15) ready for model.predict_proba().
        """
        # Sender domain
        sender_domain = ''
        if parsed_email.from_addr and '@' in parsed_email.from_addr:
            sender_domain = parsed_email.from_addr.split('@')[-1].strip().strip('>')

        # Date-based features
        hour, day_of_week = 12, 0
        try:
            dt = parsed_email.date
            if isinstance(dt, datetime):
                hour = dt.hour
                day_of_week = dt.weekday()
        except Exception:
            pass

        # Reply / forward detection from subject
        subject = str(parsed_email.subject or '')
        subject_lower = subject.lower().strip()
        is_reply = 1 if subject_lower.startswith('re:') else 0
        is_forward = 1 if subject_lower.startswith(('fwd:', 'fw:')) else 0

        # Attachment count from parsed email
        num_attachments = len(getattr(parsed_email, 'attachments', []) or [])

        # Extract all features from text
        features = extract_features_from_text(
            subject=subject,
            body=str(parsed_email.body_text or ''),
            sender_domain=sender_domain,
            num_attachments=num_attachments,
            is_reply=is_reply,
            is_forward=is_forward,
            hour=hour,
            day_of_week=day_of_week,
        )

        # Build feature vector in the exact column order used during training
        vector = np.array([[features[col] for col in FEATURE_COLUMNS]], dtype=float)
        return vector, features

    def classify_email(self, parsed_email) -> Dict:
        """
        Classify a parsed email and return a result dict compatible
        with the existing rules_engine.py and crud.py interfaces.
        """
        feature_vector, raw_features = self._extract_features(parsed_email)

        result = {
            'spam_prob': 0.0,
            'phishing_prob': 0.0,
            'category': 'Primary',
            'category_probs': {},
            'contains_otp': raw_features.get('contains_otp', 0),
            'sender_reputation': raw_features.get('sender_reputation', 0.3),
            'model_versions': {},
        }

        # ── Spam ───────────────────────────────────────────────
        if self.spam_model is not None:
            try:
                proba = self.spam_model.predict_proba(feature_vector)[0]
                # class index 1 = spam
                spam_idx = list(self.spam_model.classes_).index(1)
                result['spam_prob'] = float(proba[spam_idx])
                result['model_versions']['spam'] = self.spam_metadata.get('version', '3.0.0')
            except Exception as e:
                print(f"Spam prediction error: {e}")

        # ── Phishing ───────────────────────────────────────────
        if self.phishing_model is not None:
            try:
                proba = self.phishing_model.predict_proba(feature_vector)[0]
                # XGBoost classes_ = [0, 1]; 1 = phishing
                phishing_idx = list(self.phishing_model.classes_).index(1)
                result['phishing_prob'] = float(proba[phishing_idx])
                result['model_versions']['phishing'] = self.phishing_metadata.get('version', '3.0.0')
            except Exception as e:
                print(f"Phishing prediction error: {e}")

        # ── Category ───────────────────────────────────────────
        if self.category_model is not None:
            try:
                proba = self.category_model.predict_proba(feature_vector)[0]
                pred = self.category_model.predict(feature_vector)[0]
                result['category'] = pred
                result['category_probs'] = {
                    label: float(p)
                    for label, p in zip(self.category_model.classes_, proba)
                }
                result['model_versions']['category'] = self.category_metadata.get('version', '3.0.0')
            except Exception as e:
                print(f"Category prediction error: {e}")

        # OTP version tag
        if self.otp_metadata:
            result['model_versions']['otp'] = self.otp_metadata.get('version', '2.0.0')

        return result


# ── Singleton ──────────────────────────────────────────────────────────────────
_classifier = None


def get_classifier() -> EmailClassifier:
    global _classifier
    if _classifier is None:
        _classifier = EmailClassifier()
    return _classifier


def classify_email(parsed_email) -> Dict:
    """Public convenience function — called by routes.py."""
    return get_classifier().classify_email(parsed_email)
# File: decision/rules_engine.py
import os
from typing import Dict

class RulesEngine:
    def __init__(self):
        # Load thresholds from environment with defaults
        self.phishing_threshold = float(os.getenv('PHISHING_THRESHOLD', '0.97'))
        self.spam_threshold = float(os.getenv('SPAM_THRESHOLD', '0.85'))
        self.confidence_threshold = float(os.getenv('CONFIDENCE_THRESHOLD', '0.5'))
    
    def apply_rules(self, prediction: Dict) -> str:
        """
        Apply priority rules to determine final label.
        Priority: OTP > PHISHING > SPAM > CATEGORY
        OTP is checked first because legitimate password reset emails
        contain phishing keywords (verify, password, reset) and would
        otherwise be wrongly flagged as phishing.
        Trusted senders (reputation >= 0.85) are never labeled PHISHING —
        they go straight to spam/category check instead.
        """
        # Check OTP FIRST — before phishing
        if prediction['contains_otp']:
            return 'OTP'

        # Trusted sender check — skip phishing for high-reputation domains.
        # A email from google.com, youtube.com etc cannot be phishing
        # regardless of content keywords.
        sender_reputation = prediction.get('sender_reputation', 0.3)
        is_trusted_sender = sender_reputation >= 0.85

        # Check phishing — only if sender is NOT trusted
        if not is_trusted_sender:
            if prediction['phishing_prob'] >= self.phishing_threshold:
                return 'PHISHING'

        # Check spam
        if prediction['spam_prob'] >= self.spam_threshold:
            return 'SPAM'

        # Default to category prediction
        category = prediction['category']

        # Map category to uppercase label
        return category.upper()
    
    def get_decision_with_confidence(self, prediction: Dict) -> tuple:
        """Return decision label and confidence score"""
        label = self.apply_rules(prediction)
        
        # Calculate confidence based on label
        if label == 'PHISHING':
            confidence = prediction['phishing_prob']
        elif label == 'SPAM':
            confidence = prediction['spam_prob']
        elif label == 'OTP':
            confidence = 1.0 if prediction['contains_otp'] else 0.0
        else:
            # Use category probability
            category_probs = prediction.get('category_probs', {})
            confidence = category_probs.get(prediction['category'], 0.5)
        
        return label, float(confidence)
# File: db/models.py
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base

class Email(Base):
    __tablename__ = 'emails'
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(255), unique=True, index=True)
    from_addr = Column(String(255), index=True)
    to_addr = Column(String(255))
    subject = Column(Text)
    body_text = Column(Text)
    body_html = Column(Text, nullable=True)
    headers = Column(JSON)
    date_received = Column(DateTime)
    unread = Column(Boolean, default=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    account = Column(String(255), index=True, nullable=True)  # IMAP username that fetched this email
    
    # Relationships
    classifications = relationship('Classification', back_populates='email', cascade='all, delete-orphan')
    feedback = relationship('Feedback', back_populates='email', cascade='all, delete-orphan')

class Classification(Base):
    __tablename__ = 'classifications'
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey('emails.id'), index=True)
    label = Column(String(50), index=True)
    spam_score = Column(Float)
    phishing_score = Column(Float)
    category_scores = Column(JSON)
    contains_otp = Column(Boolean, default=False)
    confidence = Column(Float)
    model_versions = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    email = relationship('Email', back_populates='classifications')

class Feedback(Base):
    __tablename__ = 'feedback'
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey('emails.id'), index=True)
    old_label = Column(String(50))
    new_label = Column(String(50))
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    email = relationship('Email', back_populates='feedback')
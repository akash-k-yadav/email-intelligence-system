# File: db/crud.py
from sqlalchemy.orm import Session, aliased
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from typing import Optional, Dict
from db.models import Email, Classification, Feedback
def save_email(db: Session, parsed_email, classification_result: Dict = None, account: str = None):
    """Save email to database"""
    # Check if email already exists
    existing = db.query(Email).filter(Email.message_id == parsed_email.message_id).first()
    if existing:
        return existing
    
    email = Email(
        message_id=parsed_email.message_id,
        from_addr=parsed_email.from_addr,
        to_addr=parsed_email.to_addr,
        subject=parsed_email.subject,
        body_text=parsed_email.body_text,
        body_html=parsed_email.body_html,
        headers=parsed_email.headers,
        date_received=parsed_email.date,
        unread=parsed_email.unread,
        fetched_at=datetime.utcnow(),
        account=account.lower().strip() if account else None
    )
    
    db.add(email)
    db.commit()
    db.refresh(email)
    
    # Save classification if provided
    if classification_result:
        save_classification(db, email.id, classification_result)
    
    return email

def save_classification(db: Session, email_id: int, classification_result: Dict):
    """Save classification result"""
    from decision.rules_engine import RulesEngine
    
    engine = RulesEngine()
    label, confidence = engine.get_decision_with_confidence(classification_result)
    
    classification = Classification(
        email_id=email_id,
        label=label,
        spam_score=classification_result.get('spam_prob', 0.0),
        phishing_score=classification_result.get('phishing_prob', 0.0),
        category_scores=classification_result.get('category_probs', {}),
        contains_otp=classification_result.get('contains_otp', False),
        confidence=confidence,
        model_versions=classification_result.get('model_versions', {})
    )
    
    db.add(classification)
    db.commit()
    db.refresh(classification)
    
    return classification

def query_emails(
    db: Session,
    folder: Optional[str] = None,
    sender: Optional[str] = None,
    domain: Optional[str] = None,
    keyword: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    unread: Optional[bool] = None,
    account: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    sort_by: str = 'date',
    sort_order: str = 'desc'
):
   

    
    subquery = (
        db.query(
            Classification.email_id,
            func.max(Classification.created_at).label("latest")
        )
        .group_by(Classification.email_id)
        .subquery()
    )

    latest_class = aliased(Classification)

    query = (
        db.query(Email)
        .join(latest_class, Email.id == latest_class.email_id)
        .join(
            subquery,
            (latest_class.email_id == subquery.c.email_id) &
            (latest_class.created_at == subquery.c.latest)
        )
    )
    
    # Apply filters
    if folder:
        query = query.filter(latest_class.label == folder.upper())
    
    if sender:
        if '*' in sender or '%' in sender:
            # Wildcard search
            sender_pattern = sender.replace('*', '%')
            query = query.filter(Email.from_addr.like(sender_pattern))
        else:
            # Exact match or contains
            query = query.filter(Email.from_addr.contains(sender))
    
    if domain:
        query = query.filter(Email.from_addr.like(f'%@{domain}%'))
    
    if keyword:
        query = query.filter(
            or_(
                Email.subject.contains(keyword),
                Email.body_text.contains(keyword)
            )
        )
    
    if date_from:
        query = query.filter(Email.date_received >= date_from)
    
    if date_to:
        query = query.filter(Email.date_received <= date_to)
    
    if unread is not None:
        query = query.filter(Email.unread == unread)
    
    # Filter by account — only show emails belonging to the active IMAP account
    if account:
        query = query.filter(Email.account == account.lower().strip())
    
    # Apply sorting
    if sort_by == 'date':
        order_col = Email.date_received
    elif sort_by == 'sender':
        order_col = Email.from_addr
    elif sort_by == 'label':
        order_col = latest_class.label
    else:
        order_col = Email.date_received
    
    if sort_order == 'desc':
        query = query.order_by(order_col.desc())
    else:
        query = query.order_by(order_col.asc())
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    emails = query.offset(offset).limit(per_page).all()
    
    return emails, total

def get_email_by_id(db: Session, email_id: int):
    """Get email by ID with classification"""
    return db.query(Email).filter(Email.id == email_id).first()

def relabel_email(db: Session, email_id: int, new_label: str, notes: Optional[str] = None):
    """Relabel email and save feedback"""
    # Get current classification
    classification = db.query(Classification).filter(
        Classification.email_id == email_id
    ).order_by(Classification.created_at.desc()).first()
    
    if not classification:
        return None
    
    old_label = classification.label
    
    # Create new classification with updated label
    new_classification = Classification(
        email_id=email_id,
        label=new_label.upper(),
        spam_score=classification.spam_score,
        phishing_score=classification.phishing_score,
        category_scores=classification.category_scores,
        contains_otp=classification.contains_otp,
        confidence=classification.confidence,
        model_versions=classification.model_versions
    )
    
    db.add(new_classification)
    
    # Save feedback
    feedback = Feedback(
        email_id=email_id,
        old_label=old_label,
        new_label=new_label.upper(),
        notes=notes
    )
    
    db.add(feedback)
    db.commit()
    
    return new_classification

def save_feedback(db: Session, email_id: int, old_label: str, new_label: str, notes: Optional[str] = None):
    """Save user feedback"""
    feedback = Feedback(
        email_id=email_id,
        old_label=old_label,
        new_label=new_label,
        notes=notes
    )
    
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    
    return feedback

def get_stats(db: Session, account: Optional[str] = None):
    """Get statistics — optionally filtered to one account"""
    # Count by label
    # Only count the LATEST classification per email — not historical relabels
    subquery = (
        db.query(
            Classification.email_id,
            func.max(Classification.created_at).label('latest')
        )
        .group_by(Classification.email_id)
        .subquery()
    )

    label_counts_query = (
        db.query(
            Classification.label,
            func.count(Classification.id)
        )
        .join(
            subquery,
            (Classification.email_id == subquery.c.email_id) &
            (Classification.created_at == subquery.c.latest)
        )
        .join(Email, Email.id == Classification.email_id)
    )
    if account:
        label_counts_query = label_counts_query.filter(
            Email.account == account.lower().strip()
        )
    label_counts = label_counts_query.group_by(Classification.label).all()
    
    # Last 7 days processed
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_counts_query = db.query(
        func.date(Email.fetched_at).label('date'),
        func.count(Email.id).label('count')
    ).filter(Email.fetched_at >= seven_days_ago)
    if account:
        daily_counts_query = daily_counts_query.filter(
            Email.account == account.lower().strip()
        )
    daily_counts = daily_counts_query.group_by(func.date(Email.fetched_at)).all()
    
    # Model versions
    latest_classification = db.query(Classification).order_by(
        Classification.created_at.desc()
    ).first()
    
    model_versions = latest_classification.model_versions if latest_classification else {}
    
    return {
        'label_counts': {label: count for label, count in label_counts},
        'daily_counts': [
            {'date': str(date), 'count': count} 
            for date, count in daily_counts
        ],
        'model_versions': model_versions
    }
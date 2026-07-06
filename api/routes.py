# File: api/routes.py

from dotenv import load_dotenv
load_dotenv()

from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
from db.database import get_db_session
from db import crud
from models.predict import classify_email
from parser.email_parser import EmailParser
# from connectors.gmail_connector import GmailConnector
from connectors.imap_connector import IMAPConnector
import traceback
import os

api_bp = Blueprint('api', __name__)

@api_bp.route('/')
def index():
    """Home page - redirect to inbox"""
    return render_template('inbox.html')

@api_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@api_bp.route('/me', methods=['GET'])
def get_current_account():
    """Return the currently configured IMAP account"""
    try:
        from dotenv import dotenv_values
        import pathlib
        env_path = pathlib.Path(__file__).resolve().parents[1] / '.env'
        env_vars = dotenv_values(env_path)
        username = env_vars.get('IMAP_USERNAME', '').strip().lower()
        return jsonify({'account': username})
    except Exception as e:
        return jsonify({'account': '', 'error': str(e)})


@api_bp.route('/fetch', methods=['POST'])
def fetch_emails():
    """Fetch emails from source"""
    try:
        data = request.get_json() or {}
        source = data.get('source') or os.getenv('EMAIL_SOURCE', 'imap')
        limit = int(data.get('limit', 10))
        mailbox = data.get('mailbox', 'INBOX')

        if source == 'imap':
            connector = IMAPConnector()
            raw_emails = connector.fetch_emails(limit=limit, mailbox=mailbox)
            parser_func = EmailParser.parse_imap_message
            # Read the active account directly from .env (same way connector does)
            from dotenv import dotenv_values
            import pathlib
            env_path = pathlib.Path(__file__).resolve().parents[1] / '.env'
            active_account = dotenv_values(env_path).get('IMAP_USERNAME', '').strip().lower()
        # dead code now ,gmail connector not in this version  
        # elif source == 'gmail':
        #     connector = GmailConnector()
        #     raw_emails = connector.fetch_emails(limit=limit, mailbox=mailbox)
        #     parser_func = EmailParser.parse_gmail_message
        #     active_account = os.getenv('GMAIL_USERNAME', '').strip().lower()

        else:
            return jsonify({'error': f'Invalid email source: {source}'}), 400

        db = get_db_session()
        processed = 0

        for raw_email in raw_emails:
            try:
                parsed = parser_func(raw_email)
                classification = classify_email(parsed)
                crud.save_email(db, parsed, classification, account=active_account)
                processed += 1
            except Exception as e:
                print(f"Error processing email: {e}")
                continue

        db.close()

        return jsonify({
            'success': True,
            'fetched': len(raw_emails),
            'processed': processed
        })

    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@api_bp.route('/emails', methods=['GET'])
def get_emails():
    """Get emails with filters"""
    try:
        # Parse query parameters
        folder     = request.args.get('folder')
        sender     = request.args.get('sender')
        domain     = request.args.get('domain')
        keyword    = request.args.get('keyword')
        unread     = request.args.get('unread')
        account    = request.args.get('account', '').strip().lower() or None
        page       = int(request.args.get('page', 1))
        per_page   = int(request.args.get('per_page', 50))
        sort_by    = request.args.get('sort_by', 'date')
        sort_order = request.args.get('sort_order', 'desc')

        # Only pass non-empty values — empty string means no filter
        if sender  == '': sender  = None
        if domain  == '': domain  = None
        if keyword == '': keyword = None

        # Parse dates
        date_from = None
        date_to   = None

        if request.args.get('date_from'):
            date_from = datetime.fromisoformat(request.args.get('date_from'))

        if request.args.get('date_to'):
            date_to = datetime.fromisoformat(request.args.get('date_to'))
            # ── FIX: include the full date_to day, not just midnight ──
            date_to = date_to.replace(hour=23, minute=59, second=59)

        # Parse unread boolean — only filter if explicitly 'true'
        if unread is not None:
            unread = unread.lower() in ['true', '1', 'yes']
        else:
            unread = None

        db = get_db_session()
        emails, total = crud.query_emails(
            db, folder=folder, sender=sender, domain=domain,
            keyword=keyword, date_from=date_from, date_to=date_to,
            unread=unread, account=account, page=page, per_page=per_page,
            sort_by=sort_by, sort_order=sort_order
        )

        result = []
        for email in emails:
            classification = email.classifications[-1] if email.classifications else None
            result.append({
                'id':         email.id,
                'message_id': email.message_id,
                'from':       email.from_addr,
                'to':         email.to_addr,
                'subject':    email.subject,
                'date':       email.date_received.isoformat(),
                'unread':     email.unread,
                'label':      classification.label      if classification else 'UNKNOWN',
                'confidence': classification.confidence if classification else 0.0
            })

        db.close()

        return jsonify({
            'emails':   result,
            'total':    total,
            'page':     page,
            'per_page': per_page,
            'pages':    (total + per_page - 1) // per_page
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/emails/<int:email_id>', methods=['GET'])
def get_email(email_id):
    """Get email by ID and mark as read"""
    try:
        db = get_db_session()
        email = crud.get_email_by_id(db, email_id)

        if not email:
            db.close()
            return jsonify({'error': 'Email not found'}), 404

        # ── FIX: Mark as read when opened ──
        if email.unread:
            email.unread = False
            db.commit()

        classification = email.classifications[-1] if email.classifications else None

        result = {
            'id':         email.id,
            'message_id': email.message_id,
            'from':       email.from_addr,
            'to':         email.to_addr,
            'subject':    email.subject,
            'body_text':  email.body_text,
            'body_html':  email.body_html,
            'headers':    email.headers,
            'date':       email.date_received.isoformat(),
            'unread':     email.unread,
            'classification': {
                'label':           classification.label,
                'spam_score':      classification.spam_score,
                'phishing_score':  classification.phishing_score,
                'category_scores': classification.category_scores,
                'contains_otp':    classification.contains_otp,
                'confidence':      classification.confidence,
                'model_versions':  classification.model_versions
            } if classification else None
        }

        db.close()
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/emails/<int:email_id>/relabel', methods=['POST'])
def relabel_email_route(email_id):
    """Relabel email"""
    try:
        data      = request.get_json()
        new_label = data.get('label', '').upper()
        notes     = data.get('notes')

        # ── FIX: ADVERTISEMENT removed from valid labels ──
        valid_labels = ['SPAM', 'PHISHING', 'PRIMARY', 'PROMOTIONS',
                        'SOCIAL', 'UPDATES', 'OTP']

        if new_label not in valid_labels:
            return jsonify({'error': 'Invalid label'}), 400

        db = get_db_session()
        classification = crud.relabel_email(db, email_id, new_label, notes)

        if not classification:
            db.close()
            return jsonify({'error': 'Email not found'}), 404

        db.close()
        return jsonify({'success': True, 'new_label': new_label})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get statistics — filtered by active account"""
    try:
        account = request.args.get('account', '').strip().lower() or None
        db = get_db_session()
        stats = crud.get_stats(db, account=account)
        db.close()
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/search', methods=['GET'])
def search():
    """Search emails (alias for /emails with filters)"""
    return get_emails()


# ── UI Routes ──────────────────────────────────────────────
@api_bp.route('/inbox')
def inbox():
    """Inbox page"""
    return render_template('inbox.html')

@api_bp.route('/email/<int:email_id>')
def email_detail(email_id):
    """Email detail page"""
    return render_template('email_detail.html')

@api_bp.route('/statistics')
def statistics():
    """Statistics page"""
    return render_template('stats.html')


@api_bp.route('/update_env', methods=['POST'])
def update_env():
    """Update IMAP credentials in .env file"""
    try:
        data     = request.get_json()
        email    = data.get('email', '').strip()
        password = data.get('password', '').strip()

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required.'}), 400

        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()

        keys_to_set = {'IMAP_USERNAME': email, 'IMAP_PASSWORD': password}
        keys_found  = {k: False for k in keys_to_set}

        new_lines = []
        for line in lines:
            matched = False
            for key in keys_to_set:
                if line.startswith(f'{key}=') or line.startswith(f'{key} ='):
                    new_lines.append(f'{key}={keys_to_set[key]}\n')
                    keys_found[key] = True
                    matched = True
                    break
            if not matched:
                new_lines.append(line)

        for key, found in keys_found.items():
            if not found:
                new_lines.append(f'{key}={keys_to_set[key]}\n')

        with open(env_path, 'w') as f:
            f.writelines(new_lines)

        return jsonify({'success': True, 'message': 'Credentials updated. Restart app to apply changes.'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/clear_emails', methods=['POST'])
def clear_emails():
    """Delete all emails from database"""
    try:
        from db.database import SessionLocal
        from db.models import Email

        db = SessionLocal()
        db.query(Email).delete()
        db.commit()
        db.close()

        return jsonify({"success": True, "message": "All emails cleared."})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
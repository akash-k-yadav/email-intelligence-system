# Environment Configuration Guide

This file explains every variable in `.env.template`. Copy it to `.env` and fill in your own values.

```bash
copy .env.template .env
```


---

## Database Configuration

```env
DATABASE_URL=sqlite:///email_intelligence.db
```

SQLite is the default and requires no setup — works out of the box. No changes needed unless you're switching to PostgreSQL or MySQL for production use.

---

## Flask Application Configuration

```env
SECRET_KEY=change-this-to-a-random-secret-key-in-production
PORT=5000
```

Don't leave `SECRET_KEY` as the default. Generate a real one:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output into `SECRET_KEY`.

---

## Email Source Configuration

```env
EMAIL_SOURCE=imap
```

Keep this as `imap` — it's the only fetch method implemented in this version.

---

## IMAP Configuration — Required

This is the core configuration the project depends on to actually fetch emails.

```env
IMAP_SERVER=imap.gmail.com
IMAP_USERNAME=your-email@gmail.com
IMAP_PASSWORD=your-app-specific-password
IMAP_PORT=993
```

### If you're using Gmail:

1. Enable **2-Step Verification** on your Google Account — required before App Passwords work
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. App: **Mail**, Device: **Other** → name it anything (e.g. `EmailIntelligenceSystem`)
4. Copy the generated **16-character password** — shown only once
5. Paste it into `IMAP_PASSWORD` — **not your real Gmail password**
6. Also enable IMAP access: Gmail → Settings → **Forwarding and POP/IMAP** → Enable IMAP → Save

### If you're using a different mail provider:

Change `IMAP_SERVER` to match your provider. Common examples:

| Provider | IMAP Server | Port |
|---|---|---|
| Gmail | `imap.gmail.com` | 993 |
| Outlook / Hotmail | `outlook.office365.com` | 993 |
| Yahoo Mail | `imap.mail.yahoo.com` | 993 |
| Zoho Mail | `imap.zoho.com` | 993 |

Most providers require an app-specific password rather than your account password if 2FA is enabled — check your provider's account security settings for an equivalent option.

---

## Machine Learning Model Thresholds

```env
PHISHING_THRESHOLD=0.97
SPAM_THRESHOLD=0.85
CONFIDENCE_THRESHOLD=0.5
```

These control how the rule engine interprets model scores:

- **`PHISHING_THRESHOLD`** — minimum XGBoost confidence required to label an email PHISHING. Set high intentionally — the phishing model is tuned aggressively, so even at this threshold it can flag legitimate senders. This is handled separately by the trusted domain reputation system, not by this threshold alone.
- **`SPAM_THRESHOLD`** — minimum Random Forest confidence required to label an email SPAM
- **`CONFIDENCE_THRESHOLD`** — general fallback confidence floor used by the rule engine

Lowering these values catches more threats but increases false positives. Raising them reduces false positives but risks missing real threats — there is no universally "correct" value, it depends on how conservative or aggressive you want detection to be.

---

## Quick Checklist Before Running

- [ ] 2-Step Verification enabled on your email account
- [ ] App password generated
- [ ] IMAP access enabled in mail provider settings
- [ ] `.env` created from `.env.template`
- [ ] `IMAP_USERNAME` and `IMAP_PASSWORD` filled in correctly
- [ ] `SECRET_KEY` regenerated, not left as default
- [ ] `.env` confirmed in `.gitignore` — verify with `git status` that it does NOT appear as a tracked/staged file

---

## If Credentials Are Ever Accidentally Committed

1. **Revoke the app password immediately** in your account security settings
2. Generate a new one
3. Deleting the file in a later commit is **not enough** — it remains in git history. Treat the old credential as permanently compromised and rotate it; rewriting history is a separate, more advanced step if you need it fully scrubbed.

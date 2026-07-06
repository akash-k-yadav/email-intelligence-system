import os
import imaplib
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


class IMAPConnector:
    def __init__(self):
        self.server = os.getenv("IMAP_SERVER")
        self.port = int(os.getenv("IMAP_PORT", 993))

        if not self.server:
            raise RuntimeError("IMAP server not configured")

        self.mail = None

    def connect(self):
        import imaplib
        from dotenv import dotenv_values

   
        env_vars = dotenv_values(ENV_PATH)

        username = env_vars.get("IMAP_USERNAME")
        password = env_vars.get("IMAP_PASSWORD")

        

        if not username or not password:
            raise RuntimeError("IMAP credentials missing")

        self.mail = imaplib.IMAP4_SSL(self.server, self.port)
        self.mail.login(username, password)

    def fetch_emails(self, limit=50, mailbox="INBOX"):
        self.connect()
        self.mail.select(mailbox)

        status, messages = self.mail.search(None, "ALL")
        email_ids = messages[0].split()

        # Get newest emails first
        email_ids = email_ids[::-1][:limit]

        raw_emails = []
        for eid in email_ids:
            _, data = self.mail.fetch(eid, "(RFC822)")

            raw_emails.append({
                "raw": data[0][1],
                "id": eid.decode() if isinstance(eid, bytes) else str(eid)
            })

        self.mail.logout()
        return raw_emails
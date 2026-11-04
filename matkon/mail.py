"""Matkon's few emails (invites and codes), through an SMTP server, like Proton Mail Bridge on the
same machine: STARTTLS, then AUTH, one message per connection.

Where it sends from: MATKON_MAIL, or STATE/mail.json (600, never in git):
  {"host": "127.0.0.1", "port": 1025, "user": "...", "pass": "...", "from": "Matkon <support@example.com>"}
No file means no email: the owner gets each invite's code to pass on by hand.
MATKON_MAIL=outbox writes each message to STATE/outbox.jsonl instead (for tests and the demo).
"""
import json
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from . import config

LOCAL = {"127.0.0.1", "::1", "localhost"}


def _cfg():
    where = os.environ.get("MATKON_MAIL") or str(config.STATE / "mail.json")
    if where == "outbox":
        return "outbox"
    try:
        c = json.loads(open(where).read())
    except (OSError, ValueError):
        return None
    return c if c.get("from") else None


def available():
    return _cfg() is not None


def send(to, subject, text):
    """True when it went out."""
    c = _cfg()
    if c is None:
        return False
    if c == "outbox":
        with open(config.STATE / "outbox.jsonl", "a") as f:
            f.write(json.dumps({"at": int(time.time()), "to": to, "subject": subject, "text": text}, ensure_ascii=False) + "\n")
        return True
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = c["from"], to, subject
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=c["from"].split("@")[-1].strip(">"))
    m.set_content(text)
    host = c.get("host", "127.0.0.1")
    ctx = ssl.create_default_context()
    if host in LOCAL:                       # Bridge's certificate is its own: fine on this machine only
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with smtplib.SMTP(host, int(c.get("port", 25)), timeout=20) as s:
            s.starttls(context=ctx)
            if c.get("user"):
                s.login(c["user"], c.get("pass", ""))
            s.send_message(m)
        return True
    except (OSError, smtplib.SMTPException) as e:
        print("mail to", to, "failed:", e, flush=True)
        return False

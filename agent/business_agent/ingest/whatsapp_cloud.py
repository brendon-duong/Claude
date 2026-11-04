"""Webhook receiver for the official WhatsApp Business Cloud API.

This is the only supported way to read WhatsApp programmatically. Messages sent
to your *business* number arrive here as webhooks; your personal chats do not,
and no legitimate API exposes them.

    python3 -m business_agent.ingest.whatsapp_cloud --inbox inbox --port 8080

Environment:
    WHATSAPP_VERIFY_TOKEN  any string you also paste into the Meta dashboard
    WHATSAPP_APP_SECRET    your Meta app secret, used to verify signatures

Put this behind HTTPS (Cloudflare Tunnel or ngrok are the easy options on a
Mac mini) and point the Meta webhook at https://your-host/webhook.

Standard library only, on purpose: an unattended box should have as few moving
parts as you can manage.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

log = logging.getLogger("whatsapp_cloud")

MAX_BODY_BYTES = 1_000_000


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Confirm Meta actually sent this. Without it, anyone can post you fake
    dropouts and steer the roster."""
    if not app_secret:
        return False
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256=") :])


def extract_messages(payload: dict) -> list[dict]:
    """Pull the interesting bits out of Meta's deeply nested webhook shape."""
    records: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {
                contact.get("wa_id"): contact.get("profile", {}).get("name", "")
                for contact in value.get("contacts", [])
            }
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue  # images, audio and stickers carry no roster signal
                sender_id = message.get("from", "")
                try:
                    sent_at = datetime.fromtimestamp(
                        int(message.get("timestamp", 0)), tz=timezone.utc
                    )
                except (TypeError, ValueError):
                    sent_at = datetime.now(timezone.utc)
                records.append(
                    {
                        "id": message.get("id", ""),
                        "sent_at": sent_at.isoformat(),
                        "sender": contacts.get(sender_id) or sender_id,
                        "text": message.get("text", {}).get("body", ""),
                        "channel": "whatsapp",
                        "chat": value.get("metadata", {}).get("display_phone_number", ""),
                    }
                )
    return records


def append_to_inbox(inbox: Path, records: list[dict]) -> int:
    """Append to a per-day file, skipping message ids already stored.

    Meta retries webhooks it thinks failed, so the same dropout can arrive
    several times. Without this you would ask three people to cover one shift.
    """
    if not records:
        return 0
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"whatsapp-{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    seen: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line).get("id", ""))
            except json.JSONDecodeError:
                continue

    written = 0
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            if record["id"] and record["id"] in seen:
                continue
            handle.write(json.dumps(record) + "\n")
            written += 1
    return written


class WebhookHandler(BaseHTTPRequestHandler):
    inbox: Path = Path("inbox")
    verify_token: str = ""
    app_secret: str = ""

    def log_message(self, fmt: str, *args) -> None:  # quieter default logging
        log.info("%s - %s", self.address_string(), fmt % args)

    def _respond(self, status: int, body: str = "") -> None:
        payload = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        """Meta's one-time subscription handshake."""
        query = parse_qs(urlparse(self.path).query)
        mode = query.get("hub.mode", [""])[0]
        token = query.get("hub.verify_token", [""])[0]
        challenge = query.get("hub.challenge", [""])[0]
        if mode == "subscribe" and hmac.compare_digest(token, self.verify_token):
            self._respond(200, challenge)
        else:
            self._respond(403, "verification failed")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._respond(413, "too large")
            return
        body = self.rfile.read(length)

        if not verify_signature(self.app_secret, body, self.headers.get("X-Hub-Signature-256")):
            log.warning("rejected a webhook with a bad signature")
            self._respond(403, "bad signature")
            return

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, "bad json")
            return

        # Always 200 quickly. Meta retries anything else, and a retry storm on
        # a home internet connection is not what you want.
        written = append_to_inbox(self.inbox, extract_messages(payload))
        if written:
            log.info("stored %d new message(s)", written)
        self._respond(200, "ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WhatsApp Cloud API webhook receiver.")
    parser.add_argument("--inbox", default="inbox")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    WebhookHandler.inbox = Path(args.inbox)
    WebhookHandler.verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    WebhookHandler.app_secret = os.environ.get("WHATSAPP_APP_SECRET", "")

    if not WebhookHandler.verify_token or not WebhookHandler.app_secret:
        print(
            "Set WHATSAPP_VERIFY_TOKEN and WHATSAPP_APP_SECRET before starting.",
            file=sys.stderr,
        )
        return 2

    server = ThreadingHTTPServer((args.host, args.port), WebhookHandler)
    log.info("listening on http://%s:%d -> %s", args.host, args.port, args.inbox)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

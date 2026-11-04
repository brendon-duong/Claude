"""Ways messages get into the inbox directory.

Each ingest writes .jsonl lines that messages.parse_jsonl understands. The rest
of the agent never learns which channel a message came from.
"""

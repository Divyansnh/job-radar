"""Parse manual contact lists pasted by the user."""

from __future__ import annotations

import re

from job_radar.email_finder import emails_in_text

_LINE_RE = re.compile(
    r"^\s*(?P<name>[^|,@\n]+?)\s*[|,]\s*(?P<email>[^\s|,]+@[^\s|,]+)"
    r"(?:\s*[|,]\s*(?P<linkedin>https?://\S+))?\s*$",
    re.IGNORECASE,
)


def parse_contact_lines(text: str) -> list[dict[str, str]]:
    """
    Accept lines like:
      Jane Doe | jane@co.com | https://linkedin.com/in/jane
      jane@co.com
      Jane Doe, jane@co.com
    """
    contacts: list[dict[str, str]] = []
    seen: set[str] = set()

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        name = ""
        email = ""
        linkedin = ""

        m = _LINE_RE.match(line)
        if m:
            name = (m.group("name") or "").strip()
            email = (m.group("email") or "").strip().lower()
            linkedin = (m.group("linkedin") or "").strip()
        else:
            found = emails_in_text(line)
            if not found:
                continue
            email = found[0].lower()
            rest = line.replace(email, "").strip(" ,|")
            if rest and "@" not in rest and not rest.startswith("http"):
                name = rest

        if not email or email in seen:
            continue
        seen.add(email)
        contacts.append(
            {
                "name": name,
                "email": email,
                "linkedin_url": linkedin,
            }
        )

    return contacts

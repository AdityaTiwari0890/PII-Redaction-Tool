import re

_PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.in", "yahoo.in",
    "hotmail.com", "hotmail.co.in", "outlook.com", "outlook.in",
    "live.com", "live.in", "rediffmail.com", "icloud.com",
    "me.com", "mac.com", "protonmail.com", "proton.me",
    "zohomail.com", "ymail.com", "aol.com",
}

_STATUTORY_DOMAINS = {
    "sebi.gov.in", "rbi.org.in", "bseindia.com", "nseindia.com",
    "nsdl.co.in", "cdsl.com", "mca.gov.in", "incometax.gov.in",
    "irdai.gov.in",
}


def is_personal_email(email: str) -> bool:
    email = email.strip().lower()
    try:
        _, domain = email.rsplit("@", 1)
    except ValueError:
        return False

    if domain in _STATUTORY_DOMAINS:
        return False

    if domain in _PERSONAL_DOMAINS:
        return True

    for pd in _PERSONAL_DOMAINS:
        if domain.endswith(f".{pd}"):
            return True

    return False


def is_company_email(email: str) -> bool:
    email_l = email.strip().lower()
    try:
        _, domain = email_l.rsplit("@", 1)
    except ValueError:
        return False
    if domain in _STATUTORY_DOMAINS:
        return False
    return not is_personal_email(email)


_TOLL_FREE_RE = re.compile(r"^\+?(?:91)?1800", re.ASCII)
_FAX_CONTEXT_RE = re.compile(r"\bfax\b", re.IGNORECASE)


def is_personal_phone(phone: str, context: str = "") -> bool:
    digits = re.sub(r"\D", "", phone)
    if _TOLL_FREE_RE.match(digits):
        return False
    if _FAX_CONTEXT_RE.search(context):
        return False
    return True


def add_personal_domain(domain: str) -> None:
    _PERSONAL_DOMAINS.add(domain.lower().strip())


def add_statutory_domain(domain: str) -> None:
    _STATUTORY_DOMAINS.add(domain.lower().strip())

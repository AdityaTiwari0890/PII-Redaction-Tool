import re
from typing import List, Optional
from redactor.detectors import PIIDetector, PIISpan

_ADDR_KEYWORDS = re.compile(
    r"\b(?:Village|Plot\s+No|Survey\s+No|Gat\s+No|Tower|Floor|"
    r"Road|Street|Lane|Block|Sector|Phase|Wing|Unit|"
    r"District|Taluka|Taluk|Tehsil|Maharashtra|Karnataka|Gujarat|"
    r"Rajasthan|Andhra\s+Pradesh|Telangana|Tamil\s+Nadu|Uttar\s+Pradesh|"
    r"Madhya\s+Pradesh|Bihar|Odisha|Jharkhand|Chhattisgarh|Haryana|"
    r"Delhi|Mumbai|Pune|Bangalore|Bengaluru|Chennai|Kolkata|Hyderabad|"
    r"Ahmedabad|Surat|Jaipur|Lucknow|Kanpur|Nagpur|Nashik|Thane|"
    r"Pincode|Pin\s+Code|Navi\s+Mumbai|Panvel|Raigad|Chakan|Khed|"
    r"Baner|Vikhroli|Andheri|Kurla|Bandra|Mulund|Powai|Hinjewadi|"
    r"Wakad|Aundh|Kothrud|Kharadi|Hadapsar|Yerwada|Shivajinagar|"
    r"BKC|G\s*Block|Nariman\s+Point|Fort|Churchgate|Lower\s+Parel|"
    r"Industrial\s+Area|Industrial\s+Estate|SEZ|MIDC|IT\s+Park)\b",
    re.IGNORECASE,
)

_PIN_CODE = re.compile(r"\b\d{6}\b")

_STATUTORY_LABEL = re.compile(
    r"^(?:Registered\s+Office|Corporate\s+Office|Head\s+Office|"
    r"Principal\s+Office|Regd\.?\s+Office|Correspondence\s+Address|"
    r"Mailing\s+Address|Office\s+Address)\s*[:\-]?\s*",
    re.IGNORECASE,
)

_PERSONAL_LABEL = re.compile(
    r"(?:Residential\s+Address|Home\s+Address|Personal\s+Address|"
    r"Address\s+of|address\s+for\s+correspondence)\s*[:\-]?\s*",
    re.IGNORECASE,
)


def _is_address_line(line: str) -> bool:
    return bool(_ADDR_KEYWORDS.search(line) or _PIN_CODE.search(line))


def _value_after_label(line: str, label_match: re.Match) -> Optional[str]:
    val = line[label_match.end():].strip()
    return val if len(val) >= 10 else None


class AddressDetector(PIIDetector):
    label = "ADDRESS"

    def __init__(self, preserve_statutory: bool = True):
        self._preserve = preserve_statutory

    def detect(self, text: str) -> List[PIISpan]:
        out = []
        lines = text.split("\n")
        cursor = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                cursor += len(line) + 1
                i += 1
                continue

            stat_m = _STATUTORY_LABEL.match(stripped)
            if stat_m:
                val = _value_after_label(stripped, stat_m)
                if val:
                    value_offset = stripped.index(val)
                    abs_start = cursor + (len(line) - len(stripped)) + value_offset
                    out.append(
                        PIISpan(abs_start, abs_start + len(val), val, self.label, 0.95)
                    )
                else:
                    j = i + 1
                    while j < len(lines) and j <= i + 4:
                        nxt = lines[j].strip()
                        if nxt and _is_address_line(nxt):
                            nxt_cursor = cursor + sum(
                                len(lines[k]) + 1 for k in range(i + 1, j + 1)
                            ) - len(lines[j]) - 1
                            nxt_stripped_off = len(lines[j]) - len(lines[j].lstrip())
                            abs_start = nxt_cursor + nxt_stripped_off
                            out.append(
                                PIISpan(abs_start, abs_start + len(nxt), nxt, self.label, 0.90)
                            )
                        j += 1

                cursor += len(line) + 1
                i += 1
                continue

            pers_m = _PERSONAL_LABEL.match(stripped)
            if pers_m:
                val = _value_after_label(stripped, pers_m)
                if val:
                    value_offset = stripped.index(val)
                    abs_start = cursor + (len(line) - len(stripped)) + value_offset
                    out.append(
                        PIISpan(abs_start, abs_start + len(val), val, self.label, 0.95)
                    )
                cursor += len(line) + 1
                i += 1
                continue

            if _is_address_line(stripped):
                leading_ws = len(line) - len(stripped)
                abs_start = cursor + leading_ws
                out.append(
                    PIISpan(abs_start, abs_start + len(stripped), stripped, self.label, 0.75)
                )

            cursor += len(line) + 1
            i += 1

        return out


def cell_looks_like_address(cell_text: str) -> bool:
    return _is_address_line(cell_text) or len(cell_text.split(",")) >= 3

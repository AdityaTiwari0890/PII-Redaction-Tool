import pytest
from redactor.detectors import (
    EmailDetector, PhoneDetector, IPDetector, SSNDetector,
    CreditCardDetector, DOBDetector, PANDetector, CINDetector,
)
from redactor.classify import is_personal_email, is_personal_phone


def test_email_personal_detected():
    det = EmailDetector()
    spans = det.detect("Contact rashi.patil@gmail.com for details.")
    assert len(spans) == 1
    assert spans[0].text == "rashi.patil@gmail.com"
    assert spans[0].label == "EMAIL"


def test_email_image_filename_not_flagged():
    det = EmailDetector()
    spans = det.detect("See file logo@2x.png for reference.")
    assert all(not s.text.endswith(".png") for s in spans)


def test_phone_plus91_detected():
    det = PhoneDetector()
    spans = det.detect("Call +91 98765 43210 now.")
    assert len(spans) == 1
    assert "+91" in spans[0].text


def test_phone_invalid_rejected():
    det = PhoneDetector()
    spans = det.detect("Ref: +91 1234 5678")
    assert len(spans) == 0


def test_ip_valid_detected():
    det = IPDetector()
    spans = det.detect("Server at 192.168.1.42 responded.")
    assert len(spans) == 1
    assert spans[0].text == "192.168.1.42"


def test_ip_invalid_octet_rejected():
    det = IPDetector()
    spans = det.detect("Bad IP 999.168.1.1 here.")
    assert len(spans) == 0


def test_ssn_valid_detected():
    det = SSNDetector()
    spans = det.detect("SSN: 123-45-6789")
    assert len(spans) == 1
    assert spans[0].label == "SSN"


def test_ssn_invalid_area_rejected():
    det = SSNDetector()
    spans = det.detect("SSN: 000-45-6789")
    assert len(spans) == 0


def test_credit_card_valid_detected():
    det = CreditCardDetector()
    spans = det.detect("Card: 4111 1111 1111 1111")
    assert len(spans) == 1
    assert spans[0].label == "CREDIT_CARD"


def test_credit_card_luhn_fail_rejected():
    det = CreditCardDetector()
    spans = det.detect("Card: 4111 1111 1111 1112")
    assert len(spans) == 0


def test_dob_context_detected():
    det = DOBDetector()
    spans = det.detect("Date of birth: 15/08/1990 as per records.")
    assert len(spans) == 1
    assert spans[0].label == "DOB"


def test_pan_valid_detected():
    det = PANDetector()
    spans = det.detect("Taxpayer PAN: ABCDE1234F")
    assert len(spans) == 1
    assert spans[0].text == "ABCDE1234F"


def test_cin_valid_detected():
    det = CINDetector()
    spans = det.detect("CIN: U72900MH2018PTC310447")
    assert len(spans) == 1
    assert spans[0].label == "CIN"


def test_classify_personal_email():
    assert is_personal_email("user@gmail.com") is True
    assert is_personal_email("admin@sebi.gov.in") is False
    assert is_personal_email("info@acmecorp.com") is False


def test_classify_toll_free_phone():
    assert is_personal_phone("+911800123456") is False
    assert is_personal_phone("+91 98765 43210") is True

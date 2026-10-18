from s2a import parse

ACCEPT = """# Verification
## Acceptance criteria
AC1 — PASS — test ran
## Unchanged behaviour
UB1 — PASS — ok
## Defects
(none)
VERDICT: ACCEPT
"""


def test_accept() -> None:
    v = parse.verdict(ACCEPT)
    assert v.stated == "ACCEPT" and v.derived == "ACCEPT" and v.defects == [] and v.lines == {"AC1": "PASS", "UB1": "PASS"}


def test_fail_line_overrides_accept() -> None:
    v = parse.verdict(ACCEPT.replace("UB1 — PASS", "UB1 — FAIL"))
    assert v.stated == "ACCEPT" and v.derived == "REJECT"


def test_reject_with_defects_and_missing_verdict() -> None:
    v = parse.verdict("AC1 — FAIL — no\n## Defects\n1. B.java:12 speed not saved\nVERDICT: REJECT")
    assert v.derived == "REJECT" and v.defects == ["B.java:12 speed not saved"]
    assert parse.verdict("AC1 — PASS").derived is None

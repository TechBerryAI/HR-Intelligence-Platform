"""Company name matching for org-scoped job access."""


def normalize_company(name: str | None) -> str:
    s = (name or '').strip().lower()
    for suffix in (
        ' private limited',
        ' pvt. ltd.',
        ' pvt ltd.',
        ' pvt. ltd',
        ' pvt ltd',
        ' ltd.',
        ' ltd',
        ' inc.',
        ' inc',
        ' llc',
    ):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip(' ,.-')
            break
    return s


def companies_related(a: str | None, b: str | None) -> bool:
    """Treat 'Techberry Infotech' and 'Techberry Infotech Pvt. Ltd.' as the same org."""
    na, nb = normalize_company(a), normalize_company(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na

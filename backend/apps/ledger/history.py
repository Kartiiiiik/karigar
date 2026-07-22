"""Serialise a django-simple-history stream into a readable changelog.

Each entry reports who changed the record, when, the change type
(created / updated / deleted), and the field-level old->new diffs.
"""
_TYPE_LABEL = {"+": "created", "~": "updated", "-": "deleted"}


def _stringify(value):
    return "" if value is None else str(value)


def build_changelog(instance):
    records = list(instance.history.all())  # newest first
    out = []
    for i, record in enumerate(records):
        changes = []
        if record.history_type == "~" and i + 1 < len(records):
            try:
                diff = record.diff_against(records[i + 1])
                changes = [
                    {"field": c.field, "old": _stringify(c.old), "new": _stringify(c.new)}
                    for c in diff.changes
                ]
            except Exception:
                changes = []
        out.append({
            "history_id": record.history_id,
            "type": _TYPE_LABEL.get(record.history_type, record.history_type),
            "date": record.history_date,
            "user": getattr(record.history_user, "username", None),
            "changes": changes,
        })
    return out

# app/routers/codes_sync_mvp.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Tuple, Any
from sqlalchemy.orm import Session
import re

from database import get_db     # existing dependency
from models import Code         # SQLAlchemy model (unique on chapter+section)

router = APIRouter(prefix="/codes/sync", tags=["codes-sync"])

# ---------- helpers ----------
NBSP = "\u00a0"
def norm_space(s: str) -> str:
    """Replace NBSP with space and collapse internal whitespace for comparison only."""
    s = (s or "").replace(NBSP, " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return s.strip()

def norm(s: str) -> str:
    """Normalize a string by trimming and lowercasing."""
    return (s or "").strip().lower()

def normalize_section_for_match(chapter: str, section: str) -> str:
    """
    Normalize for matching ONLY. Storage can keep original formatting.
    - strip spaces and '\xA7' artifacts
    - '-' -> '.'
    - remove chapter prefix like '1.' if present
    - remove leading zeros in dotted parts (01.02 -> 1.2)
    """
    chap = str(chapter).strip()
    s = (section or "").strip()
    s = s.replace("\xA7", "").replace(" ", "").replace("-", ".")
    if s.startswith(f"{chap}."):
        s = s[len(chap)+1:]
    parts = [p.lstrip("0") or "0" for p in s.split(".") if p != ""]
    return ".".join(parts)

def token_jaccard(a: str, b: str) -> float:
    """Calculate Jaccard similarity between token sets of two strings."""
    A, B = set(norm_space(a).lower().split()), set(norm_space(b).lower().split())
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

def is_large_delta(old: str, new: str, threshold: float = 0.65) -> bool:
    """Check if the difference between two strings is considered large based on Jaccard similarity."""
    return token_jaccard(old, new) < threshold

# ---------- schemas ----------
class CodeItem(BaseModel):
    section: str
    name: str
    description: str

class ChapterPayload(BaseModel):
    chapter: str
    source: Optional[str] = None
    version: Optional[str] = None
    items: List[CodeItem]

class DiffRow(BaseModel):
    id: Optional[int] = None
    chapter: str
    section: str
    name: str
    description: str

class UpdateRow(BaseModel):
    id: int
    chapter: str
    section: str
    name: str
    description: str

class ConflictItem(BaseModel):
    id: Optional[int] = None
    reason: str
    message: str
    before: Optional[DiffRow] = None
    after: Optional[DiffRow] = None

class DiffResponse(BaseModel):
    creates: List[DiffRow] = []
    updates: List[Dict[str, Any]] = []  # {id, before, after}
    conflicts: List[ConflictItem] = []
    summary: Dict[str, int]

class ApplyRequest(BaseModel):
    creates: List[DiffRow] = []
    updates: List[UpdateRow] = []

# ---------- core ----------
def index_existing_by_key(rows: List[Code]) -> Dict[Tuple[str, str], Code]:
    """Create a dictionary index of existing codes keyed by normalized (chapter, section)."""
    idx: Dict[Tuple[str, str], Code] = {}
    for r in rows:
        key = (norm(r.chapter), normalize_section_for_match(r.chapter, r.section))
        idx[key] = r
    return idx

@router.post("/diff", response_model=DiffResponse)
def diff(payload: ChapterPayload, db: Session = Depends(get_db)):
    """
    Compare incoming code chapter data against the database to generate a diff (creates, updates, conflicts).

    Args:
        payload (ChapterPayload): Incoming chapter data.
        db (Session): The database session.

    Returns:
        DiffResponse: A breakdown of proposed changes.
    """
    # Load existing for this chapter only (faster) -- adjust if your /codes spans all chapters
    existing_rows: List[Code] = db.query(Code).filter(Code.chapter == payload.chapter).all()
    existing_idx = index_existing_by_key(existing_rows)

    # Detect ambiguous source sections after normalization
    seen_src_keys: Dict[Tuple[str, str], str] = {}
    creates: List[DiffRow] = []
    updates: List[Dict[str, Any]] = []
    conflicts: List[ConflictItem] = []

    for item in payload.items:
        key = (norm(payload.chapter), normalize_section_for_match(payload.chapter, item.section))

        # ambiguous mapping in source?
        if key in seen_src_keys:
            conflicts.append(ConflictItem(
                reason="ambiguous_mapping",
                message=f"Multiple source items map to the same key {(payload.chapter, key[1])}",
                before=None,
                after=DiffRow(id=None, chapter=payload.chapter, section=item.section, name=item.name, description=item.description),
            ))
            continue
        seen_src_keys[key] = item.section

        existing = existing_idx.get(key)
        after_row = DiffRow(id=existing.id if existing else None,
                            chapter=payload.chapter,
                            section=item.section,  # keep UI's original section string
                            name=item.name,
                            description=item.description)

        if not existing:
            creates.append(after_row)
        else:
            # compare on normalized text (spaces only)
            name_changed = norm_space(existing.name) != norm_space(item.name)
            desc_changed = norm_space(existing.description) != norm_space(item.description)

            if name_changed or desc_changed:
                # large-delta conflict?
                if is_large_delta(existing.description or "", item.description or "") or \
                   is_large_delta(existing.name or "", item.name or ""):
                    conflicts.append(ConflictItem(
                        id=existing.id,
                        reason="large_delta",
                        message="Substantial change detected; please review.",
                        before=DiffRow(id=existing.id, chapter=existing.chapter, section=existing.section,
                                       name=existing.name, description=existing.description),
                        after=after_row
                    ))
                else:
                    updates.append({
                        "id": existing.id,
                        "before": DiffRow(id=existing.id, chapter=existing.chapter, section=existing.section,
                                          name=existing.name, description=existing.description),
                        "after": after_row
                    })

    return DiffResponse(
        creates=creates,
        updates=updates,
        conflicts=conflicts,
        summary={"creates": len(creates), "updates": len(updates), "conflicts": len(conflicts)}
    )

@router.post("/apply")
def apply_changes(body: ApplyRequest, db: Session = Depends(get_db)):
    """
    Apply approved changes (creates and updates) to the database.

    Args:
        body (ApplyRequest): List of creates and updates to apply.
        db (Session): The database session.

    Returns:
        dict: Counts of created and updated records.
    """
    created = updated = 0
    # CREATE
    for it in body.creates:
        # guard against duplicates under concurrent runs
        key_norm = normalize_section_for_match(it.chapter, it.section)
        exists = db.query(Code).filter(
            Code.chapter == it.chapter,
            # match on normalized form; but we only have stored raw section; compare both possibilities
            # simplest guard: try exact first
            Code.section == it.section
        ).first()
        if exists:
            continue
        db.add(Code(
            chapter=it.chapter.strip(),
            section=it.section.strip(),
            name=it.name.strip(),
            description=it.description
        ))
        created += 1

    # UPDATE
    for it in body.updates:
        row: Code = db.query(Code).get(it.id)
        if not row:
            continue
        row.chapter = it.chapter.strip()
        row.section = it.section.strip()
        row.name = it.name.strip()
        row.description = it.description
        updated += 1

    db.commit()
    return {"created": created, "updated": updated}

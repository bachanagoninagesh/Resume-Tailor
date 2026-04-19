"""
PDF Resume Renderer — crisp, vivid, professional styling.

Visual design decisions:
  - Name: ALL CAPS, large bold, pure black — commanding and clean
  - Contact: deep charcoal #1A1A1A — readable, not washed out
  - Section headers: deep navy #1F3864 bold + full-width navy rule
  - Body text: pure black — maximum contrast, ATS-friendly
  - Bullets: real • characters, consistent indent
  - Two-col skills: sharp bold category labels
  - Education: compact 2-line strict layout
  - All content indented 4pt inside section rules
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.models import TailoredResume


def _x(s: str) -> str:
    """Escape XML special characters in user text before embedding in Paragraph markup."""
    return _xml_escape(str(s or ""))


# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = letter          # 612 × 792 pt
ML = 0.60 * inch
MR = 0.60 * inch
MT = 0.38 * inch
MB = 0.36 * inch
CW = PAGE_W - ML - MR           # ≈ 518.4 pt

# Content indent — all body text sits 4pt inside the section rule
CI = 4

# ── Colour palette — vivid and sharp ──────────────────────────────────────────
NAVY        = colors.HexColor("#2C68A8")   # classic professional mid-blue — slightly brighter than Word default
BLACK       = colors.HexColor("#0A0A0A")   # near-black for all body text
CONTACT_CLR = colors.HexColor("#1A1A1A")   # dark charcoal for contact line
URL_CLR     = "#2C68A8"                    # blue for URLs/emails in contact (hex str for HTML)
BULLET_CLR  = colors.HexColor("#2C68A8")   # matching blue bullets
RULE_CLR    = colors.HexColor("#2C68A8")   # same as blue

# ── Font-size ladder ───────────────────────────────────────────────────────────
_FONT_SIZES = [10.5, 10.2, 9.9, 9.6, 9.3, 9.0, 8.7, 8.4, 8.1, 7.8, 7.5, 7.2]


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════════════════

def render_resume_pdf(resume: TailoredResume, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    last = b""
    for fs in _FONT_SIZES:
        buf = BytesIO()
        pages = _build(buf, resume, fs)
        last = buf.getvalue()
        if pages <= 1:
            break
    out_path.write_bytes(last)


# ══════════════════════════════════════════════════════════════════════════════
# Core builder
# ══════════════════════════════════════════════════════════════════════════════

def _build(buf: BytesIO, r: TailoredResume, fs: float) -> int:
    S  = _styles(fs)
    st = []

    # ── NAME — ALL CAPS, large, pure black, centered ──────────────────────────
    name = _x((r.contact.name or "Candidate").upper())
    st.append(Paragraph(name, S["name"]))

    # ── Small gap between name and contact ────────────────────────────────────
    st.append(Spacer(1, 0.030 * inch))

    # ── CONTACT LINE — dark charcoal, URLs/emails in blue ────────────────────
    parts = [p for p in [
        r.contact.email, r.contact.phone, r.contact.location,
        r.contact.linkedin, r.contact.portfolio,
    ] if p]
    if parts:
        st.append(Paragraph(_contact_html(parts), S["contact"]))

    # ── HEADER RULE — full width, navy, 1.2pt ─────────────────────────────────
    st.append(Spacer(1, 0.042 * inch))
    st.append(HRFlowable(width="100%", thickness=1.2, color=RULE_CLR,
                          spaceBefore=0, spaceAfter=0))

    # ── PROFESSIONAL SUMMARY ──────────────────────────────────────────────────
    if r.summary:
        st.append(Spacer(1, 0.070 * inch))   # extra gap after header rule
        st.append(Paragraph("PROFESSIONAL SUMMARY", S["section"]))
        st.extend(_sec_rule())
        st.append(Paragraph(_x(r.summary), S["body"]))
        st.append(Spacer(1, 0.014 * inch))

    # ── PROFESSIONAL EXPERIENCE ───────────────────────────────────────────────
    if r.experience:
        st.extend(_sec_gap())
        st.append(Paragraph("PROFESSIONAL EXPERIENCE", S["section"]))
        st.extend(_sec_rule())
        for exp in r.experience:
            st.extend(_render_exp(exp, S))

    # ── TECHNICAL SKILLS ──────────────────────────────────────────────────────
    if r.skills:
        st.extend(_sec_gap())
        st.append(Paragraph("TECHNICAL SKILLS", S["section"]))
        st.extend(_sec_rule())
        st.extend(_render_skills(r.skills, S, fs))
        st.append(Spacer(1, 0.014 * inch))

    # ── CERTIFICATIONS ────────────────────────────────────────────────────────
    if r.certifications:
        st.extend(_sec_gap())
        st.append(Paragraph("CERTIFICATIONS", S["section"]))
        st.extend(_sec_rule())
        st.extend(_render_certs(r.certifications, S))
        st.append(Spacer(1, 0.014 * inch))

    # ── EDUCATION ─────────────────────────────────────────────────────────────
    if r.education:
        st.extend(_sec_gap())
        st.append(Paragraph("EDUCATION", S["section"]))
        st.extend(_sec_rule())
        edu_list = r.education[:2]
        for i, edu in enumerate(edu_list):
            st.extend(_render_edu(edu, S))
            if i < len(edu_list) - 1:
                st.append(Spacer(1, 0.010 * inch))  # gap between degree entries
        st.append(Spacer(1, 0.010 * inch))

    doc = _Doc(
        buf,
        pagesize=letter,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB,
        title=f"{r.contact.name} Resume",
        author=r.contact.name,
    )
    doc.build(st)
    return doc.page_count


# ══════════════════════════════════════════════════════════════════════════════
# Section helpers
# ══════════════════════════════════════════════════════════════════════════════

def _sec_gap() -> list:
    return [Spacer(1, 0.026 * inch)]

def _sec_rule() -> list:
    return [HRFlowable(width="100%", thickness=0.9, color=RULE_CLR,
                       spaceBefore=1, spaceAfter=2)]


# ══════════════════════════════════════════════════════════════════════════════
# Block renderers
# ══════════════════════════════════════════════════════════════════════════════

def _render_exp(exp, S: dict) -> list:
    elems = []

    # Title (bold left) ←→ Dates (italic right)
    elems.append(_lr_table(
        f"<b>{_x(exp.title or '')}</b>",
        f"<i>{_x(exp.dates or '')}</i>",
        S["row_left"], S["row_right"],
        left_frac=0.72,
    ))

    # Company | Location (italic left)
    co_loc = _join([exp.company, exp.location], " | ")
    if co_loc:
        elems.append(Paragraph(f"<i>{_x(co_loc)}</i>", S["company_line"]))

    # Top-level bullets
    for b in exp.bullets:
        t = b.strip().lstrip("-•").strip()
        if t:
            elems.append(Paragraph(f"\u2022  {_x(t)}", S["bullet"]))

    # Project subheadings + bullets
    for sec in exp.sections:
        if sec.name:
            elems.append(Paragraph(_x(sec.name), S["subhead"]))
        for b in sec.bullets:
            t = b.strip().lstrip("-•").strip()
            if t:
                elems.append(Paragraph(f"\u2022  {_x(t)}", S["bullet"]))

    elems.append(Spacer(1, 0.016 * inch))
    return elems


def _render_skills(skills: list, S: dict, fs: float) -> list:
    parsed: list[tuple[str, str]] = []
    for s in skills:
        t = s.strip()
        if not t:
            continue
        if ":" in t:
            cat, vals = t.split(":", 1)
            parsed.append((cat.strip(), vals.strip()))
        else:
            parsed.append(("", t))
    if not parsed:
        return []

    base = getSampleStyleSheet()["Normal"]
    cs = ParagraphStyle(
        "sk", parent=base,
        fontName="Helvetica", fontSize=fs,
        leading=fs * 1.32, textColor=BLACK,
        spaceBefore=0, spaceAfter=0,
    )

    col_w = (CW - CI) / 2
    rows = []
    for i in range(0, len(parsed), 2):
        lc, lv = parsed[i]
        rc, rv = parsed[i+1] if i+1 < len(parsed) else ("", "")

        def _p(cat, val, _cs=cs):
            if cat:
                return Paragraph(f"<b>{_x(cat)}:</b> {_x(val)}", _cs)
            return Paragraph(_x(val), _cs)

        inner = Table([[_p(lc, lv), _p(rc, rv)]], colWidths=[col_w, col_w])
        inner.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("TOPPADDING",    (0,0), (-1,-1), 1),
            ("BOTTOMPADDING", (0,0), (-1,-1), 1),
        ]))
        outer = Table([[inner]], colWidths=[CW - CI])
        outer.setStyle(TableStyle([
            ("LEFTPADDING",   (0,0), (-1,-1), CI),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        rows.append(outer)
    return rows


def _render_certs(certs: list, S: dict) -> list:
    """All certs in one flowing paragraph — no isolated stragglers."""
    clean = [c.strip() for c in certs if c.strip()]
    if not clean:
        return []
    return [Paragraph("  \u2022  ".join(_x(c) for c in clean), S["body"])]


def _render_edu(edu, S: dict) -> list:
    """3-line layout per degree: title row / detail row / coursework row."""
    # Line 1: Degree | School  ←→  Dates
    elems = [_lr_table(
        f"<b>{_x(_join([edu.degree, edu.school], ' | '))}</b>",
        f"<i>{_x(edu.dates)}</i>",
        S["edu_left"], S["edu_right"],
        left_frac=0.65,
    )]
    # Line 2: Location  |  GPA / details (italic)
    detail_line = _join([edu.location, edu.details], "  |  ")
    if detail_line:
        elems.append(Paragraph(f"<i>{_x(detail_line)}</i>", S["edu_detail"]))
    # Line 3: Relevant Coursework
    cw = (edu.coursework or "").strip()
    if cw:
        elems.append(Paragraph(f"<i>Relevant Coursework: {_x(cw)}</i>", S["coursework"]))
    elems.append(Spacer(1, 0.008 * inch))
    return elems


# ══════════════════════════════════════════════════════════════════════════════
# Table helper — all content indented CI pts inside section rule
# ══════════════════════════════════════════════════════════════════════════════

def _lr_table(
    left_html: str, right_html: str,
    left_style: ParagraphStyle, right_style: ParagraphStyle,
    left_frac: float = 0.74,
) -> Table:
    inner_w = CW - CI
    lw = inner_w * left_frac
    rw = inner_w * (1 - left_frac)

    inner = Table(
        [[Paragraph(left_html, left_style), Paragraph(right_html, right_style)]],
        colWidths=[lw, rw],
    )
    inner.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "BOTTOM"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    outer = Table([[inner]], colWidths=[CW - CI])
    outer.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0), (-1,-1), CI),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    return outer


def _join(parts: list, sep: str) -> str:
    return sep.join(p for p in parts if p)


def _contact_html(parts: list[str]) -> str:
    """Join contact parts; wrap URLs and emails in blue."""
    rendered = []
    for p in parts:
        if p.startswith(("http://", "https://", "www.")) or "@" in p:
            rendered.append(f'<font color="{URL_CLR}">{_x(p)}</font>')
        else:
            rendered.append(_x(p))
    return " | ".join(rendered)


# ══════════════════════════════════════════════════════════════════════════════
# Style sheet — vivid, sharp, professional
# ══════════════════════════════════════════════════════════════════════════════

def _styles(fs: float) -> dict:
    base = getSampleStyleSheet()["Normal"]
    BI = CI + 9   # bullet left indent
    BH = 7        # bullet hanging

    return {
        # ── Header name — ALL CAPS, large, same blue as section headers ────────
        "name": ParagraphStyle(
            "name", parent=base,
            fontName="Helvetica-Bold",
            fontSize=fs + 6.8,
            leading=(fs + 6.8) * 1.15,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceAfter=0,
        ),
        # ── Contact line — dark charcoal, not gray ───────────────────────────
        "contact": ParagraphStyle(
            "contact", parent=base,
            fontName="Helvetica",
            fontSize=fs - 0.4,
            leading=(fs - 0.4) * 1.28,
            alignment=TA_CENTER,
            textColor=CONTACT_CLR,
            spaceAfter=0,
        ),
        # ── Section heading — deep navy bold ─────────────────────────────────
        "section": ParagraphStyle(
            "section", parent=base,
            fontName="Helvetica-Bold",
            fontSize=fs + 0.5,
            leading=(fs + 0.5) * 1.18,
            alignment=TA_LEFT,
            textColor=NAVY,
            spaceBefore=0, spaceAfter=0,
        ),
        # ── Body / summary — pure black, max contrast ────────────────────────
        "body": ParagraphStyle(
            "body", parent=base,
            fontName="Helvetica",
            fontSize=fs,
            leading=fs * 1.44,
            alignment=TA_LEFT,
            textColor=BLACK,
            leftIndent=CI,
            spaceAfter=0,
        ),
        # ── Two-col row: left (bold role/degree) ─────────────────────────────
        "row_left": ParagraphStyle(
            "row_left", parent=base,
            fontName="Helvetica-Bold",
            fontSize=fs,
            leading=fs * 1.35,
            alignment=TA_LEFT,
            textColor=BLACK,
            spaceAfter=0,
        ),
        # ── Two-col row: right (italic dates) ────────────────────────────────
        "row_right": ParagraphStyle(
            "row_right", parent=base,
            fontName="Helvetica-Oblique",
            fontSize=fs - 0.2,
            leading=(fs - 0.2) * 1.35,
            alignment=TA_RIGHT,
            textColor=BLACK,
            spaceAfter=0,
        ),
        # ── Company / location italic line ───────────────────────────────────
        "company_line": ParagraphStyle(
            "company_line", parent=base,
            fontName="Helvetica-Oblique",
            fontSize=fs - 0.1,
            leading=(fs - 0.1) * 1.38,
            alignment=TA_LEFT,
            textColor=BLACK,
            leftIndent=CI,
            spaceAfter=1,
        ),
        # ── Project subheading — bold, navy tint ─────────────────────────────
        "subhead": ParagraphStyle(
            "subhead", parent=base,
            fontName="Helvetica-Bold",
            fontSize=fs,
            leading=fs * 1.36,
            alignment=TA_LEFT,
            textColor=BLACK,
            leftIndent=CI,
            spaceBefore=2, spaceAfter=0,
        ),
        # ── Bullet with hanging indent ────────────────────────────────────────
        "bullet": ParagraphStyle(
            "bullet", parent=base,
            fontName="Helvetica",
            fontSize=fs,
            leading=fs * 1.42,
            leftIndent=BI,
            firstLineIndent=-BH,
            alignment=TA_LEFT,
            textColor=BLACK,
            spaceAfter=1.5,
        ),
        # ── Activity bullet (no hanging) ──────────────────────────────────────
        "bullet_plain": ParagraphStyle(
            "bullet_plain", parent=base,
            fontName="Helvetica",
            fontSize=fs,
            leading=fs * 1.42,
            leftIndent=CI,
            firstLineIndent=0,
            alignment=TA_LEFT,
            textColor=BLACK,
            spaceAfter=1.5,
        ),
        # ── Coursework line — small italic under degree ───────────────────────
        "coursework": ParagraphStyle(
            "coursework", parent=base,
            fontName="Helvetica-Oblique",
            fontSize=fs - 0.6,
            leading=(fs - 0.6) * 1.22,
            alignment=TA_LEFT,
            textColor=BLACK,
            leftIndent=CI,
            spaceAfter=1,
        ),
        # ── Education detail line (location | GPA) ────────────────────────────
        "edu_detail": ParagraphStyle(
            "edu_detail", parent=base,
            fontName="Helvetica-Oblique",
            fontSize=fs - 0.4,
            leading=(fs - 0.4) * 1.20,
            alignment=TA_LEFT,
            textColor=BLACK,
            leftIndent=CI,
            spaceAfter=1,
        ),
        # ── Education compact styles — prevents 3rd line ──────────────────────
        "edu_left": ParagraphStyle(
            "edu_left", parent=base,
            fontName="Helvetica-Bold",
            fontSize=fs - 0.25,
            leading=(fs - 0.25) * 1.14,
            alignment=TA_LEFT,
            textColor=BLACK,
            spaceAfter=0,
        ),
        "edu_right": ParagraphStyle(
            "edu_right", parent=base,
            fontName="Helvetica-Oblique",
            fontSize=fs - 0.45,
            leading=(fs - 0.45) * 1.14,
            alignment=TA_RIGHT,
            textColor=BLACK,
            spaceAfter=0,
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Page-count tracking
# ══════════════════════════════════════════════════════════════════════════════

class _Doc(SimpleDocTemplate):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.page_count = 0

    def afterPage(self):
        self.page_count += 1

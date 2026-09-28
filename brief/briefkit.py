"""briefkit: the building blocks of the UPSC Desk daily brief (v2 design), for any desk.

Every block takes the desk's theme, so the same kit draws the Sociology Desk in Steel and
Amber and the Essay Desk in Claret and Gold. brief_build.py turns a content file into a
brief with these blocks; nothing here holds any day's content.

Fonts: Arial and Georgia TrueType files are used when they are on the machine (macOS, or
Linux with the Microsoft core fonts; Liberation Sans stands in for Arial, being the same
size). Otherwise the brief falls back to ReportLab's built-in Helvetica and Times, which
need no files. Set BRIEF_FONTS=builtin to force the fallback.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageTemplate, Paragraph, Table, TableStyle

# ------------------------------------------------------------------ fonts
_SANS_SETS = [   # (regular, bold, italic, bold italic), each tried as a whole family
    ("/System/Library/Fonts/Supplemental/", ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf")),
    ("/Library/Fonts/", ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf")),
    ("/usr/share/fonts/truetype/msttcorefonts/", ("Arial.ttf", "Arial_Bold.ttf", "Arial_Italic.ttf", "Arial_Bold_Italic.ttf")),
    ("/usr/share/fonts/truetype/msttcorefonts/", ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")),
    ("C:/Windows/Fonts/", ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")),
    ("/usr/share/fonts/truetype/liberation/", ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf")),
    ("/usr/share/fonts/truetype/liberation2/", ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf")),
    ("/usr/share/fonts/liberation-sans/", ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf")),
]
_SERIF_SETS = [  # (italic, bold italic): Georgia is used only in italic
    ("/System/Library/Fonts/Supplemental/", ("Georgia Italic.ttf", "Georgia Bold Italic.ttf")),
    ("/Library/Fonts/", ("Georgia Italic.ttf", "Georgia Bold Italic.ttf")),
    ("/usr/share/fonts/truetype/msttcorefonts/", ("Georgia_Italic.ttf", "Georgia_Bold_Italic.ttf")),
    ("/usr/share/fonts/truetype/msttcorefonts/", ("georgiai.ttf", "georgiaz.ttf")),
    ("C:/Windows/Fonts/", ("georgiai.ttf", "georgiaz.ttf")),
]


def _load_fonts():
    f = dict(sans="Helvetica", sansB="Helvetica-Bold", sansI="Helvetica-Oblique", sansBI="Helvetica-BoldOblique",
             serifI="Times-Italic", serifBI="Times-BoldItalic", sans_src="built-in Helvetica", serif_src="built-in Times")
    if os.environ.get("BRIEF_FONTS", "").lower() == "builtin":
        return f
    for d, files in _SANS_SETS:
        paths = [os.path.join(d, x) for x in files]
        if all(os.path.isfile(p) for p in paths):
            try:
                names = ("BriefSans", "BriefSans-Bold", "BriefSans-Italic", "BriefSans-BoldItalic")
                for n, p in zip(names, paths):
                    pdfmetrics.registerFont(TTFont(n, p))
                registerFontFamily("BriefSans", normal=names[0], bold=names[1], italic=names[2], boldItalic=names[3])
                f.update(sans=names[0], sansB=names[1], sansI=names[2], sansBI=names[3], sans_src=paths[0])
                break
            except Exception:
                continue
    for d, files in _SERIF_SETS:
        paths = [os.path.join(d, x) for x in files]
        if all(os.path.isfile(p) for p in paths):
            try:
                pdfmetrics.registerFont(TTFont("BriefSerif-Italic", paths[0]))
                pdfmetrics.registerFont(TTFont("BriefSerif-BoldItalic", paths[1]))
                f.update(serifI="BriefSerif-Italic", serifBI="BriefSerif-BoldItalic", serif_src=paths[0])
                break
            except Exception:
                continue
    return f


F = _load_fonts()


def can_draw(text, font):
    """the characters of text that font cannot draw (built-in fonts cover Windows-1252 only)"""
    bad = []
    fo = pdfmetrics.getFont(font)
    face = getattr(fo, "face", None)
    cmap = getattr(face, "charToGlyph", None) if face is not None else None
    for ch in set(text):
        if ch in "\n\t":
            continue
        if isinstance(cmap, dict) and cmap:
            if ord(ch) not in cmap:
                bad.append(ch)
        else:
            try:
                ch.encode("cp1252")
            except UnicodeEncodeError:
                bad.append(ch)
    return sorted(bad)


# ------------------------------------------------------------------ page geometry and themes
W, H = A4
M = 18 * mm
CW = W - 2 * M          # content width

C = colors.HexColor
THEMES = {
    "sociology": dict(primary=C("#1E3A5F"), deep=C("#142038"), strip=C("#0C1A2E"), accent=C("#F59E0B"), accentDeep=C("#B26E00"),
                      tint=C("#DCE8F5"), support=C("#B8CCE0"), motif=C("#3C587F"), pale=C("#FDF3DF"), paler=C("#FEF9EE"),
                      soft=C("#EEF3FA"), ink=C("#1A1D22"), muted=C("#5B6270"), name="THE SOCIOLOGY DESK",
                      tag="Current Affairs through a Sociological Lens", short="The Sociology Desk", hl="#FFE3A3"),
    "essay": dict(primary=C("#7A2D3A"), deep=C("#461A22"), strip=C("#32121A"), accent=C("#B8860B"), accentDeep=C("#8A6300"),
                  tint=C("#F6EFE3"), support=C("#D6B4BC"), motif=C("#78464E"), pale=C("#F6EFDF"), paler=C("#FBF7EE"),
                  soft=C("#F7EEEE"), ink=C("#1A1D22"), muted=C("#5B6270"), name="THE ESSAY DESK",
                  tag="UPSC Essay, decoded", short="The Essay Desk", hl="#F3DE9E"),
}
RED = "#B8322A"
# the margin-note headings, each in its own colour; the notes sit in one uniform pale box
NOTE_COLOURS = {"WHY IT SCORES": "#2F6B3A", "ADD": "#1E3A5F", "AVOID": "#B8322A", "EXAMPLE": "#8A6300", "CURRENT AFFAIRS": "#5E4A73"}


def hexc(c):
    return "#%02X%02X%02X" % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))


def styles(th):
    ink = th["ink"]
    base = ParagraphStyle("body", fontName=F["sans"], fontSize=10.6, leading=15.2, textColor=ink, alignment=TA_JUSTIFY)
    return {
        "body": base,
        "bodyL": ParagraphStyle("bodyL", parent=base, alignment=TA_LEFT),
        "small": ParagraphStyle("small", parent=base, fontSize=9.2, leading=12.6, alignment=TA_LEFT),
        "label": ParagraphStyle("label", fontName=F["sansB"], fontSize=8.4, leading=11, textColor=th["muted"]),
        "labelA": ParagraphStyle("labelA", fontName=F["sansB"], fontSize=8.4, leading=11, textColor=th["accentDeep"]),
        "h3": ParagraphStyle("h3", fontName=F["sansB"], fontSize=10.8, leading=14, textColor=th["primary"]),
        "q": ParagraphStyle("q", fontName=F["sansB"], fontSize=11.4, leading=15.6, textColor=ink),
        "topic": ParagraphStyle("topic", fontName=F["serifBI"], fontSize=15, leading=20, textColor=th["primary"]),
        "note": ParagraphStyle("note", fontName=F["sans"], fontSize=8.2, leading=10.8, textColor=ink),
        "apart": ParagraphStyle("apart", parent=base, alignment=TA_LEFT, textColor=th["accentDeep"]),
        "lifted": ParagraphStyle("lifted", parent=base, alignment=TA_LEFT, fontName=F["sansI"]),
        "count": ParagraphStyle("count", fontName=F["sansB"], fontSize=9.5, textColor=th["accentDeep"]),
        "motive": ParagraphStyle("motive", fontName=F["serifI"], fontSize=11.5, leading=16, textColor=colors.white, alignment=TA_CENTER),
    }


# ------------------------------------------------------------------ page furniture
def make_doc(path, th, issue, date):
    """page 1 carries the masthead; every later page the running header; all pages the licence line"""
    doc = BaseDocTemplate(path, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=20 * mm, bottomMargin=18 * mm,
                          title=f"{th['short']}, Issue #{issue}", author=th["short"])
    frame = Frame(M, 18 * mm, CW, H - 38 * mm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    first = Frame(M, 18 * mm, CW, H - 18 * mm - 62 * mm, id="f1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    licence = "Compiled by " + th["short"] + "  |  A UPSC Desk product  |  Distributed under licence"

    def header(c, d):
        c.saveState()
        c.setFont(F["sans"], 7.8); c.setFillColor(th["primary"])
        c.drawString(M, H - 12 * mm, f"{th['short']}  ·  Issue #{issue}  ·  {date}")
        c.drawRightString(W - M, H - 12 * mm, str(d.page))
        c.setStrokeColor(th["primary"]); c.setLineWidth(0.6); c.line(M, H - 13.8 * mm, W - M, H - 13.8 * mm)
        c.setFillColor(th["muted"]); c.setFont(F["sans"], 7)
        c.drawCentredString(W / 2, 9 * mm, licence)
        c.restoreState()

    def cover(c, d):
        c.saveState()
        c.setFillColor(th["primary"]); c.rect(0, H - 52 * mm, W, 52 * mm, stroke=0, fill=1)
        c.setFillColor(th["accent"]); c.rect(0, H - 53.2 * mm, W, 1.2 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont(F["sansB"], 26); c.drawString(M, H - 24 * mm, th["name"])
        c.setFillColor(th["accent"]); c.setFont(F["sansB"], 9.5); c.drawString(M, H - 31 * mm, th["tag"].upper())
        c.setFont(F["sansB"], 10); c.drawRightString(W - M, H - 24 * mm, f"Issue #{issue}  |  {date}")
        c.setFillColor(th["motif"])                     # the brand's dot grid
        for i in range(5):
            for j in range(5):
                c.circle(W - M - 4 - i * 4.2 * mm, H - 36 * mm - j * 2.6 * mm, 0.55 * mm, stroke=0, fill=1)
        c.setFillColor(th["strip"]); c.rect(0, H - 62 * mm, W, 8.8 * mm, stroke=0, fill=1)
        c.setFillColor(th["support"]); c.setFont(F["sansI"], 9)
        c.drawCentredString(W / 2, H - 58.6 * mm, "Empirically grounded. Theoretically anchored. Exam-ready.")
        c.setFillColor(th["muted"]); c.setFont(F["sans"], 7)
        c.drawCentredString(W / 2, 9 * mm, licence)
        c.restoreState()

    doc.addPageTemplates([PageTemplate(id="cover", frames=[first], onPage=cover), PageTemplate(id="page", frames=[frame], onPage=header)])
    return doc


# ------------------------------------------------------------------ blocks
def band(text, th, sub=None):
    s = ParagraphStyle("b", fontName=F["sansB"], fontSize=11.5, leading=14, textColor=colors.white)
    cell = [Paragraph(text, s)]
    if sub:
        cell.append(Paragraph(sub, ParagraphStyle("bs", fontName=F["sans"], fontSize=8.5, leading=11, textColor=th["tint"])))
    t = Table([[cell]], colWidths=[CW])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), th["primary"]), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LINEBELOW", (0, 0), (-1, -1), 1.5, th["accent"])]))
    return t


def box(flows, th, fill=None, rule=None, border=None, pad=8, width=None):
    t = Table([[flows]], colWidths=[width or CW])
    st = [("BACKGROUND", (0, 0), (-1, -1), fill or th["paler"]), ("LEFTPADDING", (0, 0), (-1, -1), pad + (3 if rule else 0)),
          ("RIGHTPADDING", (0, 0), (-1, -1), pad), ("TOPPADDING", (0, 0), (-1, -1), pad - 1), ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]
    if rule:
        st.append(("LINEBEFORE", (0, 0), (0, -1), 3.2, rule))
    if border:
        st.append(("BOX", (0, 0), (-1, -1), 0.8, border))
    t.setStyle(TableStyle(st))
    return t


def pills_width(texts, size=7.4):
    return sum(pdfmetrics.stringWidth(t, F["sansB"], size) + 5 * mm for t in texts) + 2 * mm * (len(texts) - 1)


class Pills(Flowable):
    """a row of rounded tags: [(text, fill, textcolour)]"""
    def __init__(self, items, h=5.4 * mm, size=7.4):
        super().__init__(); self.items, self.h, self.size = items, h, size
    def wrap(self, aw, ah): return aw, self.h + 1
    def draw(self):
        x = 0
        for text, fill, fg in self.items:
            w = pdfmetrics.stringWidth(text, F["sansB"], self.size) + 5 * mm
            self.canv.setFillColor(fill); self.canv.roundRect(x, 0, w, self.h, self.h / 2, stroke=0, fill=1)
            self.canv.setFillColor(fg); self.canv.setFont(F["sansB"], self.size)
            self.canv.drawCentredString(x + w / 2, self.h / 2 - self.size * 0.36, text)
            x += w + 2 * mm


METER_DOTS_X, METER_NOTE_X = 46 * mm, 70 * mm


def meter_fit(reason, width):
    """True when a meter's one line of reason fits beside its dots in a row this wide"""
    return pdfmetrics.stringWidth(reason, F["sans"], 7.6) <= width - METER_NOTE_X


class Meter(Flowable):
    """element 28: a label, five dots with n filled, and one line of reason"""
    def __init__(self, th, label, n, note=""):
        super().__init__(); self.th, self.label, self.n, self.note = th, label, n, note
    def wrap(self, aw, ah): self.aw = aw; return aw, 5.5 * mm
    def draw(self):
        c, th = self.canv, self.th
        c.setFillColor(th["ink"]); c.setFont(F["sansB"], 8.2); c.drawString(0, 1.5 * mm, self.label)
        for i in range(5):
            c.setFillColor(th["accent"] if i < self.n else th["tint"]); c.circle(METER_DOTS_X + i * 4.4 * mm, 2.6 * mm, 1.6 * mm, stroke=0, fill=1)
        c.setFillColor(th["muted"]); c.setFont(F["sans"], 7.6); c.drawString(METER_NOTE_X, 1.5 * mm, self.note)


def wrap_text(text, font, size, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= width: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


# how much text each drawn box holds before it would be cut off (checked by brief_build.py)
PIPE_TITLE_LINES, PIPE_SUB_LINES = 2, 4
HUB_SPOKE_SUB_LINES, HUB_LINES = 2, 2
HUB_BOX_W, HUB_W = 38 * mm, 50 * mm


def pipeline_fit(nodes, width):
    """[(node index, what is cut off)] for a Pipeline of this width"""
    n = len(nodes); bw = (width - (n - 1) * 9 * mm) / n; out = []
    for i, (label, title, sub) in enumerate(nodes):
        if len(wrap_text(title, F["sansB"], 9.6, bw - 6 * mm)) > PIPE_TITLE_LINES: out.append((i, "title", PIPE_TITLE_LINES))
        if len(wrap_text(sub, F["sans"], 7.2, bw - 6 * mm)) > PIPE_SUB_LINES: out.append((i, "text", PIPE_SUB_LINES))
        if pdfmetrics.stringWidth(label, F["sansB"], 6.8) > bw - 6 * mm: out.append((i, "label", 1))
    return out


class Pipeline(Flowable):
    """boxes joined by arrows, left to right: [(label, title, sub)]; the last box is filled"""
    def __init__(self, th, nodes, width=CW, h=26 * mm, fill_last=True, gap=9 * mm):
        super().__init__(); self.th, self.nodes, self.w, self.h, self.fill_last, self.gap = th, nodes, width, h, fill_last, gap
    def wrap(self, aw, ah): return self.w, self.h
    def draw(self):
        c, th, n = self.canv, self.th, len(self.nodes)
        bw = (self.w - (n - 1) * self.gap) / n
        for i, (label, title, sub) in enumerate(self.nodes):
            x = i * (bw + self.gap)
            last = self.fill_last and i == n - 1
            c.setFillColor(th["accent"] if last else th["soft"]); c.setStrokeColor(th["primary"]); c.setLineWidth(0.8)
            c.roundRect(x, 0, bw, self.h, 2.2 * mm, stroke=0 if last else 1, fill=1)
            c.setFillColor(th["deep"] if last else th["accentDeep"]); c.setFont(F["sansB"], 6.8)
            c.drawString(x + 3 * mm, self.h - 5 * mm, label)
            c.setFillColor(th["deep"] if last else th["primary"]); c.setFont(F["sansB"], 9.6)
            y = self.h - 10 * mm
            for ln in wrap_text(title, F["sansB"], 9.6, bw - 6 * mm)[:PIPE_TITLE_LINES]:
                c.drawString(x + 3 * mm, y, ln); y -= 4.2 * mm
            c.setFillColor(th["ink"]); c.setFont(F["sans"], 7.2)
            for ln in wrap_text(sub, F["sans"], 7.2, bw - 6 * mm)[:PIPE_SUB_LINES]:
                c.drawString(x + 3 * mm, y, ln); y -= 3.2 * mm
            if i < n - 1:                                      # the arrow into the next box
                ax, ay = x + bw + 1.2 * mm, self.h / 2
                c.setStrokeColor(th["accent"]); c.setLineWidth(1.8); c.line(ax, ay, ax + self.gap - 4.2 * mm, ay)
                c.setFillColor(th["accent"]); p = c.beginPath()
                p.moveTo(ax + self.gap - 2.4 * mm, ay); p.lineTo(ax + self.gap - 5 * mm, ay + 1.7 * mm); p.lineTo(ax + self.gap - 5 * mm, ay - 1.7 * mm); p.close()
                c.drawPath(p, stroke=0, fill=1)


def hub_fit(hub, spokes):
    """what would be cut off in a HubSpoke: [(where, detail)]"""
    out = []
    if len(wrap_text(hub, F["sansB"], 9.4, 46 * mm)) > HUB_LINES: out.append(("hub", HUB_LINES))
    for i, (t, s) in enumerate(spokes):
        if pdfmetrics.stringWidth(t, F["sansB"], 8.6) > HUB_BOX_W - 3 * mm: out.append((f"lens {i + 1} title", 1))
        if len(wrap_text(s, F["sans"], 6.6, HUB_BOX_W - 4 * mm)) > HUB_SPOKE_SUB_LINES: out.append((f"lens {i + 1} text", HUB_SPOKE_SUB_LINES))
    return out


class HubSpoke(Flowable):
    """a hub in the middle and spokes to the lenses around it, clockwise from the top, arrows pointing out"""
    def __init__(self, th, hub, spokes, width=CW, h=78 * mm):
        super().__init__(); self.th, self.hub, self.spokes, self.w, self.h = th, hub, spokes, width, h
    def wrap(self, aw, ah): return self.w, self.h
    def draw(self):
        import math
        c, th = self.canv, self.th
        cx, cy = self.w / 2, self.h / 2
        n = len(self.spokes); rx, ry = self.w * 0.36, self.h * 0.36
        bw, bh = HUB_BOX_W, 12.5 * mm
        for i, (t, s) in enumerate(self.spokes):
            a = math.pi / 2 - i * 2 * math.pi / n
            x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
            dx, dy = x - cx, y - cy; L = math.hypot(dx, dy) or 1; ux, uy = dx / L, dy / L
            th_hub = min(25 * mm / max(abs(ux), 1e-6), 8 * mm / max(abs(uy), 1e-6))
            th_box = min((bw / 2) / max(abs(ux), 1e-6), (bh / 2) / max(abs(uy), 1e-6))
            sx, sy = cx + ux * (th_hub + 0.8 * mm), cy + uy * (th_hub + 0.8 * mm)
            ex, ey = x - ux * (th_box + 0.8 * mm), y - uy * (th_box + 0.8 * mm)
            c.setStrokeColor(th["accent"]); c.setLineWidth(1.4); c.line(sx, sy, ex, ey)
            ang = math.atan2(ey - sy, ex - sx); c.setFillColor(th["accent"]); p = c.beginPath()
            p.moveTo(ex, ey); p.lineTo(ex - 2.6 * mm * math.cos(ang - 0.4), ey - 2.6 * mm * math.sin(ang - 0.4))
            p.lineTo(ex - 2.6 * mm * math.cos(ang + 0.4), ey - 2.6 * mm * math.sin(ang + 0.4)); p.close(); c.drawPath(p, stroke=0, fill=1)
            c.setFillColor(th["soft"]); c.setStrokeColor(th["primary"]); c.setLineWidth(0.7)
            c.roundRect(x - bw / 2, y - bh / 2, bw, bh, 2 * mm, stroke=1, fill=1)
            c.setFillColor(th["primary"]); c.setFont(F["sansB"], 8.6); c.drawCentredString(x, y + 1.2 * mm, t)
            c.setFillColor(th["ink"]); c.setFont(F["sans"], 6.6)
            for k, ln in enumerate(wrap_text(s, F["sans"], 6.6, bw - 4 * mm)[:HUB_SPOKE_SUB_LINES]):
                c.drawCentredString(x, y - 2.6 * mm - k * 2.8 * mm, ln)
        c.setFillColor(th["primary"]); c.roundRect(cx - 25 * mm, cy - 8 * mm, HUB_W, 16 * mm, 3 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont(F["sansB"], 9.4)
        for k, ln in enumerate(wrap_text(self.hub, F["sansB"], 9.4, 46 * mm)[:HUB_LINES]):
            c.drawCentredString(cx, cy + 1.2 * mm - k * 4 * mm, ln)


def grid(data, widths, th, head=True, zebra=True, size=8.8):
    st = ParagraphStyle("g", fontName=F["sans"], fontSize=size, leading=size * 1.35, textColor=th["ink"])
    sh = ParagraphStyle("gh", fontName=F["sansB"], fontSize=size - 0.4, leading=size * 1.3, textColor=colors.white)
    rows = [[Paragraph(x, sh if (head and i == 0) else st) for x in r] for i, r in enumerate(data)]
    t = Table(rows, colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, th["support"]),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if head:
        style.append(("BACKGROUND", (0, 0), (-1, 0), th["primary"]))
    if zebra:
        for i in range(1 if head else 0, len(data)):
            if i % 2 == 0: style.append(("BACKGROUND", (0, i), (-1, i), th["soft"]))
    t.setStyle(TableStyle(style))
    return t


def mark(phrase, n, th):
    """a highlighted phrase with its note number (a small red superscript), as the answer shows it"""
    return f"<span backColor='{th['hl']}'>{phrase}</span><super><font color='{RED}' size='7'><b>{n}</b></font></super>"


MARGIN_LEFT = 0.70          # the answer's share of the width; the notes take the rest
BODY_PAD_R, NOTE_PAD_L, NOTE_PAD_R, NOTE_GAP = 10, 6, 5, 3


def note_html(n, tag, text):
    col = NOTE_COLOURS.get(tag, "#8A6300")
    return f"<font color='{RED}'><b>{n}</b></font>  <font color='{col}'><b>{tag}.</b></font> {text}"


def column_heights(body_html, notes, th, st):
    """(paragraph height, note column height) in points, as numbered_margin lays them out"""
    lw, rw = CW * MARGIN_LEFT, CW * (1 - MARGIN_LEFT)
    bh = Paragraph(body_html, st["body"]).wrap(lw - BODY_PAD_R, 1e6)[1]
    nh = 0
    for n, tag, text in notes:
        nh += Paragraph(note_html(n, tag, text), st["note"]).wrap(rw - NOTE_PAD_L - NOTE_PAD_R, 1e6)[1] + NOTE_GAP
    return bh, nh


def numbered_margin(rows, th, st):
    """[(paragraph html with mark() inside, [(n, TAG, note)])]: the answer on the left; beside
    each paragraph, in one uniform pale box, its numbered notes with a coloured heading"""
    from reportlab.platypus import Spacer
    lw, rw = CW * MARGIN_LEFT, CW * (1 - MARGIN_LEFT)
    data, style = [], [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), BODY_PAD_R),
                       ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
    for i, (body, notes) in enumerate(rows):
        cell = []
        for n, tag, text in notes:
            cell.append(Paragraph(note_html(n, tag, text), st["note"]))
            cell.append(Spacer(1, NOTE_GAP))
        data.append([Paragraph(body, st["body"]), cell or ""])
        if notes:
            style += [("BACKGROUND", (1, i), (1, i), th["pale"]), ("LINEBEFORE", (1, i), (1, i), 2.4, th["accent"]),
                      ("LEFTPADDING", (1, i), (1, i), NOTE_PAD_L), ("RIGHTPADDING", (1, i), (1, i), NOTE_PAD_R)]
    t = Table(data, colWidths=[lw, rw])
    t.setStyle(TableStyle(style))
    return t

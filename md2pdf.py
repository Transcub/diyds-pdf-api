"""
DoItYaDamnSelf.com — Markdown to PDF Converter
Usage: python3 md2pdf.py "path/to/guide.md" [output.pdf]
Or import and call: convert_md_to_pdf(markdown_text, title, output_path)
"""

import re
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Flowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus.flowables import HRFlowable

FONT = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
FONT_ITALIC = 'Helvetica-Oblique'
FONT_BOLDITALIC = 'Helvetica-BoldOblique'

# ── COLORS ──
LIME    = colors.HexColor('#c5e835')
BLACK   = colors.HexColor('#111111')
DARK    = colors.HexColor('#1a1a1a')
DARK2   = colors.HexColor('#2e2e2e')
WHITE   = colors.white
MUTED   = colors.HexColor('#666666')
BLUE    = colors.HexColor('#0066CC')
GOLD    = colors.HexColor('#8a6800')
GRAY    = colors.HexColor('#888888')
TIP_BG  = colors.HexColor('#f0f8e8')
TIP_BD  = colors.HexColor('#2a8a2a')
WARN_BG = colors.HexColor('#fff8e0')
WARN_BD = colors.HexColor('#e0a000')
NOTE_BG = colors.HexColor('#f8f8f0')
ROW_ALT = colors.HexColor('#fafaf8')

W, H = letter
MARGIN = 0.75 * inch
CONTENT_W = W - 2 * MARGIN

# ── CALLOUT BOX FLOWABLE ──
class CalloutBox(Flowable):
    def __init__(self, text, style='tip'):
        super().__init__()
        self.raw = text
        self.style = style
        self.pad = 10

    def wrap(self, avail_w, avail_h):
        self.avail_w = avail_w
        if self.style == 'tip':
            self.bg, self.bd = TIP_BG, TIP_BD
            self.label = '✓  PRO TIP'
            self.lc = colors.HexColor('#1a6a1a')
        elif self.style == 'warn':
            self.bg, self.bd = WARN_BG, WARN_BD
            self.label = '⚠  WARNING'
            self.lc = colors.HexColor('#8a4a00')
        else:
            self.bg, self.bd = NOTE_BG, LIME
            self.label = '📋  NOTE'
            self.lc = MUTED

        # Estimate height
        style = ParagraphStyle('ct', fontName=FONT, fontSize=10, leading=14)
        p = Paragraph(self.raw, style)
        _, ph = p.wrap(avail_w - 28, 999)
        self.bh = ph + self.pad * 3 + 14
        return avail_w, self.bh

    def draw(self):
        c = self.canv
        w = self.avail_w
        # Background
        c.setFillColor(self.bg)
        c.roundRect(0, 0, w, self.bh, 5, fill=1, stroke=0)
        # Left bar
        c.setFillColor(self.bd)
        c.rect(0, 0, 4, self.bh, fill=1, stroke=0)
        # Label
        c.setFont(FONT_BOLD, 8)
        c.setFillColor(self.lc)
        c.drawString(14, self.bh - self.pad - 4, self.label)
        # Text
        style = ParagraphStyle('ct', fontName=FONT, fontSize=10,
                               leading=14, textColor=colors.HexColor('#333333'))
        p = Paragraph(self.raw, style)
        pw, ph = p.wrap(w - 28, self.bh)
        p.drawOn(c, 14, self.bh - self.pad - 14 - ph + 2)

# ── COVER BLOCK FLOWABLE ──
class CoverBlock(Flowable):
    def __init__(self, title, intro, width):
        super().__init__()
        self.title = title
        self.intro = intro
        self.bwidth = width

    def wrap(self, avail_w, avail_h):
        self.bwidth = avail_w
        # Measure title height
        words = self.title.split()
        lines, current = [], ''
        from reportlab.pdfbase.pdfmetrics import stringWidth
        for w in words:
            test = (current + ' ' + w).strip()
            if stringWidth(test, 'Helvetica-Bold', 26) < avail_w - 20:
                current = test
            else:
                lines.append(current)
                current = w
        if current: lines.append(current)
        self.title_lines = lines
        title_h = len(lines) * 34
        
        # Measure intro height
        intro_h = 0
        if self.intro:
            s = ParagraphStyle('i', fontName=FONT_ITALIC, fontSize=11, leading=16)
            p = Paragraph(self.intro, s)
            _, intro_h = p.wrap(avail_w - 40, 200)
        
        self.block_h = 60 + title_h + 16 + intro_h + 24
        return avail_w, self.block_h

    def draw(self):
        c = self.canv
        w = self.bwidth
        h = self.block_h
        # Lime background
        c.setFillColor(LIME)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        # Site name at top
        c.setFillColor(colors.HexColor('#555555'))
        c.setFont(FONT_BOLD, 8)
        c.drawCentredString(w/2, h - 22, 'DOITYADAMNSELF.COM')
        # Title
        c.setFillColor(BLACK)
        c.setFont(FONT_BOLD, 26)
        y = h - 50
        for line in self.title_lines:
            c.drawCentredString(w/2, y, line)
            y -= 34
        # Divider
        c.setStrokeColor(BLACK)
        c.setLineWidth(1.5)
        c.line(20, y - 4, w - 20, y - 4)
        # Intro
        if self.intro:
            s = ParagraphStyle('i', fontName=FONT_ITALIC, fontSize=11,
                               leading=16, textColor=colors.HexColor('#444444'),
                               alignment=TA_CENTER)
            p = Paragraph(self.intro, s)
            pw, ph = p.wrap(w - 40, 200)
            p.drawOn(c, 20, y - 14 - ph)

# ── PAGE TEMPLATE ──
def header_footer(canvas, doc):
    canvas.saveState()
    # Header bar - 40pt tall
    canvas.setFillColor(DARK)
    canvas.rect(0, H - 40, W, 40, fill=1, stroke=0)
    canvas.setFillColor(LIME)
    canvas.setFont('Helvetica-Bold', 10)
    canvas.drawString(MARGIN, H - 24, 'DOITYADAMNSELF.COM')
    canvas.setFillColor(colors.HexColor('#888888'))
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(W - MARGIN, H - 24, 'Your DIY Guide to Getting It Done')
    # Footer bar - 28pt tall
    canvas.setFillColor(LIME)
    canvas.rect(0, 0, W, 28, fill=1, stroke=0)
    canvas.setFillColor(BLACK)
    canvas.setFont('Helvetica', 7.5)
    canvas.drawString(MARGIN, 10, '© DoItYaDamnSelf.com — For personal use only. Not legal advice.')
    canvas.drawRightString(W - MARGIN, 10, f'Page {doc.page}')
    canvas.restoreState()

# ── TEXT PARSING: inline bold + links ──
def parse_inline(text):
    """Convert markdown inline formatting to reportlab XML."""
    # Escape XML chars first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<font name="Courier" size="9">\1</font>', text)
    # Links [text](url)
    def replace_link(m):
        label = m.group(1)
        url = m.group(2)
        return f'<link href="{url}"><font color="#0066CC"><u>{label}</u></font></link>'
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, text)
    return text

# ── MARKDOWN PARSER ──
def parse_markdown(md):
    """Parse markdown into a list of structured blocks."""
    lines = md.split('\n')
    blocks = []
    i = 0
    title = ''
    intro = ''

    while i < len(lines):
        line = lines[i]

        # Title
        if re.match(r'^#\s+', line) and i < 4:
            title = re.sub(r'^#\s+', '', line).strip()
            i += 1
            continue

        # H2
        if re.match(r'^##\s+', line):
            blocks.append({'type': 'h2', 'text': re.sub(r'^##\s+', '', line).strip()})
            i += 1
            continue

        # H3
        if re.match(r'^###\s+', line):
            blocks.append({'type': 'h3', 'text': re.sub(r'^###\s+', '', line).strip()})
            i += 1
            continue

        # Callout / blockquote
        if re.match(r'^>\s+', line):
            text = re.sub(r'^>\s+', '', line).strip()
            style = 'tip' if re.search(r'Pro Tip|✓', text) else 'warn' if re.search(r'Warning|⚠|Important', text, re.I) else 'note'
            # Clean the label prefix
            text = re.sub(r'^\*\*(Pro Tip|Warning|Important|Note):\*\*\s*', '', text)
            blocks.append({'type': 'callout', 'text': text, 'style': style})
            i += 1
            continue

        # Checklist item — only use checkbox in What You'll Need section
        if re.match(r'^\s*-\s+\[\s*\]\s+', line):
            text = re.sub(r'^\s*-\s+\[\s*\]\s+', '', line).strip()
            # Check if we've seen a Step heading yet
            in_steps = any(b.get('type') == 'h2' and 
                          any(w in b.get('text','').lower() for w in ['step', 'instruction', 'how', 'phase', 'process', 'file', 'dispute'])
                          for b in blocks)
            indent = len(line) - len(line.lstrip())
            if in_steps:
                # Inside steps — use bullet, not checkbox
                block_type = 'bullet2' if indent >= 2 else 'bullet1'
                blocks.append({'type': block_type, 'text': text})
            else:
                blocks.append({'type': 'checklist', 'text': text})
            i += 1
            continue

        # Sub-bullet (2+ spaces indent)
        if re.match(r'^\s{2,}[-*]\s+', line):
            text = re.sub(r'^\s+[-*]\s+', '', line).strip()
            blocks.append({'type': 'bullet2', 'text': text})
            i += 1
            continue

        # Main bullet
        if re.match(r'^\s*[-*]\s+', line):
            text = re.sub(r'^\s*[-*]\s+', '', line).strip()
            blocks.append({'type': 'bullet1', 'text': text})
            i += 1
            continue

        # Numbered sub-step (e.g. 1.1, 2.3)
        m = re.match(r'^(\d+\.\d+)\s+(.*)', line)
        if m:
            blocks.append({'type': 'num2', 'num': m.group(1), 'text': m.group(2).strip()})
            i += 1
            continue

        # Numbered step
        m = re.match(r'^(\d+)\.\s+(.*)', line)
        if m:
            blocks.append({'type': 'num1', 'num': m.group(1)+'.', 'text': m.group(2).strip()})
            i += 1
            continue

        # Table
        if re.match(r'^\|', line):
            rows = []
            while i < len(lines) and re.match(r'^\|', lines[i]):
                if not re.match(r'^[\|\s\-:]+$', lines[i]):
                    cells = [c.strip() for c in lines[i].split('|') if c.strip()]
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append({'type': 'table', 'rows': rows})
            continue

        # HR
        if re.match(r'^---+$', line.strip()):
            blocks.append({'type': 'hr'})
            i += 1
            continue

        # Empty line
        if not line.strip():
            blocks.append({'type': 'space'})
            i += 1
            continue

        # Regular paragraph
        if line.strip():
            blocks.append({'type': 'para', 'text': line.strip()})
        i += 1

    return title, blocks

# ── BUILD STORY FROM BLOCKS ──
def build_story(title, blocks):
    story = []
    is_first_para = True
    past_needs = False  # Track when we're past What You'll Need section

    def sp(n=6): return Spacer(1, n)

    # Paragraph styles
    sBody = ParagraphStyle('body', fontName=FONT, fontSize=10.5, leading=16,
                           textColor=BLACK, spaceAfter=8, alignment=TA_JUSTIFY)
    sIntro = ParagraphStyle('intro', fontName=FONT_ITALIC, fontSize=11, leading=16,
                            textColor=MUTED, spaceAfter=16, alignment=TA_CENTER)
    sH3 = ParagraphStyle('h3', fontName=FONT_BOLD, fontSize=11, leading=14,
                         textColor=colors.HexColor('#222222'), spaceBefore=14, spaceAfter=6)
    sBul1 = ParagraphStyle('b1', fontName=FONT, fontSize=10.5, leading=15,
                           textColor=BLACK, leftIndent=24, spaceAfter=5)
    sBul2 = ParagraphStyle('b2', fontName=FONT, fontSize=10, leading=14,
                           textColor=colors.HexColor('#444444'), leftIndent=52, spaceAfter=4)
    sNum1 = ParagraphStyle('n1', fontName=FONT, fontSize=10.5, leading=15,
                           textColor=BLACK, leftIndent=36, firstLineIndent=0, spaceAfter=5)
    sNum2 = ParagraphStyle('n2', fontName=FONT, fontSize=10, leading=14,
                           textColor=colors.HexColor('#444444'), leftIndent=64, spaceAfter=4)
    sCheck = ParagraphStyle('ck', fontName=FONT, fontSize=10.5, leading=15,
                            textColor=BLACK, leftIndent=24, spaceAfter=5)
    sResHead = ParagraphStyle('rh', fontName=FONT_BOLD, fontSize=10.5, leading=14,
                              textColor=BLACK, spaceBefore=10, spaceAfter=4)

    for block in blocks:
        t = block['type']

        if t == 'space':
            story.append(sp(5))

        elif t == 'hr':
            story.append(HRFlowable(width='100%', thickness=0.5,
                                    color=colors.HexColor('#dddddd'),
                                    spaceBefore=8, spaceAfter=8))

        elif t == 'h2':
            story.append(sp(6))
            story.append(Paragraph(
                f'<font color="#c5e835">&nbsp;&nbsp;{block["text"].upper()}&nbsp;&nbsp;</font>',
                ParagraphStyle('h2', fontName=FONT_BOLD, fontSize=13, leading=16,
                               textColor=LIME, backColor=DARK, spaceBefore=20, spaceAfter=10,
                               leftIndent=-6, rightIndent=-6,
                               borderPadding=(8, 10, 8, 10))
            ))

        elif t == 'h3':
            story.append(Paragraph(parse_inline(block['text']), sH3))

        elif t == 'callout':
            story.append(sp(4))
            story.append(CalloutBox(parse_inline(block['text']), block.get('style', 'note')))
            story.append(sp(4))

        elif t == 'checklist':
            # Use checkbox only in What You'll Need, regular bullet elsewhere
            if not past_needs:
                story.append(Paragraph(
                    f'&#9744;&nbsp;&nbsp;{parse_inline(block["text"])}',
                    sCheck
                ))
            else:
                story.append(Paragraph(
                    f'&#8226;&nbsp;&nbsp;{parse_inline(block["text"])}',
                    sBul1
                ))

        elif t == 'bullet1':
            story.append(Paragraph(
                f'&#8226;&nbsp;&nbsp;{parse_inline(block["text"])}',
                sBul1
            ))

        elif t == 'bullet2':
            story.append(Paragraph(
                f'–&nbsp;&nbsp;{parse_inline(block["text"])}',
                sBul2
            ))

        elif t == 'num1':
            story.append(Paragraph(
                f'<b>{block["num"]}</b>&nbsp;&nbsp;{parse_inline(block["text"])}',
                sNum1
            ))

        elif t == 'num2':
            story.append(Paragraph(
                f'<b>{block["num"]}</b>&nbsp;&nbsp;{parse_inline(block["text"])}',
                sNum2
            ))

        elif t == 'table':
            rows = block['rows']
            if not rows:
                continue
            max_cols = max(len(r) for r in rows)
            col_w = CONTENT_W / max_cols
            col_widths = [col_w] * max_cols

            table_data = []
            for ri, row in enumerate(rows):
                # Pad row if needed
                while len(row) < max_cols:
                    row.append('')
                table_data.append([
                    Paragraph(
                        f'<b>{parse_inline(cell)}</b>' if ri == 0 else parse_inline(cell),
                        ParagraphStyle('tc', fontName=FONT_BOLD if ri == 0 else 'Helvetica',
                                       fontSize=9.5 if ri == 0 else 10, leading=13,
                                       textColor=LIME if ri == 0 else BLACK)
                    ) for cell in row
                ])

            t_style = TableStyle([
                ('BACKGROUND', (0,0), (-1,0), DARK),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, ROW_ALT]),
                ('LINEBELOW', (0,0), (-1,0), 0, LIME),
                ('LINEBELOW', (0,-1), (-1,-1), 1.5, LIME),
                ('LINEBELOW', (0,1), (-1,-2), 0.5, colors.HexColor('#eeeeee')),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ])
            tbl = Table(table_data, colWidths=col_widths)
            tbl.setStyle(t_style)
            story.append(tbl)
            story.append(sp(8))

        elif t == 'para':
            text = parse_inline(block['text'])
            if is_first_para:
                # Skip intro para — it's already rendered on the cover page
                is_first_para = False
            else:
                story.append(Paragraph(text, sBody))

    return story


def convert_md_to_pdf(markdown_text, output_path):
    """Main conversion function."""
    title, blocks = parse_markdown(markdown_text)
    if not title:
        title = 'DIY Guide'

    # Extract intro (first para block before first h2)
    intro = ''
    for b in blocks:
        if b['type'] == 'h2':
            break
        if b['type'] == 'para':
            intro = b['text']
            break

    # Cover block at top of story — flows naturally, no blank pages
    cover = CoverBlock(title, intro, CONTENT_W)
    story = [cover, Spacer(1, 18)] + build_story(title, blocks)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.7*inch,    # Space below the 40pt header bar
        bottomMargin=0.5*inch,  # Space above the 28pt footer bar
        title=title,
        author='DoItYaDamnSelf.com',
    )

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f'✓ PDF created: {output_path}')
    return output_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 md2pdf.py guide.md [output.pdf]')
        sys.exit(1)
    md_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else md_file.replace('.md', '.pdf').replace('.txt', '.pdf')
    with open(md_file) as f:
        md = f.read()
    convert_md_to_pdf(md, out_file)

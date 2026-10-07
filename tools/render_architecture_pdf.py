"""Render the architecture Markdown to PDF without desktop application automation."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/BAO_CAO_KIEN_TRUC_MODEL.md"
TARGET = SOURCE.with_suffix(".pdf")
ASSETS = ROOT / "report_assets/model_architecture"


def inline(content):
    result = []
    pattern = re.compile(r"(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|`[^`]+`)")
    for token in pattern.split(content):
        link = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", token)
        if link:
            label, target = link.groups()
            if target.startswith("https://"):
                result.append(f'<a href="{html.escape(target, quote=True)}">{html.escape(label)}</a>')
            else:
                result.append(html.escape(label))
        elif token.startswith("**") and token.endswith("**"):
            result.append(f"<b>{html.escape(token[2:-2])}</b>")
        elif token.startswith("`") and token.endswith("`"):
            result.append(f"<code>{html.escape(token[1:-1])}</code>")
        else:
            result.append(html.escape(token))
    return "".join(result)


def to_html(markdown):
    lines, result, position = markdown.splitlines(), [], 0
    while position < len(lines):
        line = lines[position].strip()
        position += 1
        if not line:
            continue
        if line.startswith("```"):
            contents = []
            while position < len(lines) and not lines[position].startswith("```"):
                contents.append(lines[position])
                position += 1
            position += 1
            result.append(f"<pre>{html.escape(chr(10).join(contents))}</pre>")
            continue
        if line.startswith("|"):
            rows = [[cell.strip() for cell in line.strip("|").split("|")]]
            while position < len(lines) and lines[position].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[position].strip().strip("|").split("|")]
                position += 1
                if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                    continue
                rows.append(cells)
            table_class = ' class="layers"' if rows[0][0] == "Tầng" else ""
            result.append(f'<table width="100%"{table_class}>')
            for index, row in enumerate(rows):
                color = "#15324f" if index == 0 else "#f0f4f8" if index % 2 else "#ffffff"
                result.append(f'<tr style="background-color:{color}">')
                for col, cell in enumerate(row):
                    style = "color:white;font-weight:bold;" if index == 0 else ""
                    if rows[0][0] == "Artifact" and index > 0 and col == 1:
                        style += "font-family:ReportMono;font-size:8.5pt;"
                        # Explicit two-line hashes prevent narrow-cell overflow.
                        contents = html.escape(cell[:32]) + "<br/>" + html.escape(cell[32:])
                    else:
                        contents = inline(cell)
                    result.append(f'<td style="{style}">{contents}</td>')
                result.append("</tr>")
            result.append("</table>")
            continue
        image_match = re.fullmatch(r"!\[([^\]]+)\]\(([^)]+)\)", line)
        if image_match:
            caption, path = image_match.groups()
            absolute = (SOURCE.parent / path).resolve()
            from PIL import Image
            with Image.open(absolute) as image:
                width, height = image.size
            display_width = 439 if absolute.name == "classifier_architecture.png" else 475
            result.append(f'<div class="figure"><img src="{absolute.relative_to(ROOT).as_posix()}" '
                          f'width="{display_width}" height="{display_width * height / width:.2f}"/>'
                          f'<p class="caption">{html.escape(caption)}</p></div>')
            continue
        heading = re.match(r"^(#{1,3}) (.*)$", line)
        if heading:
            level = len(heading.group(1))
            result.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif line.startswith("- "):
            items = [line[2:]]
            while position < len(lines) and lines[position].strip().startswith("- "):
                items.append(lines[position].strip()[2:])
                position += 1
            result.append("<ul>" + "".join(f"<li>{inline(item)}</li>" for item in items) + "</ul>")
        else:
            contents = [line]
            while position < len(lines):
                candidate = lines[position].strip()
                if not candidate or candidate.startswith(("#", "|", "![", "- ", "```")):
                    break
                contents.append(candidate)
                position += 1
            result.append(f"<p>{inline(' '.join(contents))}</p>")
    return "\n".join(result)


def main():
    css = """
    @font-face {font-family:ReportSerif;src:url(fonts/times.ttf);}
    @font-face {font-family:ReportSerif;font-weight:bold;src:url(fonts/timesbd.ttf);}
    @font-face {font-family:ReportSerif;font-style:italic;src:url(fonts/timesi.ttf);}
    @font-face {font-family:ReportSans;src:url(fonts/calibri.ttf);}
    @font-face {font-family:ReportSans;font-weight:bold;src:url(fonts/calibrib.ttf);}
    @font-face {font-family:ReportMono;src:url(fonts/consola.ttf);}
    body {font-family:ReportSerif;font-size:11.5pt;line-height:1.08;color:#152b40;margin:0;}
    p {margin-top:0;margin-bottom:6pt;text-align:justify;}
    h1,h2,h3 {font-family:ReportSans;color:#15324f;page-break-after:avoid;}
    h1 {font-size:21pt;margin-top:0;margin-bottom:10pt;}
    h2 {font-size:16pt;margin-top:0;margin-bottom:8pt;}
    h3 {font-size:13pt;margin-top:10pt;margin-bottom:6pt;}
    table {border-collapse:collapse;margin-top:4pt;margin-bottom:8pt;font-size:10pt;}
    td {border:0.5pt solid #d5dfe8;padding:4pt;vertical-align:middle;}
    .layers td {padding:2pt;}
    tr {page-break-inside:avoid;}
    code,pre {font-family:ReportMono;font-size:9pt;}
    pre {background-color:#f0f4f8;padding:8pt;margin-bottom:8pt;}
    a {color:#176789;}
    .figure {page-break-inside:avoid;margin:5pt 0;text-align:center;}
    .caption {font-size:10pt;font-style:italic;text-align:center;color:#56687a;margin-top:4pt;}
    ul {margin:0 0 7pt 0;padding-left:16pt;}
    li {margin-bottom:4pt;}
    """
    archive = pymupdf.Archive(str(ROOT))
    archive.add("C:/Windows/Fonts", "fonts")
    document = pymupdf.open()
    markdown = SOURCE.read_text(encoding="utf-8")
    page_rect = pymupdf.Rect(0, 0, 595.28, 841.89)

    def rectangles(number, filled):
        if number > 5:
            raise ValueError("Report section overflowed unexpectedly")
        return page_rect, pymupdf.Rect(56.7, 51, 538.58, 790.9), None

    section_pages = []
    for section in markdown.split("<!-- page-break -->"):
        story = pymupdf.Story(html=to_html(section), user_css=css, em=11.5, archive=archive)
        fragment = story.write_with_links(rectangles)
        section_pages.append(fragment.page_count)
        document.insert_pdf(fragment, links=True)
        fragment.close()
    for number, page in enumerate(document, 1):
        page.insert_font(fontname="reporthdr", fontfile="C:/Windows/Fonts/calibri.ttf")
        page.insert_text((56.7, 31), "GIÁM SÁT TÀI XẾ  |  KIẾN TRÚC MODEL", fontname="reporthdr", fontsize=8.5,
                         color=(0.34, 0.41, 0.48))
        page.insert_textbox(pymupdf.Rect(56.7, 809, 538.58, 827), f"06/10/2026   •   Trang {number} / {document.page_count}",
                            fontname="reporthdr", fontsize=9, color=(0.34, 0.41, 0.48), align=2)
    document.set_metadata({"title": "Báo cáo kiến trúc model giám sát tài xế", "author": "Driver Monitor Project",
                           "subject": "YuNet + hai YOLOv8n-cls, Radxa ROCK 4D RK3576"})
    document.save(TARGET, garbage=4, deflate=True)
    # Verify the serialized PDF, including final font/resource mappings.
    document.close()
    document = pymupdf.open(TARGET)
    texts = [page.get_text() for page in document]
    full_text = "\n".join(texts)
    manifest = json.loads((ROOT / "models/manifest.json").read_text(encoding="utf-8"))
    hashes = [manifest["detector"]["sha256"]] + [item["sha256"] for spec in manifest["classifiers"].values()
                                                for item in spec["artifacts"].values()]
    compact_text = re.sub(r"\s+", "", full_text)
    if not all(digest in compact_text for digest in hashes):
        raise ValueError("A model fingerprint is missing from PDF")
    missing_references = [target for target in re.findall(r"\]\(([^)]+)\)", markdown)
                          if not target.startswith("https://") and not (SOURCE.parent / target).is_file()]
    if missing_references:
        raise ValueError(f"Missing local report references: {missing_references}")
    outside = [(number + 1, span["text"]) for number, page in enumerate(document)
               for block in page.get_text("dict")["blocks"] if block["type"] == 0
               for line in block["lines"] for span in line["spans"]
               if span["bbox"][0] < 48 or span["bbox"][2] > 547 or span["bbox"][1] < 15 or span["bbox"][3] > 832]
    if outside:
        raise ValueError(f"PDF text outside printable bounds: {outside}")
    for required in ("1.440.850", "RK3576", "53104", "UNKNOWN"):
        if required == "53104":
            if "53.104" not in full_text:
                raise ValueError("Missing YuNet weight count")
        elif required not in full_text:
            raise ValueError(f"Required report fact missing from PDF: {required}")
    ASSETS.mkdir(exist_ok=True, parents=True)
    for number, page in enumerate(document, 1):
        page.get_pixmap(matrix=pymupdf.Matrix(0.9, 0.9), alpha=False).save(ASSETS / f"page_{number:02d}.png")
    metadata = {"renderer": "PyMuPDF HTML Story from the reviewed Markdown; independent of Word pagination",
                "pymupdf": pymupdf.VersionBind, "pages": document.page_count,
                "pages_per_section": section_pages, "pdf_bytes": TARGET.stat().st_size,
                "pdf_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                "page_text_characters": [len(text) for text in texts],
                "verified_model_fingerprints": len(hashes), "missing_local_references": missing_references,
                "text_outside_printable_bounds": outside,
                "docx_structure_checked": True, "docx_desktop_render_checked": False}
    (ROOT / "reports/model_architecture_render.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    document.close()


if __name__ == "__main__":
    main()

import io

import pytest
from docx import Document

from interview_app.extractors import extract_text_from_file, find_links


def minimal_pdf(text: str) -> bytes:
    """A one-page PDF containing `text`, built by hand so the tests need no PDF writer."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n%s\nendobj\n" % (number, content)
    xref = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        body += b"%010d 00000 n \n" % offset
    body += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return body


def test_text_is_read_from_a_pdf(tmp_path):
    path = tmp_path / "cv.pdf"
    path.write_bytes(minimal_pdf("Jane Doe, backend developer"))
    assert "Jane Doe, backend developer" in extract_text_from_file(str(path))


def test_text_is_read_from_a_word_file_including_tables(tmp_path):
    document = Document()
    document.add_paragraph("Experienced developer")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Python"
    table.rows[0].cells[1].text = "5 years"
    path = tmp_path / "cv.docx"
    buffer = io.BytesIO()
    document.save(buffer)
    path.write_bytes(buffer.getvalue())
    text = extract_text_from_file(str(path))
    assert "Experienced developer" in text
    assert "Python | 5 years" in text


def test_a_text_file_is_read_as_is(tmp_path):
    path = tmp_path / "cv.txt"
    path.write_text("plain text cv", encoding="utf-8")
    assert extract_text_from_file(str(path)) == "plain text cv"


def test_an_unsupported_format_is_refused(tmp_path):
    path = tmp_path / "cv.rtf"
    path.write_text("x")
    with pytest.raises(ValueError, match="Unsupported"):
        extract_text_from_file(str(path))


def test_links_are_found_in_the_text():
    links = find_links("See https://github.com/jane/project and (https://jane.dev/about).")
    assert "https://github.com/jane/project" in links
    assert any(link.startswith("https://jane.dev/about") for link in links)

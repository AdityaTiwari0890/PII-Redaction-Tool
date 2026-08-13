from docx import Document

doc = Document(r"docs\Red Herring Prospectus.docx")
print("Total paragraphs:", len(doc.paragraphs))
print("Total tables:", len(doc.tables))

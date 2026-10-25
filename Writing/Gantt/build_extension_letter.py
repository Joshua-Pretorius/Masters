from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUTPUT = Path(r"D:\Masters\Writing\Gantt\MSc_Extension_Letter_of_Explanation.docx")

doc = Document()
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.top_margin = Inches(0.9)
section.bottom_margin = Inches(0.85)
section.left_margin = Inches(0.95)
section.right_margin = Inches(0.95)

styles = doc.styles
normal = styles["Normal"]
normal.font.name = "Arial"
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor(0, 0, 0)
normal.paragraph_format.space_after = Pt(10)
normal.paragraph_format.line_spacing = 1.15

title = styles["Title"]
title.font.name = "Arial"
title.font.size = Pt(14)
title.font.bold = True
title.font.color.rgb = RGBColor(0, 0, 0)
title.paragraph_format.space_after = Pt(14)
title_properties = title._element.get_or_add_pPr()
title_border = title_properties.find(qn("w:pBdr"))
if title_border is not None:
    title_properties.remove(title_border)

doc.add_paragraph("Request for extension of study period", style="Title")

p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(2)
p.add_run("To the Postgraduate Review Committee").bold = True
p = doc.add_paragraph("University of Pretoria")
p.paragraph_format.space_after = Pt(16)

doc.add_paragraph("Dear Committee Members")

doc.add_paragraph(
    "I request an extension of my study period to 31 March 2027 to complete my MSc dissertation "
    "in Geoinformatics. The accompanying Gantt chart sets out a focused plan for the remaining "
    "research, writing, review and submission stages."
)

doc.add_paragraph(
    "My research develops a synthetic aperture radar based training dataset and machine learning "
    "model for detecting floating marine plastics in the South African exclusive economic zone. "
    "The principal reason for the extension is the time needed to produce a reliable, locally "
    "relevant labelled dataset before the model can be trained and evaluated. This involves "
    "matching marine debris evidence with satellite scenes, reviewing uncertainty in the labels, "
    "preprocessing the imagery and assembling suitable samples. Completing these steps carefully "
    "is necessary for a defensible evaluation of the model."
)

doc.add_paragraph(
    "I plan to finish data labelling and sample assembly by the end of November 2026, train and "
    "refine the model during December, and evaluate it in January 2027. I will then complete the "
    "main writing in February and March, including the methods, results, discussion and conclusion, "
    "and refine the introduction once the findings are clear. I will prepare a journal article for "
    "submission alongside the final thesis writing."
)

doc.add_paragraph(
    "My target is to provide a complete draft to my supervisor by mid March, incorporate feedback "
    "and complete the final checks before submitting the dissertation by 31 March 2027. I respectfully "
    "ask that the extension be granted so that I can complete these remaining stages and submit a "
    "coherent, properly reviewed dissertation."
)

p = doc.add_paragraph("Yours faithfully")
p.paragraph_format.space_before = Pt(10)
p.paragraph_format.space_after = Pt(26)

p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(2)
p.add_run("JW Pretorius").bold = True
p = doc.add_paragraph("Student number 20499435")
p.paragraph_format.space_after = Pt(0)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUTPUT)
print(OUTPUT)

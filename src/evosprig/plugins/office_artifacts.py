"""Office artifacts use a single calculated ledger and explicit number placeholders."""

import re
from decimal import Decimal
from html import escape


def analyze(rows):
    def total(key):
        return sum((Decimal(str(row[key])) for row in rows), Decimal(0))

    revenue, cost = total("revenue"), total("cost")
    profit = revenue - cost
    return {"revenue": float(revenue), "cost": float(cost), "profit": float(profit),
            "orders": int(total("orders")), "margin_pct": float(profit / revenue * 100) if revenue else 0,
            "periods": len(rows), "best_period": max(rows, key=lambda r: r["revenue"] - r["cost"])["period"],
            "profit_by_period": [{"period": r["period"], "profit": float(Decimal(str(r["revenue"])) - Decimal(str(r["cost"])))} for r in rows]}


def create_office(destination, rows, title, summary, recommendations):
    import xlsxwriter
    from docx import Document
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    metrics = analyze(rows)

    def render(text):
        def replace(match):
            key = match.group(1)
            if key not in metrics or isinstance(metrics[key], list):
                raise ValueError("Unknown metric placeholder: " + key)
            value = metrics[key]
            return f"{value:,.2f}" if isinstance(value, float) else str(value)
        return re.sub(r"\{\{([a-z_]+)\}\}", replace, text)

    summary = render(summary)
    recommendations = [render(text) for text in recommendations]
    workbook = xlsxwriter.Workbook(destination / "analysis.xlsx")
    worksheet = workbook.add_worksheet("Analysis")
    header = workbook.add_format({"bold": True, "bg_color": "#E7EEF6"})
    money = workbook.add_format({"num_format": "#,##0.00"})
    percent = workbook.add_format({"num_format": "0.0%"})
    for col, value in enumerate(["Period", "Revenue", "Cost", "Orders", "Profit", "Margin"]):
        worksheet.write(0, col, value, header)
    for index, row in enumerate(rows, 1):
        worksheet.write_string(index, 0, row["period"])
        for col, key in enumerate(["revenue", "cost", "orders"], 1):
            worksheet.write_number(index, col, row[key], money if col < 3 else None)
        n = index + 1
        profit = metrics["profit_by_period"][index-1]["profit"]
        worksheet.write_formula(index, 4, f"=B{n}-C{n}", money, profit)
        worksheet.write_formula(index, 5, f"=IFERROR(E{n}/B{n},0)", percent, profit/row["revenue"] if row["revenue"] else 0)
    last = len(rows) + 1
    worksheet.write_string(last, 0, "Total", header)
    for col, key in enumerate(["revenue", "cost", "orders", "profit"], 1):
        letter = chr(65+col)
        worksheet.write_formula(last, col, f"=SUM({letter}2:{letter}{last})", money, metrics[key])
    worksheet.write_formula(last, 5, f"=IFERROR(E{last+1}/B{last+1},0)", percent, metrics["margin_pct"]/100)
    worksheet.set_column(0, 5, 18)
    worksheet.freeze_panes(1, 1)
    chart = workbook.add_chart({"type": "column"})
    chart.add_series({"name": "Profit", "categories": ["Analysis", 1, 0, len(rows), 0],
                      "values": ["Analysis", 1, 4, len(rows), 4]})
    worksheet.insert_chart("H2", chart)
    workbook.close()

    document = Document()
    document.add_heading(title, 0)
    document.add_paragraph(summary)
    table = document.add_table(rows=1, cols=2)
    table.style = "Light Shading Accent 1"
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Metric", "Value"
    for key in ["revenue", "cost", "profit", "orders", "margin_pct"]:
        cells = table.add_row().cells
        cells[0].text, cells[1].text = key.replace("_", " ").title(), render("{{" + key + "}}")
    document.add_heading("Next steps", 1)
    for item in recommendations:
        document.add_paragraph(item, style="List Bullet")
    document.save(destination / "brief.docx")

    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)

    def slide(heading, lines):
        page = deck.slides.add_slide(deck.slide_layouts[6])
        box = page.shapes.add_textbox(Inches(.7), Inches(.6), Inches(12), Inches(1))
        box.text_frame.text = heading
        box.text_frame.paragraphs[0].font.size = Pt(30)
        box.text_frame.paragraphs[0].font.bold = True
        for idx, line in enumerate(lines):
            frame = page.shapes.add_textbox(Inches(.8), Inches(2 + idx*1.3), Inches(11.7), Inches(1.15)).text_frame
            frame.word_wrap = True
            frame.text = line
            for paragraph in frame.paragraphs:
                paragraph.font.size = Pt(22)
                paragraph.font.color.rgb = RGBColor.from_string("253245")
        return page

    # Small pages keep prose editable and avoid silently squeezing whole reports onto a slide.
    slide(title[:100], [summary[:450]])
    slide("The numbers", [render("Revenue  {{revenue}}    Profit  {{profit}}"),
                          render("Margin  {{margin_pct}}%    Orders  {{orders}}"),
                          render("Strongest period  {{best_period}}")])
    for index in range(0, len(recommendations), 3):
        slide("Next steps", [item[:250] for item in recommendations[index:index+3]])
    deck.save(destination / "report.pptx")
    html = '<!doctype html><meta charset="utf-8"><title>'+escape(title)+'</title><style>body{max-width:960px;margin:60px auto;font:20px system-ui;color:#253245}table{border-collapse:collapse;width:100%}td,th{padding:14px;border-bottom:1px solid #ddd;text-align:left}h1{font-size:38px}</style>'
    html += '<h1>'+escape(title)+'</h1><p>'+escape(summary)+'</p><table><tr><th>Period</th><th>Revenue</th><th>Cost</th><th>Profit</th></tr>'
    for row, values in zip(rows, metrics["profit_by_period"], strict=True):
        html += '<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in [row['period'],row['revenue'],row['cost'],values['profit']])+'</tr>'
    html += '</table><h2>Next steps</h2><ul>'+''.join('<li>'+escape(item)+'</li>' for item in recommendations)+'</ul>'
    (destination / "preview.html").write_text(html)
    return {"files": ["analysis.xlsx", "brief.docx", "report.pptx", "preview.html"], "metrics": metrics,
            "summary": summary, "recommendations": recommendations}

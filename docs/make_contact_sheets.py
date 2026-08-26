from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent / "rendered"


def make_sheet(folder_name: str, page_numbers: list[int], output_name: str) -> None:
    page_width = 520
    label_height = 32
    gap = 20
    margin = 20
    columns = 2
    pages = []

    for number in page_numbers:
        image = Image.open(ROOT / folder_name / f"page-{number}.png").convert("RGB")
        height = round(image.height * page_width / image.width)
        pages.append((number, image.resize((page_width, height), Image.Resampling.LANCZOS)))

    cell_height = max(image.height for _, image in pages) + label_height
    rows = (len(pages) + columns - 1) // columns
    sheet_width = margin * 2 + columns * page_width + (columns - 1) * gap
    sheet_height = margin * 2 + rows * cell_height + (rows - 1) * gap
    sheet = Image.new("RGB", (sheet_width, sheet_height), "#d7dce3")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)

    for index, (number, image) in enumerate(pages):
        row, column = divmod(index, columns)
        x = margin + column * (page_width + gap)
        y = margin + row * (cell_height + gap)
        draw.text((x, y), f"{folder_name.title()} – page {number}", fill="#111827", font=font)
        sheet.paste(image, (x, y + label_height))

    sheet.save(ROOT / output_name, quality=92)


make_sheet("chatbot", [1, 2, 3, 4], "chatbot-contact-1.jpg")
make_sheet("chatbot", [5, 6, 7, 8], "chatbot-contact-2.jpg")
make_sheet("chatbot", [9], "chatbot-contact-3.jpg")
make_sheet("business", [1, 2, 3, 4], "business-contact-1.jpg")
make_sheet("business", [5, 6, 7, 8], "business-contact-2.jpg")

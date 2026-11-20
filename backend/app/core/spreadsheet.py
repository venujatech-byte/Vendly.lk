"""Write exported spreadsheet values without inferring formulas from text."""

from openpyxl.cell import Cell


def write_export_cell(cell, value):
    cell.value = value
    # openpyxl infers formulas and error cells from some strings on assignment.
    if isinstance(value, str):
        cell.data_type = "s"
    return cell


def append_export_row(sheet, values):
    # Worksheet.append accepts explicitly typed cells alongside ordinary numbers.
    sheet.append([write_export_cell(Cell(sheet), value) if isinstance(value, str) else value for value in values])

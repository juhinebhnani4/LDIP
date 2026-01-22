"""Table formatting utilities.

Converts Docling table structures to various formats
including Markdown and JSON for storage and retrieval.
"""

from typing import Any


class TableFormatter:
    """Convert tables to various formats for storage and display."""

    def to_markdown(self, table_data: list[list[Any]]) -> str:
        """Convert table data to Markdown format.

        Args:
            table_data: 2D list of cell values, first row is header.

        Returns:
            Markdown-formatted table string.
        """
        if not table_data:
            return ""

        rows = table_data
        if not rows or not rows[0]:
            return ""

        # Sanitize cell values
        def sanitize_cell(cell: Any) -> str:
            text = str(cell) if cell is not None else ""
            # Escape pipe characters and newlines for Markdown
            return text.replace("|", "\\|").replace("\n", " ").strip()

        # Build header row
        header = rows[0]
        header_cells = [sanitize_cell(cell) for cell in header]
        md_lines = [
            "| " + " | ".join(header_cells) + " |",
            "| " + " | ".join("---" for _ in header_cells) + " |",
        ]

        # Build body rows
        for row in rows[1:]:
            # Ensure row has same number of columns as header
            cells = list(row) + [""] * (len(header) - len(row))
            cells = cells[: len(header)]  # Truncate if too many
            row_cells = [sanitize_cell(cell) for cell in cells]
            md_lines.append("| " + " | ".join(row_cells) + " |")

        return "\n".join(md_lines)

    def to_json(self, table_data: list[list[Any]]) -> list[dict[str, Any]]:
        """Convert table data to JSON format (list of row dicts).

        Args:
            table_data: 2D list of cell values, first row is header.

        Returns:
            List of dictionaries, one per data row.
        """
        if not table_data or len(table_data) < 2:
            return []

        headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(table_data[0])]

        result = []
        for row in table_data[1:]:
            row_dict: dict[str, Any] = {}
            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else None
                row_dict[header] = str(value) if value is not None else ""
            result.append(row_dict)

        return result

    def to_csv_string(self, table_data: list[list[Any]]) -> str:
        """Convert table data to CSV string.

        Args:
            table_data: 2D list of cell values.

        Returns:
            CSV-formatted string.
        """
        if not table_data:
            return ""

        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        for row in table_data:
            writer.writerow([str(cell) if cell is not None else "" for cell in row])

        return output.getvalue()

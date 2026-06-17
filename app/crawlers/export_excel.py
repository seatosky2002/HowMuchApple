import argparse
import math
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import create_engine, text

from app.core.config import settings


EXPORT_COLUMNS = (
    "run_id",
    "crawled_at",
    "platform",
    "crawler_class",
    "keyword",
    "item_rank",
    "title",
    "price",
    "url",
    "external_id",
    "dedupe_key",
    "sgg",
    "emd",
    "dong_code",
    "sku_id",
    "category_id",
    "status",
    "item_id",
    "is_new_record",
    "parse_status",
    "parse_error",
    "source_payload_id",
    "updated_at_db",
)

CRAWLER_CLASSES = {
    "daangn": "DaangnCrawler",
    "bunjang": "BunjangCrawler",
    "joongna": "JoognaCrawler",
}


def export_latest_results(output_path: Path, limit_per_platform: int = 200) -> int:
    rows = _fetch_latest_rows(limit_per_platform)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_xlsx(output_path, [EXPORT_COLUMNS, *([row.get(column) for column in EXPORT_COLUMNS] for row in rows)])
    return len(rows)


def _fetch_latest_rows(limit_per_platform: int) -> list[dict[str, Any]]:
    query = """
        WITH latest_logs AS (
            SELECT
                log_id,
                platform,
                started_at,
                finished_at
            FROM (
                SELECT
                    log_id,
                    platform,
                    started_at,
                    finished_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY platform
                        ORDER BY finished_at IS NULL, finished_at DESC, log_id DESC
                    ) AS log_rank
                FROM crawler_log
                WHERE status = 'success'
                  AND platform IN ('daangn', 'bunjang', 'joongna')
            ) latest
            WHERE log_rank = 1
        ),
        ranked_items AS (
            SELECT
                l.log_id AS run_id,
                l.started_at AS run_started_at,
                l.finished_at AS crawled_at,
                i.source AS platform,
                CASE i.source
                    WHEN 'daangn' THEN 'DaangnCrawler'
                    WHEN 'bunjang' THEN 'BunjangCrawler'
                    WHEN 'joongna' THEN 'JoognaCrawler'
                    ELSE ''
                END AS crawler_class,
                i.search_keyword AS keyword,
                row_number() OVER (
                    PARTITION BY i.source
                    ORDER BY i.updated_at IS NULL, i.updated_at DESC, i.item_id DESC
                ) AS item_rank,
                i.title,
                i.price,
                i.url,
                i.external_id,
                CONCAT(i.source, ':', i.external_id) AS dedupe_key,
                i.region_sgg AS sgg,
                i.region_emd AS emd,
                i.dong_code AS dong_code,
                i.sku_id,
                i.category_id,
                CAST(i.status AS CHAR) AS status,
                i.item_id,
                CASE
                    WHEN i.created_at >= l.started_at
                     AND (l.finished_at IS NULL OR i.created_at <= l.finished_at)
                    THEN true
                    ELSE false
                END AS is_new_record,
                CASE
                    WHEN i.title IS NOT NULL
                     AND i.url IS NOT NULL
                     AND i.external_id IS NOT NULL
                     AND i.price IS NOT NULL
                    THEN 'parsed'
                    ELSE 'parse_error'
                END AS parse_status,
                '' AS parse_error,
                '' AS source_payload_id,
                i.updated_at AS updated_at_db
            FROM item i
            JOIN latest_logs l ON l.platform = i.source
            WHERE i.source IN ('daangn', 'bunjang', 'joongna')
        )
        SELECT
            run_id,
            crawled_at,
            platform,
            crawler_class,
            keyword,
            item_rank,
            title,
            price,
            url,
            external_id,
            dedupe_key,
            sgg,
            emd,
            dong_code,
            sku_id,
            category_id,
            status,
            item_id,
            is_new_record,
            parse_status,
            parse_error,
            source_payload_id,
            updated_at_db
        FROM ranked_items
        WHERE item_rank <= :limit_per_platform
        ORDER BY
            CASE platform WHEN 'daangn' THEN 1 WHEN 'bunjang' THEN 2 WHEN 'joongna' THEN 3 ELSE 9 END,
            item_rank
    """
    engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text(query), {"limit_per_platform": limit_per_platform})
        return [dict(row) for row in result.mappings().all()]


def _write_xlsx(path: Path, rows: list[tuple[Any, ...] | list[Any]]) -> None:
    sheet_xml = _worksheet_xml(rows)
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="crawl_results" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>"""
    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>"""
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>"""

    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _worksheet_xml(rows: list[tuple[Any, ...] | list[Any]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(_cell_xml(row_index, column_index, value) for column_index, value in enumerate(row, start=1))
        row_xml.append(f'<row r="{row_index}">{cells}</row>')

    dimension = f"A1:{_cell_ref(len(rows), len(EXPORT_COLUMNS))}" if rows else "A1"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetData>'
        + "".join(row_xml)
        + '</sheetData><autoFilter ref="A1:W1"/></worksheet>'
    )


def _cell_xml(row_index: int, column_index: int, value: Any) -> str:
    ref = _cell_ref(row_index, column_index)
    if value is None:
        return f'<c r="{ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, int) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    if isinstance(value, float) and math.isfinite(value):
        return f'<c r="{ref}"><v>{value}</v></c>'

    return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_text(_format_text(value))}</t></is></c>'


def _cell_ref(row_index: int, column_index: int) -> str:
    letters = ""
    index = column_index
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row_index}"


def _format_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _xml_text(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch in "\t\n\r" or ord(ch) >= 32)
    return escape(cleaned, {'"': "&quot;"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export latest crawler rows to an Excel workbook.")
    parser.add_argument("--limit-per-platform", type=int, default=200)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output or Path("exports") / f"apple_crawl_results_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    row_count = export_latest_results(output_path, args.limit_per_platform)
    print(f"exported {row_count} rows to {output_path}")


if __name__ == "__main__":
    main()

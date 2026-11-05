"""PDF sales report written with Qt's own PDF support (no extra dependency).

`report_content` gathers already computed results (financial cards, top
products, chart values) from the session; `report_html` lays them out; and
`write_pdf` prints that HTML with QTextDocument into a QPdfWriter. The PDF is
first written to a temporary file in the target folder and then moved into
place, so a failure never leaves a partial report behind.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from html import escape
from io import BytesIO
import os
from pathlib import Path
import tempfile

from sales_data_analyzer.application import SalesSession

from . import reports
from .texts import moment, t, weekday

CHART_KINDS = ("daily", "monthly", "products")
"""Charts included in the report (the same three as the PNG export)."""


class ReportWriteError(OSError):
    """Raised when the PDF cannot be written; no file was left behind."""


@dataclass(frozen=True)
class ReportContent:
    """Everything printed in the report, already formatted for display."""

    company: str
    sector: str
    period: str
    generated: str
    cards: tuple[reports.Card, ...]
    top_products: reports.Table
    charts: tuple[tuple[str, bytes], ...]
    forecast_note: str | None


def _chart_png(kind: str, inputs, labels) -> bytes:
    """Render one chart to PNG bytes with Matplotlib's Agg renderer."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    from sales_data_analyzer.charts.images import build_figure

    figure = build_figure(kind, inputs, labels)
    if kind == "daily":
        from matplotlib.dates import DateFormatter

        figure.axes[0].xaxis.set_major_formatter(DateFormatter(t("charts.date_axis")))
    figure.set_layout_engine("constrained")
    stream = BytesIO()
    FigureCanvasAgg(figure).print_png(stream)
    return stream.getvalue()


def report_content(session: SalesSession, now: datetime | None = None) -> ReportContent:
    """Collect the report of the active selection (NoSalesInSelectionError when empty)."""
    from sales_data_analyzer.charts.images import ChartInputs, has_data

    from .pages.charts import chart_labels
    from .texts import method_title

    workspace = session.require_current()
    cards = reports.financial_cards(session)
    top = reports.top_products_table(session, limit=10)
    data = session.chart_data()
    period = reports.period_text(session.selection)
    method = (
        method_title(data.forecast_key, data.forecast_title or "") if data.forecast_key
        else data.forecast_title
    )  # fmt: skip
    inputs = replace(
        ChartInputs.from_data(data, weekday_names=[weekday(i)[:3] for i in range(7)]),
        title=f"{workspace.company.name} — {period}",
        forecast_title=method,
    )
    labels = chart_labels()
    charts = tuple(
        (kind, _chart_png(kind, inputs, labels)) for kind in CHART_KINDS if has_data(kind, inputs)
    )
    if data.forecast_refusal is not None:
        note = t(
            "charts.forecast_off", reason=reports.explain_forecast_refusal(data.forecast_refusal)
        )
    else:
        note = t("report.forecast_note", title=method)
    return ReportContent(
        company=workspace.company.name,
        sector=workspace.company.sector,
        period=period,
        generated=moment((now or datetime.now()).replace(microsecond=0)),
        cards=cards,
        top_products=top,
        charts=charts,
        forecast_note=note,
    )


def _table_html(table: reports.Table) -> str:
    """Return a styled HTML table (numbers right-aligned)."""
    head = "".join(
        f'<th align="{"right" if i in table.numeric else "left"}">{escape(h)}</th>'
        for i, h in enumerate(table.headers)
    )
    rows = "".join(
        "<tr>" + "".join(
            f'<td align="{"right" if i in table.numeric else "left"}">{escape(cell)}</td>'
            for i, cell in enumerate(row)
        ) + "</tr>"
        for row in table.rows
    )  # fmt: skip
    return f'<table class="data" cellspacing="0" cellpadding="5" width="100%"><tr>{head}</tr>{rows}</table>'


def report_html(content: ReportContent) -> str:
    """Return the report as HTML; chart images are referenced as `chart:<kind>`."""
    cards = "".join(
        f'<td class="card"><span class="label">{escape(c.label)}</span><br>'
        f'<span class="value">{escape(c.value)}</span></td>' + ("</tr><tr>" if index == 2 else "")
        for index, c in enumerate(content.cards)
    )
    charts = "".join(
        f'<p align="center"><img src="chart:{kind}" width="620"></p>' for kind, _ in content.charts
    )
    note = f'<p class="note">{escape(content.forecast_note)}</p>' if content.forecast_note else ""
    return f"""
<html><head><style>
body {{ font-family: sans-serif; color: #1f2933; font-size: 10pt; }}
h1 {{ color: #1f3a4d; font-size: 18pt; margin-bottom: 2px; }}
h2 {{ color: #c2531f; font-size: 13pt; margin-top: 16px; }}
p.meta {{ color: #5f6b76; margin: 0; }}
td.card {{ background: #f3eee6; padding: 8px; }}
span.label {{ color: #5f6b76; font-size: 9pt; }}
span.value {{ font-size: 14pt; font-weight: bold; color: #1f5fae; }}
table.data th {{ background: #f3eee6; border-bottom: 1px solid #d5cdc0; }}
table.data td {{ border-bottom: 1px solid #eee6da; }}
p.note {{ color: #5f6b76; font-size: 9pt; }}
</style></head><body>
<h1>{escape(t("report.heading", company=content.company))}</h1>
<p class="meta">{escape(t("report.company", name=content.company, sector=content.sector))}</p>
<p class="meta">{escape(t("report.period", period=content.period))}</p>
<p class="meta">{escape(t("report.generated", moment=content.generated))}</p>
<h2>{escape(t("report.financial"))}</h2>
<table cellspacing="6" width="100%"><tr>{cards}</tr></table>
<h2>{escape(t("report.top_products"))}</h2>
{_table_html(content.top_products)}
<h2>{escape(t("report.charts"))}</h2>
{charts}
{note}
<p class="note">{escape(t("report.footer"))}</p>
</body></html>
"""


def document(content: ReportContent):  # -> QTextDocument
    """Return a QTextDocument of the report with its chart images attached."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QTextDocument

    doc = QTextDocument()
    for kind, png in content.charts:
        doc.addResource(
            QTextDocument.ResourceType.ImageResource, QUrl(f"chart:{kind}"), QImage.fromData(png)
        )
    doc.setHtml(report_html(content))
    return doc


def write_pdf(content: ReportContent, path: str | Path) -> Path:
    """Write the report as an A4 PDF at path, all or nothing; return the path.

    Raise ReportWriteError when the folder cannot be written (no file is left).
    """
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter

    path = Path(path)
    folder = path.parent
    try:
        handle, temporary = tempfile.mkstemp(prefix=".report-", suffix=".pdf", dir=folder)
        os.close(handle)
    except OSError:
        raise ReportWriteError("the folder cannot be written") from None
    try:
        writer = QPdfWriter(temporary)
        writer.setResolution(96)  # so HTML pixel sizes match the on-screen preview
        writer.setTitle(t("report.heading", company=content.company))
        writer.setCreator(t("app.title"))
        writer.setPageLayout(
            QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(15, 15, 15, 15),
                QPageLayout.Unit.Millimeter,
            )
        )
        document(content).print_(writer)
        del writer  # flush and close the file before moving it
        if Path(temporary).stat().st_size == 0:
            raise OSError("empty PDF")
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(temporary, 0o666 & ~mask)  # mkstemp files are private; a report is not
        os.replace(temporary, path)
    except OSError:
        raise ReportWriteError("the report could not be written") from None
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def suggested_name(company: str, now: datetime | None = None) -> str:
    """Return a file name such as 'relatorio-cafe-aurora-2026-11-05.pdf'."""
    import re
    import unicodedata

    plain = unicodedata.normalize("NFKD", company).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "empresa"
    stamp = (now or datetime.now()).date().isoformat()
    return f"{t('report.file_prefix')}-{slug}-{stamp}.pdf"

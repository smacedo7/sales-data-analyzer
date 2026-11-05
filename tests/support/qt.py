"""Headless Qt for interface tests: one offscreen QApplication and a scripted prompter."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections import deque  # noqa: E402
from pathlib import Path  # noqa: E402
import unittest  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from sales_data_analyzer.application import SalesSession  # noqa: E402


def application() -> QApplication:
    """Return the shared offscreen application, creating it once."""
    return QApplication.instance() or QApplication(["tests"])


class ScriptedPrompter:
    """Prompter that answers from queues and records every notice.

    Each queue holds the answers to give, in order; asking with an empty queue
    fails the test, so an unexpected question is never silently answered.
    """

    def __init__(self) -> None:
        self.notices: list[str] = []
        self.warnings: list[str] = []
        self.questions: list[str] = []
        self.answers: dict[str, deque] = {
            key: deque()
            for key in ("confirm", "open_csv", "choose_folder", "company", "product", "sale")
        }

    def queue(self, kind: str, *answers: object) -> "ScriptedPrompter":
        """Add answers for one kind of question and return self."""
        self.answers[kind].extend(answers)
        return self

    def _next(self, kind: str) -> object:
        if not self.answers[kind]:
            raise AssertionError(f"unexpected {kind} question")
        return self.answers[kind].popleft()

    def inform(self, text: str) -> None:
        self.notices.append(text)

    def warn(self, text: str) -> None:
        self.warnings.append(text)

    def confirm(self, question: str) -> bool:
        self.questions.append(question)
        return bool(self._next("confirm"))

    def open_csv(self) -> Path | None:
        return self._next("open_csv")

    def choose_folder(self) -> Path | None:
        return self._next("choose_folder")

    def company_form(self, name: str = "", sector: str = ""):
        self.questions.append(f"company form ({name})")
        return self._next("company")

    def product_form(self, product=None):
        self.questions.append(f"product form ({product.id if product else ''})")
        return self._next("product")

    def sale_form(self, products):
        self.questions.append("sale form")
        return self._next("sale")


class WindowTestCase(unittest.TestCase):
    """Builds MainWindow objects over sessions with a scripted prompter."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def window(self, session: SalesSession | None = None, pages=None):
        """Return a window over session (a new in-memory one by default)."""
        from sales_data_analyzer.gui.main_window import MainWindow

        self.prompter = ScriptedPrompter()
        window = MainWindow(session or SalesSession(), self.prompter, pages=pages)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def assertNoPendingAnswers(self) -> None:
        """Fail when a queued answer was never used."""
        pending = {key: list(value) for key, value in self.prompter.answers.items() if value}
        self.assertEqual(pending, {})


class StoredWindowTestCase(WindowTestCase):
    """A window over a session loaded from a temporary database file."""

    def setUp(self) -> None:
        from support.databases import temporary_database

        context = temporary_database()
        self.path = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def open_window(self, pages=None):
        """Open the database like one program run and return the window."""
        from sales_data_analyzer.persistence import SQLiteSalesRepository

        repository = SQLiteSalesRepository.open(self.path)
        self.addCleanup(repository.close)
        return self.window(SalesSession.open(repository), pages=pages)

    def reopen(self) -> SalesSession:
        """Return the stored data as a new run would load it."""
        from sales_data_analyzer.persistence import SQLiteSalesRepository

        repository = SQLiteSalesRepository.open(self.path)
        self.addCleanup(repository.close)
        return SalesSession.open(repository)

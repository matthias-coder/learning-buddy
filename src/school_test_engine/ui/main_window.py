from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from .pages.events import EventsPage
from .pages.gaps import GapsPage
from .pages.grades import GradesPage
from .pages.history import HistoryPage
from .pages.import_wizard import ImportPage
from .pages.library import LibraryPage
from .pages.menu import MenuPage
from .pages.profile_manager import ProfileManagerPage
from .pages.profile_picker import ProfilePickerPage
from .pages.prompt_builder import PromptBuilderPage
from .pages.results import ResultsPage
from .pages.review import ReviewPage
from .pages.runner import RunnerPage


class MainWindow(QMainWindow):
    user_changed = Signal(int)

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.active_user_id: int | None = None
        self.setWindowTitle("Übungstests")

        qss_path = Path(__file__).parent / "style.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.profile_picker_page = ProfilePickerPage(self, conn)
        self.profile_manager_page = ProfileManagerPage(self, conn)
        self.menu_page = MenuPage(self)
        self.library_page = LibraryPage(self, conn)
        self.runner_page = RunnerPage(self, conn)
        self.review_page = ReviewPage(self)
        self.results_page = ResultsPage(self)
        self.import_page = ImportPage(self, conn)
        self.gaps_page = GapsPage(self, conn)
        self.history_page = HistoryPage(self, conn)
        self.events_page = EventsPage(self, conn)
        self.grades_page = GradesPage(self, conn)
        self.prompt_builder_page = PromptBuilderPage(self, conn)

        for page in (
            self.profile_picker_page,
            self.profile_manager_page,
            self.menu_page,
            self.library_page,
            self.runner_page,
            self.review_page,
            self.results_page,
            self.import_page,
            self.gaps_page,
            self.history_page,
            self.events_page,
            self.grades_page,
            self.prompt_builder_page,
        ):
            self.stack.addWidget(page)

        self._return_to_history = False

    # ------------------------------------------------------------------
    # User switching
    # ------------------------------------------------------------------

    def set_active_user(self, user_id: int) -> None:
        self.active_user_id = user_id
        self.user_changed.emit(user_id)
        self.show_menu()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_profile_picker(self) -> None:
        self.profile_picker_page.reload()
        self.stack.setCurrentWidget(self.profile_picker_page)

    def show_profile_manager(self, return_to: str = "picker") -> None:
        self.profile_manager_page.show_for(return_to)
        self.stack.setCurrentWidget(self.profile_manager_page)

    def show_menu(self) -> None:
        self._return_to_history = False
        self.menu_page.reload()
        self.stack.setCurrentWidget(self.menu_page)

    def show_library(self) -> None:
        self.library_page.reload()
        self.stack.setCurrentWidget(self.library_page)

    def show_import(self) -> None:
        self.stack.setCurrentWidget(self.import_page)

    def show_gaps(self) -> None:
        self.gaps_page.reload()
        self.stack.setCurrentWidget(self.gaps_page)

    def show_history(self) -> None:
        self.history_page.reload()
        self.stack.setCurrentWidget(self.history_page)

    def show_events(self) -> None:
        self.events_page.reload()
        self.stack.setCurrentWidget(self.events_page)

    def show_grades(self) -> None:
        self.grades_page.reload()
        self.stack.setCurrentWidget(self.grades_page)

    def show_prompt_builder(self, subject: str | None = None, topics: list[str] | None = None) -> None:
        self.prompt_builder_page.show_for(subject, topics)
        self.stack.setCurrentWidget(self.prompt_builder_page)

    def start_test(self, test_id: int) -> None:
        self._return_to_history = False
        self.runner_page.start_new(test_id)
        self.stack.setCurrentWidget(self.runner_page)

    def resume_attempt(self, attempt_id: int) -> None:
        self._return_to_history = False
        self.runner_page.resume(attempt_id)
        self.stack.setCurrentWidget(self.runner_page)

    def show_review(self, attempt_id: int) -> None:
        self.review_page.show_for_attempt()
        self.stack.setCurrentWidget(self.review_page)

    def back_to_runner(self) -> None:
        self.stack.setCurrentWidget(self.runner_page)

    def jump_to_question(self, index: int) -> None:
        self.runner_page.jump_to_question(index)
        self.stack.setCurrentWidget(self.runner_page)

    def show_results(self, attempt_id: int) -> None:
        self._return_to_history = (
            self.stack.currentWidget() is self.history_page
        )
        self.results_page.show_attempt(self.conn, attempt_id)
        self.stack.setCurrentWidget(self.results_page)

    def return_from_results(self) -> None:
        if self._return_to_history:
            self.show_history()
        else:
            self.show_menu()

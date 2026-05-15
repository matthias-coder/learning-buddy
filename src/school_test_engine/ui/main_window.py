from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from ..daily import builder as daily_builder
from ..daily import finalize as daily_finalize
from ..storage import attempts_repo, daily_sessions_repo
from .pages.assessment_edit import AssessmentEditPage
from .pages.event_edit import EventEditPage
from .pages.events import EventsPage
from .pages.gaps import GapsPage
from .pages.grades import GradesPage
from .pages.history import HistoryPage
from .pages.import_wizard import ImportPage
from .pages.library import LibraryPage
from .pages.menu import MenuPage
from .pages.profile_edit import ProfileEditPage
from .pages.profile_manager import ProfileManagerPage
from .pages.profile_picker import ProfilePickerPage
from .pages.prompt_builder import PromptBuilderPage
from .pages.results import ResultsPage
from .pages.review import ReviewPage
from .pages.runner import RunnerPage


class MainWindow(QMainWindow):
    user_changed = Signal(int)
    events_synced = Signal()    # NEW — emitted after sync mutates scheduled_events

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.active_user_id: int | None = None
        self.setWindowTitle("Learning Buddy")

        qss_path = Path(__file__).parent / "style.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.profile_picker_page = ProfilePickerPage(self, conn)
        self.profile_manager_page = ProfileManagerPage(self, conn)
        self.profile_edit_page = ProfileEditPage(self, conn)
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
        self.event_edit_page = EventEditPage(self, conn)
        self.assessment_edit_page = AssessmentEditPage(self, conn)

        for page in (
            self.profile_picker_page,
            self.profile_manager_page,
            self.profile_edit_page,
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
            self.event_edit_page,
            self.assessment_edit_page,
        ):
            self.stack.addWidget(page)

        self._return_to_history = False
        self._bg_sync_thread = None
        self._bg_sync_worker = None

    # ------------------------------------------------------------------
    # User switching
    # ------------------------------------------------------------------

    def set_active_user(self, user_id: int) -> None:
        self.active_user_id = user_id
        self.user_changed.emit(user_id)
        self.show_menu()
        self._maybe_trigger_background_sync(user_id)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_profile_picker(self) -> None:
        self.profile_picker_page.reload()
        self.stack.setCurrentWidget(self.profile_picker_page)

    def show_profile_manager(self, return_to: str = "picker") -> None:
        self.profile_manager_page.show_for(return_to)
        self.stack.setCurrentWidget(self.profile_manager_page)

    def show_profile_edit(self, user_id: int | None = None, return_to: str = "picker") -> None:
        self.profile_edit_page.show_for(user_id, return_to)
        self.stack.setCurrentWidget(self.profile_edit_page)

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

    def show_event_edit(self, event_id: int | None = None, return_to: str = "events") -> None:
        self.event_edit_page.show_for(event_id, return_to)
        self.stack.setCurrentWidget(self.event_edit_page)

    def show_assessment_edit(
        self,
        assessment_id: int | None = None,
        return_to: str = "grades",
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        self.assessment_edit_page.show_for(
            assessment_id, return_to, prefill_subject, prefill_event_id,
        )
        self.stack.setCurrentWidget(self.assessment_edit_page)

    def start_test(self, test_id: int) -> None:
        self._return_to_history = False
        self.runner_page.start_new(test_id)
        self.stack.setCurrentWidget(self.runner_page)

    def start_daily_five(self) -> None:
        """Start (or resume) today's Daily-5 session."""
        uid = self.active_user_id
        if uid is None:
            return
        today = date.today()
        today_iso = today.isoformat()

        existing = daily_sessions_repo.get_for_today(self.conn, uid, today_iso)
        if existing is not None:
            if existing["completed_at"] is not None:
                return  # already done today
            if existing["attempt_id"] is not None:
                # Resume in-progress session
                self.resume_attempt(existing["attempt_id"])
                return

        # Build fresh test + start attempt + record session
        test_id = daily_builder.build_daily_test(self.conn, uid, today)
        if test_id is None:
            return  # pool insufficient (should not happen if card was clickable)

        points_total = self.conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS pts FROM questions WHERE test_id = ?",
            (test_id,),
        ).fetchone()["pts"]
        attempt_id = attempts_repo.start_attempt(self.conn, test_id, int(points_total), uid)
        daily_sessions_repo.start_session(
            self.conn, uid, today_iso,
            test_id=test_id,
            attempt_id=attempt_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.runner_page.resume(attempt_id)
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
        daily_finalize.finalize_if_daily(self.conn, attempt_id)
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

    # ------------------------------------------------------------------
    # Background iCal sync (Phase 15)
    # ------------------------------------------------------------------

    def _maybe_trigger_background_sync(self, user_id: int) -> None:
        from datetime import timedelta
        from ..config import db_path
        from ..storage import users_repo
        from .sync_worker import SyncWorker
        from PySide6.QtCore import QThread

        if self._bg_sync_thread is not None:
            return
        # Cross-path guard: don't auto-sync if EventsPage manual sync is running
        events_thread = getattr(self.events_page, "_sync_thread", None)
        if events_thread is not None:
            return
        row = users_repo.get_user(self.conn, user_id)
        if not row or not row["ical_feed_url"]:
            return
        last = row["ical_last_sync_at"]
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if datetime.now(timezone.utc) - last_dt < timedelta(hours=24):
                    return
            except ValueError:
                pass  # malformed timestamp → resync

        self._bg_sync_thread = QThread()
        self._bg_sync_worker = SyncWorker(db_path(), user_id)
        self._bg_sync_worker.moveToThread(self._bg_sync_thread)
        self._bg_sync_thread.started.connect(self._bg_sync_worker.run)
        self._bg_sync_worker.finished.connect(self._on_bg_sync_done)
        self._bg_sync_worker.finished.connect(self._bg_sync_thread.quit)
        self._bg_sync_thread.finished.connect(self._bg_sync_thread.deleteLater)
        self._bg_sync_thread.start()

    def _on_bg_sync_done(self, result) -> None:
        worker_user_id = self._bg_sync_worker.user_id if self._bg_sync_worker else None
        self._bg_sync_thread = None
        self._bg_sync_worker = None
        if worker_user_id != self.active_user_id:
            return    # user switched; DB is fine, but UI update would target wrong profile
        if not result.error and (result.added or result.updated or result.deleted):
            self.events_synced.emit()

    def closeEvent(self, event):
        if self._bg_sync_thread is not None:
            self._bg_sync_thread.quit()
            self._bg_sync_thread.wait(2000)
        super().closeEvent(event)

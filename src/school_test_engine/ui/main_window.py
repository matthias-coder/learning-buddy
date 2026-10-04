from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from ..daily import builder as daily_builder
from ..daily import finalize as daily_finalize
from ..error_book import builder as error_book_builder
from ..storage import attempts_repo, daily_sessions_repo
from .pages.assessment_edit import AssessmentEditPage
from .pages.error_book import ErrorBookPage
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
from .pages.school_calendar import SchoolCalendarPage
from .pages.test_create import TestCreatePage
from .widgets.global_header import GlobalHeader
from ..storage import users_repo
from ._layouts import row_get


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
            from ..resources import assets_dir as _assets_dir
            assets_dir = _assets_dir()
            qss = qss_path.read_text(encoding="utf-8").replace(
                "{ASSETS}", assets_dir.as_posix()
            )
            self.setStyleSheet(qss)

        # Global header (logo menu + profile chip) above the page stack.
        # Visibility is bound to active_user_id: hidden on the Profile-Picker.
        self.header = GlobalHeader(self)
        self.header.setVisible(False)
        self.stack = QStackedWidget()

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.header)
        v.addWidget(self.stack, 1)
        self.setCentralWidget(central)

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
        self.error_book_page = ErrorBookPage(self, conn)
        self.school_calendar_page = SchoolCalendarPage(self, conn)
        self.prompt_builder_page = PromptBuilderPage(self, conn)
        self.event_edit_page = EventEditPage(self, conn)
        self.assessment_edit_page = AssessmentEditPage(self, conn)
        self.test_create_page = TestCreatePage(self)

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
            self.error_book_page,
            self.school_calendar_page,
            self.prompt_builder_page,
            self.event_edit_page,
            self.assessment_edit_page,
            self.test_create_page,
        ):
            self.stack.addWidget(page)

        self.user_changed.connect(lambda _uid: self.school_calendar_page.reload())
        self.user_changed.connect(self._refresh_header_user)
        self.events_synced.connect(self.school_calendar_page.reload)

        self._return_to_history = False
        self._history: list[tuple[str, dict]] = []
        self._current: tuple[str, dict] | None = None
        self._bg_sync_thread = None
        self._bg_sync_worker = None
        self._dispatch: dict[str, Callable[..., None]] = {
            "profile_picker": self._render_profile_picker,
            "menu": self._render_menu,
            "library": self._render_library,
            "import": self._render_import,
            "gaps": self._render_gaps,
            "history": self._render_history,
            "events": self._render_events,
            "grades": self._render_grades,
            "error_book": self._render_error_book,
            "school_calendar": self._render_school_calendar,
            "prompt_builder": self._render_prompt_builder,
            "test_create": self._render_test_create,
            "event_edit": self._render_event_edit,
            "assessment_edit": self._render_assessment_edit,
            "profile_manager": self._render_profile_manager,
            "profile_edit": self._render_profile_edit,
            "results": self._render_results,
            "review": self._render_review,
            "runner": self._render_runner,
        }

        self._esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._esc_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._esc_shortcut.activated.connect(self._on_esc_pressed)

    # ------------------------------------------------------------------
    # User switching
    # ------------------------------------------------------------------

    def set_active_user(self, user_id: int) -> None:
        self.active_user_id = user_id
        self._refresh_header_user(user_id)
        self.header.setVisible(True)
        self.user_changed.emit(user_id)
        self.show_menu()
        self._maybe_trigger_background_sync(user_id)

    def _refresh_header_user(self, user_id: int) -> None:
        """Show name/photo of the given profile in the header chip (also after
        the active profile was edited)."""
        user = users_repo.get_user(self.conn, user_id)
        if user is not None:
            self.header.set_user(user["name"], row_get(user, "avatar_image"))

    # ------------------------------------------------------------------
    # Navigation dispatcher (Phase 18)
    # ------------------------------------------------------------------

    def _navigate(self, target: str, **kwargs) -> None:
        """Central navigation entry point. Pushes current head onto the
        history stack and renders the target page.

        Special rules:
        - target == "menu":   clears stack (root reset)
        - target == "runner": never pushed onto stack (mid-test must use
                              Pause-Button, not Back)
        - duplicate target:   replaces head rather than pushing (dedup)
        - leaving the runner: pushed as action="raw" so Back resumes the live
                              test instead of starting a new attempt
        - target == "results": the finished test (runner/review) is dropped
                              from the stack — Back must never re-enter it
        """
        if target == "menu":
            self._history.clear()
        elif target == "runner":
            pass
        elif self._current is not None and self._current[0] != target:
            if not self._history or self._history[-1][0] != self._current[0]:
                head = self._current
                if head[0] == "runner":
                    head = ("runner", {"action": "raw"})
                self._history.append(head)
        if target == "results":
            self._history = [
                h for h in self._history if h[0] not in ("runner", "review")
            ]
        # Resolve and render
        renderer = self._dispatch.get(target)
        if renderer is None:
            raise ValueError(f"Unknown navigation target: {target!r}")
        renderer(**kwargs)
        self._current = (target, dict(kwargs))
        self.header.back_button.setVisible(len(self._history) > 0)

    def _navigate_back(self) -> None:
        if not self._history:
            return
        target, kwargs = self._history.pop()
        renderer = self._dispatch.get(target)
        if renderer is None:
            return
        renderer(**kwargs)
        self._current = (target, dict(kwargs))
        self.header.back_button.setVisible(len(self._history) > 0)

    def _on_esc_pressed(self) -> None:
        # Guard: no-op if a modal dialog is open OR back-button is hidden.
        if QApplication.activeModalWidget() is not None:
            return
        # History, not header visibility: before login the header is hidden,
        # but the profile pages still need Esc.
        if not self._history:
            return
        self._navigate_back()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_profile_picker(self) -> None:
        # Profile picker is the pre-login root — clears the stack.
        self._history.clear()
        self._render_profile_picker()
        self._current = ("profile_picker", {})

    def _render_profile_picker(self) -> None:
        self.active_user_id = None
        self.header.setVisible(False)
        self.profile_picker_page.reload()
        self.stack.setCurrentWidget(self.profile_picker_page)

    def show_profile_manager(self, return_to: str = "picker") -> None:
        self._navigate("profile_manager", return_to=return_to)

    def _render_profile_manager(self, return_to: str = "picker") -> None:
        self.header.set_page_actions([])
        self.profile_manager_page.show_for(return_to)
        self.stack.setCurrentWidget(self.profile_manager_page)

    def show_profile_edit(self, user_id: int | None = None, return_to: str = "picker") -> None:
        self._navigate("profile_edit", user_id=user_id, return_to=return_to)

    def _render_profile_edit(self, user_id: int | None = None, return_to: str = "picker") -> None:
        self.header.set_page_actions([])
        self.profile_edit_page.show_for(user_id, return_to)
        self.stack.setCurrentWidget(self.profile_edit_page)

    def show_menu(self) -> None:
        self._return_to_history = False
        self._navigate("menu")

    def _render_menu(self) -> None:
        self.header.set_page_actions([])
        self.menu_page.reload()
        self.stack.setCurrentWidget(self.menu_page)

    def show_library(self) -> None:
        self._navigate("library")

    def _render_library(self) -> None:
        self.header.set_page_actions([])
        self.library_page.reload()
        self.stack.setCurrentWidget(self.library_page)

    def show_import(self) -> None:
        self._navigate("import")

    def _render_import(self) -> None:
        self.header.set_page_actions([])
        self.stack.setCurrentWidget(self.import_page)

    def show_gaps(self) -> None:
        self._navigate("gaps")

    def _render_gaps(self) -> None:
        self.header.set_page_actions([])
        self.gaps_page.reload()
        self.stack.setCurrentWidget(self.gaps_page)

    def show_history(self) -> None:
        self._navigate("history")

    def _render_history(self) -> None:
        csv_btn = QPushButton("CSV exportieren")
        csv_btn.setObjectName("text")
        csv_btn.clicked.connect(self.history_page.export_csv)
        self.header.set_page_actions([csv_btn])
        self.history_page.reload()
        self.stack.setCurrentWidget(self.history_page)

    def show_events(self) -> None:
        self._navigate("events")

    def _render_events(self) -> None:
        add_btn = QPushButton("Termin hinzufügen")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.events_page.add_event)
        self.header.set_page_actions([add_btn])
        self.events_page.reload()
        self.stack.setCurrentWidget(self.events_page)

    def show_grades(self) -> None:
        self._navigate("grades")

    def _render_grades(self) -> None:
        pdf_btn = QPushButton("Als PDF")
        pdf_btn.setObjectName("text")
        pdf_btn.clicked.connect(self.grades_page.export_pdf)
        add_btn = QPushButton("Note hinzufügen")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.grades_page.add_assessment)
        self.header.set_page_actions([pdf_btn, add_btn])
        self.grades_page.reload()
        self.stack.setCurrentWidget(self.grades_page)

    def show_error_book(self) -> None:
        self._navigate("error_book")

    def _render_error_book(self) -> None:
        uid = self.active_user_id
        if uid is None:
            return
        self._error_book_ueben_btn = QPushButton("Üben")
        self._error_book_ueben_btn.setObjectName("primary")
        self._error_book_ueben_btn.clicked.connect(self.error_book_page.trigger_practice)
        self.header.set_page_actions([self._error_book_ueben_btn])
        self.error_book_page.reload()
        self._refresh_error_book_action()
        self.stack.setCurrentWidget(self.error_book_page)

    def _refresh_error_book_action(self) -> None:
        """Reads `practice_button_count()` und aktualisiert den Üben-Button im Header.
        Wird von der ErrorBookPage nach Subject-Wechsel gerufen."""
        btn = getattr(self, "_error_book_ueben_btn", None)
        if btn is None:
            return
        n = self.error_book_page.practice_button_count()
        btn.setText(f"Üben ({n})" if n > 0 else "Üben")
        btn.setEnabled(n > 0)

    def show_school_calendar(self, initial_tab: str | None = None) -> None:
        self._navigate("school_calendar", initial_tab=initial_tab)

    def _render_school_calendar(self, initial_tab: str | None = None) -> None:
        uid = self.active_user_id
        if uid is None:
            return
        self.header.set_page_actions([])
        self.school_calendar_page.show_for(initial_tab=initial_tab)
        self.stack.setCurrentWidget(self.school_calendar_page)

    def start_error_book_practice(self, subject: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        uid = self.active_user_id
        if uid is None:
            return
        test_id = error_book_builder.build_practice_test(self.conn, uid, subject)
        if test_id is None:
            QMessageBox.information(
                self, "Fehlerheft",
                f"In {subject} gerade keine offenen Fehler.",
            )
            return
        # Check Resume-Pfad: gibt's einen offenen Attempt?
        existing_attempt = attempts_repo.find_incomplete_attempt(self.conn, uid, test_id=test_id)
        if existing_attempt is not None:
            self.resume_attempt(existing_attempt["id"])
            return
        # Fresh attempt
        points_total = self.conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS pts FROM questions WHERE test_id = ?",
            (test_id,),
        ).fetchone()["pts"]
        attempt_id = attempts_repo.start_attempt(self.conn, test_id, int(points_total), uid)
        self._return_to_history = False
        self.runner_page.resume(attempt_id)
        self._navigate("runner", action="raw")

    def show_prompt_builder(self, subject: str | None = None, topics: list[str] | None = None) -> None:
        self._navigate("prompt_builder", subject=subject, topics=topics)

    def _render_prompt_builder(self, subject: str | None = None, topics: list[str] | None = None) -> None:
        self.header.set_page_actions([])
        self.prompt_builder_page.show_for(subject, topics)
        self.stack.setCurrentWidget(self.prompt_builder_page)

    def show_test_create(self) -> None:
        self._navigate("test_create")

    def _render_test_create(self) -> None:
        self.header.set_page_actions([])
        self.stack.setCurrentWidget(self.test_create_page)

    def show_event_edit(self, event_id: int | None = None, return_to: str = "events") -> None:
        # return_to is preserved for API compatibility; the history stack supersedes it.
        self._navigate("event_edit", event_id=event_id)

    def _render_event_edit(self, event_id: int | None = None) -> None:
        self.header.set_page_actions([])
        self.event_edit_page.show_for(event_id, "events")
        self.stack.setCurrentWidget(self.event_edit_page)

    def show_assessment_edit(
        self,
        assessment_id: int | None = None,
        return_to: str = "grades",
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        # return_to is preserved for API compatibility; the history stack
        # supersedes it (see Phase 18 design doc, Feature 1).
        self._navigate(
            "assessment_edit",
            assessment_id=assessment_id,
            prefill_subject=prefill_subject,
            prefill_event_id=prefill_event_id,
        )

    def _render_assessment_edit(
        self,
        assessment_id: int | None = None,
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        self.header.set_page_actions([])
        self.assessment_edit_page.show_for(
            assessment_id, "grades", prefill_subject, prefill_event_id,
        )
        self.stack.setCurrentWidget(self.assessment_edit_page)

    def start_test(self, test_id: int) -> None:
        self._return_to_history = False
        self._navigate("runner", action="start", test_id=test_id)

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
        self._navigate("runner", action="raw")

    def resume_attempt(self, attempt_id: int) -> None:
        self._return_to_history = False
        self._navigate("runner", action="resume", attempt_id=attempt_id)

    def show_review(self, attempt_id: int) -> None:
        self._navigate("review", attempt_id=attempt_id)

    def _render_review(self, attempt_id: int) -> None:
        # attempt_id kept for dispatch-table symmetry; show_for_attempt() reads
        # live runner state via self.window.runner_page.get_status_overview().
        self.review_page.show_for_attempt()
        self.stack.setCurrentWidget(self.review_page)

    def back_to_runner(self) -> None:
        self._navigate("runner", action="raw")

    def jump_to_question(self, index: int) -> None:
        self.runner_page.jump_to_question(index)
        self._navigate("runner", action="raw")

    def _render_runner(self, action: str = "raw", **kwargs) -> None:
        if action == "start":
            self.runner_page.start_new(kwargs["test_id"])
        elif action == "resume":
            self.runner_page.resume(kwargs["attempt_id"])
        # "raw" → caller already mutated runner_page state
        self.stack.setCurrentWidget(self.runner_page)

    def show_results(self, attempt_id: int) -> None:
        daily_finalize.finalize_if_daily(self.conn, attempt_id)
        self._return_to_history = (
            self.stack.currentWidget() is self.history_page
        )
        self._navigate("results", attempt_id=attempt_id)

    def _render_results(self, attempt_id: int) -> None:
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
        self._bg_sync_thread.finished.connect(self._clear_bg_sync_refs)   # NEW
        self._bg_sync_thread.start()

    def _clear_bg_sync_refs(self) -> None:
        self._bg_sync_thread = None
        self._bg_sync_worker = None

    def _on_bg_sync_done(self, result) -> None:
        worker_user_id = self._bg_sync_worker.user_id if self._bg_sync_worker else None
        if worker_user_id != self.active_user_id:
            return    # user switched; DB is fine, but UI update would target wrong profile
        if not result.error and (
            result.added or result.updated or result.deleted
            or result.cal_added or result.cal_updated or result.cal_deleted
        ):
            self.events_synced.emit()

    def closeEvent(self, event):
        # HTTP timeout in fetcher is 10s; wait long enough for any in-flight
        # sync to complete naturally before Qt destroys the QThread.
        for thread in (
            self._bg_sync_thread,
            getattr(self.events_page, "_sync_thread", None),
        ):
            if thread is not None:
                thread.quit()
                thread.wait(12000)
        super().closeEvent(event)

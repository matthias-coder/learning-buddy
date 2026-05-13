import pytest
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from school_test_engine.storage import connect, run_migrations, users_repo, prompt_drafts_repo


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Clemens", "🧒")


@pytest.fixture
def page(app, conn, uid):
    from school_test_engine.ui.pages.prompt_builder import PromptBuilderPage

    class FakeWindow:
        def __init__(self):
            self.active_user_id = uid
            self.conn = conn
        def show_menu(self): pass
        def show_profile_manager(self, where): pass

    return PromptBuilderPage(FakeWindow(), conn)


def test_subject_switch_saves_under_old_subject(page, conn, uid):
    page.show_for(subject="Bio", topics=["Zellen", "DNA"])
    # Simulate user activating Mathe from the dropdown (not via setCurrentText)
    page._on_subject_changed("Mathe")

    bio = prompt_drafts_repo.get(conn, uid, "Bio")
    assert bio is not None, "Bio draft must persist after subject switch"
    assert "Zellen" in (bio["last_topic"] or "")
    assert "DNA" in (bio["last_topic"] or "")


def test_subject_switch_loads_new_subjects_draft(page, conn, uid):
    # Seed a Mathe draft
    prompt_drafts_repo.upsert(
        conn, uid, "Mathe",
        last_topic="Funktionen", last_count=12, last_dist="auto",
    )
    page.show_for(subject="Bio", topics=["Zellen"])
    page._on_subject_changed("Mathe")

    assert page.subject_combo.currentText() == "Mathe"
    assert "Funktionen" in page.topics_edit.toPlainText()
    assert page.count_spin.value() == 12

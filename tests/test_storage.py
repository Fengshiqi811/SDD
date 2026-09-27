"""shared/storage.py 单元测试。"""

from datetime import date, datetime
from pathlib import Path

from shared.storage import ReportStorage


def test_create_db_and_save_report(tmp_path: Path):
    db_path = tmp_path / "reports.db"
    storage = ReportStorage(db_path)

    assert db_path.exists()

    report_id = storage.save_report(
        report_date=date(2026, 9, 27),
        team_name="研发团队",
        markdown="# 日报\n今日完成任务",
        html="<h1>日报</h1>",
        generated_at=datetime(2026, 9, 27, 18, 0, 0),
    )

    assert isinstance(report_id, int)
    assert report_id > 0


def test_get_report_by_date_and_team(tmp_path: Path):
    storage = ReportStorage(tmp_path / "reports.db")
    storage.save_report(
        report_date=date(2026, 9, 27),
        team_name="研发团队",
        markdown="md-content",
        html="html-content",
        generated_at=datetime(2026, 9, 27, 18, 0, 0),
    )

    record = storage.get_report(date(2026, 9, 27), "研发团队")

    assert record is not None
    assert record.report_date == date(2026, 9, 27)
    assert record.team_name == "研发团队"
    assert record.markdown == "md-content"
    assert record.html == "html-content"
    assert record.generated_at == datetime(2026, 9, 27, 18, 0, 0)


def test_get_report_returns_none_when_missing(tmp_path: Path):
    storage = ReportStorage(tmp_path / "reports.db")
    assert storage.get_report(date(2026, 1, 1), "未知团队") is None


def test_upsert_and_list_reports(tmp_path: Path):
    storage = ReportStorage(tmp_path / "reports.db")
    storage.save_report(
        report_date=date(2026, 9, 26),
        team_name="研发团队",
        markdown="day1",
        html="<p>day1</p>",
    )
    storage.save_report(
        report_date=date(2026, 9, 27),
        team_name="研发团队",
        markdown="day2",
        html="<p>day2</p>",
    )
    storage.save_report(
        report_date=date(2026, 9, 27),
        team_name="研发团队",
        markdown="day2-updated",
        html="<p>day2-updated</p>",
    )

    reports = storage.list_reports()

    assert len(reports) == 2
    assert reports[0].report_date == date(2026, 9, 27)
    assert reports[0].markdown == "day2-updated"
    assert reports[1].report_date == date(2026, 9, 26)

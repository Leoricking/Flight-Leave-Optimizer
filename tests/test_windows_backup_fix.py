from pathlib import Path
from history import PriceHistory
from history_io import sqlite_backup_bytes, validate_backup, restore_backup


def test_backup_without_creating_temp_files(tmp_path, monkeypatch):
    db=PriceHistory(tmp_path/'live.sqlite3')
    import tempfile
    def forbidden(*args,**kwargs):
        raise AssertionError('Temp folders must not be used for SQLite backup')
    monkeypatch.setattr(tempfile,'TemporaryDirectory',forbidden)
    backup=sqlite_backup_bytes(db)
    assert backup.startswith(b'SQLite format 3\x00')
    assert validate_backup(backup)['quotes']==0
    assert restore_backup(db,backup)[0]['quotes']==0


def test_backup_preserves_live_db(tmp_path):
    db=PriceHistory(tmp_path/'live.sqlite3')
    db.save_offers('TPE','CTS',[{'departure_date':'2026-10-31','return_date':'2026-11-04','price_twd':8098,'airline':'Scoot','source':'SerpApi','mode':'SEARCH_RESULT'}])
    backup=sqlite_backup_bytes(db)
    assert validate_backup(backup)['quotes']==1
    assert len(db.quotes())==1

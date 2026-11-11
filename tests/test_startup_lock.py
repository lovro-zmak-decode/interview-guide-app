"""The start-up lock: one process at a time prepares the database."""

from __future__ import annotations

import threading

import pytest

import app as app_module
from interview_app.models import db
from interview_app.startup_lock import startup_lock


def test_without_postgresql_the_lock_does_nothing():
    with app_module.app.app_context():
        if db.engine.dialect.name == "postgresql":
            pytest.skip("covered by the PostgreSQL test below")
        ran = []
        with startup_lock(db.engine):
            ran.append(True)
        assert ran == [True]


def test_second_process_waits_until_the_first_has_finished():
    with app_module.app.app_context():
        engine = db.engine
    if engine.dialect.name != "postgresql":
        pytest.skip("the advisory lock only exists on PostgreSQL")

    first_has_lock = threading.Event()
    let_first_finish = threading.Event()
    second_has_lock = threading.Event()

    def first():
        with startup_lock(engine):
            first_has_lock.set()
            let_first_finish.wait(timeout=10)

    def second():
        with startup_lock(engine):
            second_has_lock.set()

    t1 = threading.Thread(target=first)
    t1.start()
    assert first_has_lock.wait(timeout=5)

    t2 = threading.Thread(target=second)
    t2.start()
    assert not second_has_lock.wait(timeout=0.5), "the second one got in while the first still held the lock"

    let_first_finish.set()
    assert second_has_lock.wait(timeout=5), "the second one never got in after the first finished"
    t1.join(timeout=5)
    t2.join(timeout=5)


def test_lock_is_released_when_the_work_inside_fails():
    with app_module.app.app_context():
        engine = db.engine
    with pytest.raises(RuntimeError):
        with startup_lock(engine):
            raise RuntimeError("set-up failed")

    entered = threading.Event()

    def again():
        with startup_lock(engine):
            entered.set()

    t = threading.Thread(target=again)
    t.start()
    assert entered.wait(timeout=5), "the lock was still held after a failure"
    t.join(timeout=5)

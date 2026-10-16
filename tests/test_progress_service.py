from backend.services.progress_service import ProgressReporter


def _collect(model="ctgan", **configure):
    events = []
    r = ProgressReporter(events.append, model_name=model)
    r.configure(**configure)
    return r, events


def test_no_callback_is_silent():
    r = ProgressReporter(None, model_name="ctgan")
    r.configure(has_llm=True)
    r.start("train")
    r.update("train", 0.5, message="x")
    r.complete("train")


def test_default_plan_skips_optional_floors():
    r, events = _collect()
    r.start("prepare")
    keys = [s["key"] for s in events[-1]["stages"]]
    assert "llm_text" not in keys and "validate" not in keys
    assert events[-1]["stage_total"] == 5


def test_optional_floors_added_when_configured():
    r, events = _collect(has_llm=True, has_validation=True)
    r.start("prepare")
    assert events[-1]["stage_total"] == 7
    assert [s["key"] for s in events[-1]["stages"]][-3:] == [
        "llm_text", "validate", "save",
    ]


def test_unplanned_stage_is_ignored():
    r, events = _collect()
    n = len(events)
    r.start("llm_text")
    r.update("llm_text", 0.5)
    r.complete("llm_text")
    assert len(events) == n


def test_percent_grows_and_never_reaches_100():
    r, events = _collect(has_llm=True, has_validation=True)
    for key in ["prepare", "rules", "train", "sample", "llm_text", "validate", "save"]:
        r.start(key)
        r.update(key, 1.0)
        r.complete(key)
    pct = [e["percent"] for e in events]
    assert pct == sorted(pct)
    assert pct[-1] == 99


def test_retry_never_moves_percent_backwards():
    r, events = _collect(has_validation=True)
    for key in ["prepare", "rules", "train", "sample", "validate"]:
        r.start(key); r.update(key, 1.0)
    high = events[-1]["percent"]
    r.set_attempt(2, 10)
    r.start("train")
    assert events[-1]["percent"] == high
    assert events[-1]["attempt"] == 2 and events[-1]["max_attempts"] == 10
    assert events[-1]["stage_index"] == 3  # lift goes back down


def test_epoch_updates_are_throttled_but_last_one_is_sent():
    r, events = _collect()
    r.start("train")
    n = len(events)
    for e in range(1, 101):
        r.update("train", e / 100, message=f"Epoch {e} of 100", epoch=e, epochs=100)
    assert len(events) - n < 100          # not one write per epoch
    assert events[-1]["epoch"] == 100     # but the final one always lands


def test_train_label_names_the_model():
    r, events = _collect(model="tvae")
    r.start("train")
    assert events[-1]["stage_label"] == "Training TVAE"


def test_callback_errors_never_break_generation():
    def boom(_):
        raise RuntimeError("redis down")
    r = ProgressReporter(boom, model_name="ctgan")
    r.configure()
    r.start("prepare")
    r.update("prepare", 1.0)
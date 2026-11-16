"""Scoring maths for the speech study.

Every transcript below is a hand-written unit-test fixture, not a recording of
any participant. No audio is decoded and no network request is made; the one
audio path exercised here stops before transcription.
"""

import asyncio
import json

import pytest

from scripts.score_speech import (
    LANGUAGES,
    PRISTINE_TEMPLATE,
    build_report,
    build_template,
    fill_hypotheses,
    render_markdown,
    resolve_endpoint,
    score_clip,
    score_rows,
)


def sheet_row(
    clip_id="c1",
    speaker="participant-1",
    condition="clean",
    language="en-HK",
    reference="I built a test harness",
    hypothesis="I built a harness",
    **extra,
):
    return {
        "id": clip_id,
        "speaker_id": speaker,
        "condition": condition,
        "language": language,
        "reference": reference,
        "hypothesis": hypothesis,
        **extra,
    }


def test_english_wer_uses_word_tokens():
    scored = score_clip(sheet_row())
    assert scored["metric"] == "WER"
    assert scored["reference_units"] == 5
    assert scored["edits"] == 1
    assert scored["error_rate"] == pytest.approx(0.2)


def test_chinese_cer_uses_character_tokens_and_drops_punctuation():
    scored = score_clip(
        sheet_row(
            language="zh-HK",
            reference="我 做，測試。",
            hypothesis="我做測試",
        )
    )
    assert scored["metric"] == "CER"
    assert scored["reference_units"] == 4
    assert scored["error_rate"] == 0.0

    scored = score_clip(sheet_row(language="zh-HK", reference="我做測試", hypothesis="我做試"))
    assert scored["edits"] == 1
    assert scored["error_rate"] == pytest.approx(0.25)


def test_empty_reference_is_rejected_not_scored_as_zero():
    with pytest.raises(ValueError, match="reference transcript is empty"):
        score_clip(sheet_row(reference="   ", hypothesis="anything"))
    with pytest.raises(ValueError, match="silence"):
        score_clip(sheet_row(language="zh-HK", reference="。，", hypothesis="我"))


def test_unknown_labels_are_rejected():
    with pytest.raises(ValueError, match="language must be"):
        score_clip(sheet_row(language="yue"))
    with pytest.raises(ValueError, match="condition must be"):
        score_clip(sheet_row(condition="loud"))


def test_alias_columns_are_accepted():
    scored = score_clip(
        {
            "id": "c9",
            "speaker_id": "participant-2",
            "condition": "noisy",
            "language": "en-HK",
            "reference_text": "five words in this line",
            "hypothesis_text": "five words in this",
            "recording_path": "clips/c9.wav",
        }
    )
    assert scored["edits"] == 1
    assert scored["reference_units"] == 5


def test_group_rates_are_corpus_level_not_a_mean_of_clip_rates():
    rows = [
        sheet_row(
            clip_id="a",
            reference="one two three four",
            hypothesis="one two three",
        ),
        sheet_row(clip_id="b", reference="yes", hypothesis="no"),
    ]
    report = build_report(rows)
    block = report["overall"]["wer"]
    assert (block["edits"], block["reference_units"]) == (2, 5)
    assert block["rate"] == pytest.approx(0.4)
    mean_of_rates = (1 / 4 + 1 / 1) / 2
    assert block["rate"] != pytest.approx(mean_of_rates)


def test_aggregation_by_speaker_and_condition():
    rows = [
        sheet_row(clip_id="a1", speaker="participant-1", condition="clean"),
        sheet_row(clip_id="a2", speaker="participant-1", condition="noisy"),
        sheet_row(
            clip_id="b1",
            speaker="participant-2",
            condition="clean",
            language="zh-HK",
            reference="我做測試",
            hypothesis="我做試",
        ),
        sheet_row(clip_id="b2", speaker="participant-2", condition="noisy"),
    ]
    report = build_report(rows)
    assert report["overall"]["clips"] == 4
    assert set(report["by_speaker"]) == {"participant-1", "participant-2"}
    assert report["by_speaker"]["participant-1"]["wer"]["reference_units"] == 10
    assert report["by_speaker"]["participant-2"]["cer"]["reference_units"] == 4
    assert report["by_condition"]["clean"]["clips"] == 2
    assert report["by_condition"]["noisy"]["clips"] == 2
    assert report["by_condition"]["clean"]["cer"]["rate"] == pytest.approx(0.25)
    assert report["by_condition"]["noisy"]["cer"] is None


def test_correction_rate_counts_edited_and_failed_clips():
    rows = [
        sheet_row(clip_id="a", corrected=True),
        sheet_row(clip_id="b", failure="recognizer_timeout", hypothesis=""),
        sheet_row(clip_id="c"),
    ]
    report = build_report(rows)
    overall = report["overall"]
    assert overall["correction_rate"] == pytest.approx(2 / 3, abs=5e-5)
    assert overall["accepted_without_edit_rate"] == pytest.approx(1 / 3, abs=5e-5)
    assert overall["failures"] == 1
    # A failure is scored as deletions, not dropped from the denominator.
    failed = next(r for r in report["records"] if r["id"] == "b")
    assert failed["edits"] == failed["reference_units"]


def test_incomplete_coverage_is_labelled_and_rendered():
    report = build_report([sheet_row()])
    assert report["status"] == "incomplete_coverage"
    assert any("of 24 clips" in gap for gap in report["coverage"]["gaps"])
    assert any("of 4 speakers" in gap for gap in report["coverage"]["gaps"])
    markdown = render_markdown(report)
    assert "| Overall | 1 |" in markdown
    assert "n/a" in markdown  # zh-HK column is empty, not invented
    assert "Status: incomplete_coverage." in markdown


def test_template_matches_the_protocol_and_fixture_field_names():
    rows = build_template()
    assert len(rows) == 24
    assert len({row["speaker_id"] for row in rows}) == 4
    for speaker in {row["speaker_id"] for row in rows}:
        clips = [row for row in rows if row["speaker_id"] == speaker]
        assert len(clips) == 6
        assert [row["condition"] for row in clips].count("clean") == 3
        assert [row["condition"] for row in clips].count("noisy") == 3
        assert {row["language"] for row in clips} == {"en-HK", "zh-HK"}
    assert all(row["reference"] == "" and row["hypothesis"] == "" for row in rows)
    assert all(row["consent_recorded"] is False for row in rows)

    # Every prompt is recorded once clean and once noisy across speakers, so the
    # prompt set never coincides with one condition.
    prompts = [(language, index) for language in LANGUAGES for index in (1, 2, 3)]
    for language, index in prompts:
        conditions = {
            row["condition"]
            for row in rows
            if row["language"] == language and row["id"].endswith(f"-{index}")
        }
        assert conditions == {"clean", "noisy"}, (language, index, conditions)

    fixture = json.loads(PRISTINE_TEMPLATE.read_text(encoding="utf-8").splitlines()[0])
    assert set(fixture) <= set(rows[0])
    assert set(rows[0]) - set(fixture) == {"notes"}


def test_blank_template_sheet_cannot_be_scored():
    with pytest.raises(ValueError, match="empty"):
        score_rows(build_template())


def test_no_whisper_endpoint_fails_loudly_without_inventing_text():
    with pytest.raises(SystemExit, match="No Whisper endpoint configured"):
        resolve_endpoint(None, {})
    with pytest.raises(SystemExit, match="http"):
        resolve_endpoint("127.0.0.1:8081", {})
    assert resolve_endpoint(None, {"WHISPER_BASE_URL": "http://127.0.0.1:8081/"}) == (
        "http://127.0.0.1:8081"
    )
    assert resolve_endpoint("http://localhost:9000", {}) == "http://localhost:9000"


def test_audio_mode_exits_before_touching_files_when_unconfigured():
    rows = [sheet_row(hypothesis="", recording_path="/nonexistent/clip.wav")]
    with pytest.raises(SystemExit, match="No Whisper endpoint configured"):
        asyncio.run(fill_hypotheses(rows, ""))


def test_audio_mode_reports_a_missing_recording(tmp_path):
    rows = [sheet_row(hypothesis="", recording_path=str(tmp_path / "missing.wav"))]
    with pytest.raises(SystemExit, match="recording not found"):
        asyncio.run(fill_hypotheses(rows, "http://127.0.0.1:8081"))

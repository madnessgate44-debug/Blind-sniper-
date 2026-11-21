#!/usr/bin/env python3
"""Static contract checks for the first Miss Noor media-engine lesson prototype."""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


class LessonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.questions: list[dict[str, object]] = []
        self.current_question: dict[str, object] | None = None
        self.inline_scripts: list[str] = []
        self.in_script = False
        self.script_external = 0
        self.lang = ""
        self.title = False
        self.buttons: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang", "") or ""
        if tag == "title":
            self.title = True
        if "id" in a and a["id"]:
            self.ids.append(a["id"] or "")
        if tag == "script":
            self.in_script = True
            if a.get("src"):
                self.script_external += 1
        if tag == "div" and "question" in (a.get("class") or "").split():
            self.current_question = {"answer": a.get("data-answer"), "choices": [], "depth": 1}
            self.questions.append(self.current_question)
        elif tag == "div" and self.current_question is not None:
            self.current_question["depth"] = int(self.current_question["depth"]) + 1
        if tag == "button":
            if a.get("id"):
                self.buttons.add(a["id"] or "")
            if self.current_question is not None and a.get("data-choice"):
                choices = self.current_question["choices"]
                assert isinstance(choices, list)
                choices.append(a["data-choice"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_script:
            self.in_script = False
        if tag == "div" and self.current_question is not None:
            depth = int(self.current_question["depth"]) - 1
            if depth == 0:
                self.current_question = None
            else:
                self.current_question["depth"] = depth

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.inline_scripts.append(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="?", default="prototype/miss-noor-media-engine/lesson-01/index.html")
    args = ap.parse_args()
    path = Path(args.html)
    source = path.read_text(encoding="utf-8")
    parser = LessonParser()
    parser.feed(source)
    parser.close()

    duplicates = sorted(k for k, n in Counter(parser.ids).items() if n > 1)
    assert not duplicates, f"duplicate HTML ids: {duplicates}"
    assert parser.lang == "fr", f"expected lang=fr, got {parser.lang!r}"
    assert len(parser.questions) == 4, f"expected 4 assessment questions, got {len(parser.questions)}"
    for index, question in enumerate(parser.questions, start=1):
        choices = question["choices"]
        assert isinstance(choices, list) and len(choices) == 2, f"question {index}: expected 2 choices"
        assert len(set(choices)) == 2, f"question {index}: duplicate choices"
        assert question["answer"] in choices, f"question {index}: answer not present among choices"
    assert parser.script_external == 0, "prototype must not load remote scripts"
    assert "forearmGroup" in source and "rotate(-100 180 235)" in source, "forearm must rotate around the elbow pivot"
    assert "prefers-reduced-motion" in source, "reduced-motion behavior missing"
    assert "speechSynthesis" in source and "fr-FR" in source, "French browser narration fallback missing"
    assert len(parser.inline_scripts) == 1, f"expected one inline script, got {len(parser.inline_scripts)}"

    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
        tmp.write(parser.inline_scripts[0])
        js_path = Path(tmp.name)
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"JavaScript syntax check failed:\n{result.stderr}"
    finally:
        js_path.unlink(missing_ok=True)

    print("PASS: French locale, unique IDs, four valid assessment items, local-only assets, elbow pivot, reduced motion, French TTS fallback and JavaScript syntax.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

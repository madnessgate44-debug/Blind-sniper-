#!/usr/bin/env python3
"""PreToolUse guard decision logic.

Reads the hook event JSON on stdin and denies destructive or secret-leaking
terminal commands. Exit 2 with {"decision":"deny","reason":...} to block, exit 0
to allow.

Matching runs on a normalized command: the payload is parsed as JSON, the shell
command is split into tokens with quote/escape handling, and patterns are
evaluated against those tokens rather than raw substrings. This avoids the two
failure modes of substring matching -- bypasses (extra spaces, quoting, flags
split across argv) and false positives (a branch name that merely contains
"main").

The guard stops honest mistakes. It is not a security boundary: a determined
command can get around it. See the README Hooks section.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

MAX_DEPTH = 3


def tokens(command: str) -> list[str]:
    """Split a shell command into tokens, keeping shell operators separate.

    ``shlex.split`` leaves a ``;`` attached to the preceding word (``hi;``), so
    operators would not be seen as segment boundaries. ``shlex.shlex`` with
    ``punctuation_chars`` makes ``; | & ( ) < >`` standalone tokens, which lets
    :func:`segments` split reliably.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def segments(argv: list[str]) -> list[list[str]]:
    """Split argv into simple commands on shell operators."""
    out: list[list[str]] = []
    current: list[str] = []
    separators = {"|", "||", "&&", ";", "&", "(", ")", ";;", "|&"}
    for tok in argv:
        if tok in separators:
            if current:
                out.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        out.append(current)
    return out


def deny(reason: str) -> None:
    print(json.dumps({"decision": "deny", "reason": reason}))
    sys.exit(2)


def prog_of(tok: str) -> str:
    return tok.rsplit("/", 1)[-1]


def current_branch() -> str:
    """The checked-out branch of the repo the guard runs in, or "" on failure.

    The guard runs from the project workspace, so this reflects the branch a bare
    `git push`/`git push origin HEAD` would actually update.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

# git global options that take a separate value, and flag-only options, skipped
# before the subcommand is read.
GIT_VALUE_OPTS = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace",
    "--exec-path", "--config-env", "--super-prefix",
}
GIT_FLAG_OPTS = {
    "--no-pager", "--no-replace-objects", "-p", "--paginate", "--bare",
    "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
    "--icase-pathspecs", "--version", "--help", "-P", "--no-optional-locks",
    "--no-advice", "--no-lazy-fetch",
}
FORCE_FLAGS = {"-f", "--force", "--force-with-lease", "--force-if-includes"}
PROTECTED = {"main", "master"}
SHORT_FORCE = "f"

# In this sandbox the plugin loader clones with a token embedded in the remote
# URL (verified: ~/.openhands/cache/plugins/*/.git/config has
# `https://<token>@github.com/...`), so anything that prints the remote URL
# leaks that token into the transcript.
TOKEN_PRINT_REASON = (
    "Refusing this: it may print a remote URL that embeds a git token "
    "(this sandbox clones with `https://<token>@...`). Read the URL without the "
    "token, or use `git remote` (names only)."
)


def git_subcommand(argv: list[str]) -> tuple[str | None, int]:
    """Return (subcommand, index) skipping git's global options."""
    if not argv or prog_of(argv[0]) != "git":
        return None, -1
    i = 1
    while i < len(argv):
        t = argv[i]
        if t in GIT_VALUE_OPTS:
            i += 2
            continue
        if t.startswith("--") and any(t.startswith(o + "=") for o in GIT_VALUE_OPTS):
            i += 1
            continue
        if t in GIT_FLAG_OPTS:
            i += 1
            continue
        if t.startswith("-"):
            # `-C<path>` / `-c<kv>` written without a space, or any other flag.
            i += 1
            continue
        return t, i
    return None, -1


def is_refspec_to_protected(tok: str) -> bool:
    """True for `src:dst` or `+src:dst` refspecs whose destination is main/master."""
    body = tok[1:] if tok.startswith("+") else tok
    if ":" not in body:
        return False
    dst = body.split(":", 1)[1]
    return dst.rsplit("/", 1)[-1] in PROTECTED


def push_is_force(rest: list[str]) -> bool:
    for t in rest:
        if t in FORCE_FLAGS or t.startswith("--force-with-lease") or t.startswith("--force-if-includes"):
            return True
        if t.startswith("+"):
            return True
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            if SHORT_FORCE in t[1:]:
                return True
    return False


def short_group_has(tok: str, letter: str) -> bool:
    return tok.startswith("-") and not tok.startswith("--") and letter in tok[1:]


def check_git(argv: list[str]) -> None:
    sub, idx = git_subcommand(argv)
    if sub is None:
        return
    rest = argv[idx + 1:]

    if any(t == "--no-verify" or t.startswith("--no-verify") for t in rest):
        deny("Refusing to bypass git hooks with --no-verify.")

    if sub == "commit" and any(short_group_has(t, "n") for t in rest):
        deny("Refusing to bypass git hooks with `git commit -n` (--no-verify).")

    # This sandbox's plugin loader clones with a token embedded in the remote URL,
    # so these commands can print that token into the transcript.
    if sub == "remote":
        if any(t == "-v" or t == "--verbose" or short_group_has(t, "v") for t in rest):
            deny(TOKEN_PRINT_REASON)
        if "get-url" in rest or any(t.startswith("get-url") for t in rest):
            deny(TOKEN_PRINT_REASON)
    if sub == "config":
        joined = " ".join(rest)
        if "--list" in rest or "-l" in rest or any(short_group_has(t, "l") for t in rest):
            deny(TOKEN_PRINT_REASON)
        if "--get" in rest or "--get-all" in rest or "--get-regexp" in rest:
            if "url" in joined.lower():
                deny(TOKEN_PRINT_REASON)

    if sub != "push":
        return

    for flag in ("--all", "--mirror"):
        if flag in rest:
            deny(
                f"Refusing `git push {flag}`; it can include main/master. "
                "Push one branch and open a pull request."
            )
    if push_is_force(rest):
        deny("Refusing to force-push (--force/-f/-fu/--force-with-lease/+ref). Push to a branch instead.")

    positionals = [t for t in rest if not t.startswith("-")]
    ref_args = positionals[1:] if positionals else []
    for tok in ref_args:
        if is_refspec_to_protected(tok) or tok.rsplit("/", 1)[-1] in PROTECTED:
            deny(
                "Refusing to push to main/master (including HEAD:main and refspecs). "
                "Push to a branch and open a pull request."
            )

    # A bare `git push`, or a refspec of `HEAD`, pushes the checked-out branch.
    # Resolve it: the guard runs in the workspace, so this is the branch that
    # would actually be updated. (`HEAD:main` is already caught above.)
    pushes_head = not ref_args or any(tok == "HEAD" for tok in ref_args)
    if pushes_head and current_branch() in PROTECTED:
        deny(
            "Refusing to push to main/master: the current branch is main/master. "
            "Run `git switch -c <short-name>` first, then push that branch."
        )


# --------------------------------------------------------------------------- #
# rm -rf
# --------------------------------------------------------------------------- #

SYSTEM_DIRS = {
    "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/opt", "/proc",
    "/root", "/sbin", "/sys", "/usr", "/var", "/lib64", "/srv", "/run",
}
RM_DENY = {"/", "/*", "~", "~/", "~/*", "$HOME", "${HOME}", ".git", ".", ".."} | SYSTEM_DIRS


def norm_target(t: str) -> str:
    t = t.strip().strip('"').strip("'")
    while len(t) > 1 and t.endswith("/"):
        t = t[:-1]
    return t


def check_rm(argv: list[str]) -> None:
    if not argv or prog_of(argv[0]) != "rm":
        return
    recursive = False
    targets: list[str] = []
    for tok in argv[1:]:
        if tok == "--recursive":
            recursive = True
        elif tok.startswith("--"):
            continue
        elif tok.startswith("-") and len(tok) > 1:
            if "r" in tok[1:] or "R" in tok[1:]:
                recursive = True
        else:
            targets.append(tok)
    if not recursive:
        return
    for t in targets:
        if norm_target(t) in RM_DENY:
            deny(f"Refusing a recursive delete of a filesystem-root, home or system path: {t}")


# --------------------------------------------------------------------------- #
# secrets
# --------------------------------------------------------------------------- #

SECRET_NAME = re.compile(r"(?i)(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY|CREDENTIAL)")
VAR_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
NAME_ONLY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Commands that write their arguments to stdout. A secret var passed to one of
# these lands in the transcript; a secret var used for auth (a URL or header) does not.
PRINTERS = {
    "echo", "printf", "set", "export",
    "cat", "bat", "less", "more", "head", "tail", "tee",
}

# Template .env files hold placeholders, not secrets, and are meant to be shared.
ENV_TEMPLATES = {".env.example", ".env.sample", ".env.template"}


def token_has_secret_var(tok: str) -> bool:
    return any(SECRET_NAME.search(m.group(1)) for m in VAR_RE.finditer(tok))


def check_secret_print(argv: list[str]) -> None:
    if not argv:
        return
    prog = prog_of(argv[0])
    if prog == "printenv":
        args = [a for a in argv[1:] if not a.startswith("-")]
        if not args:
            deny("Refusing to dump all environment secrets with printenv.")
        for a in args:
            if SECRET_NAME.search(a):
                deny(f"Refusing to print the secret environment variable {a} to the transcript.")
        return
    if prog == "env":
        if len(argv) == 1:
            deny("Refusing to dump all environment secrets with env.")
        for a in argv[1:]:
            if a.startswith("-") or "=" in a:
                continue
            if NAME_ONLY.match(a) and SECRET_NAME.search(a):
                deny(f"Refusing to print the secret environment variable {a} to the transcript.")
        return
    if prog not in PRINTERS:
        return
    for tok in argv[1:]:
        if token_has_secret_var(tok):
            deny("Refusing to print an environment secret value to the transcript.")
        base = prog_of(tok)
        if tok.startswith("/proc/") and "environ" in tok:
            deny("Refusing to read /proc/*/environ (process secrets).")
        if re.fullmatch(r"\.env(\.[\w.-]+)?", base) and base not in ENV_TEMPLATES:
            deny(f"Refusing to read a .env file ({tok}) into the transcript.")
        if base == "config" and ".git" in tok:
            deny(TOKEN_PRINT_REASON)


# --------------------------------------------------------------------------- #
# pipes and wrappers
# --------------------------------------------------------------------------- #

INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "python", "python3", "node", "perl", "ruby"}
WRAP_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
WRAP_PREFIX = {"sudo", "command", "nohup", "time", "env", "setsid", "stdbuf", "nice", "ionice"}
VALUE_OPTS = {
    "sudo": {"-u", "-g", "-p", "-C", "-h", "-r", "-t", "-U", "--user", "--group", "--prompt"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "xargs": {"-I", "-n", "-P", "-L", "-s", "-a", "-d", "-E", "--max-args", "--max-procs"},
}


def skip_wrapper_opts(prog: str, args: list[str]) -> int:
    """Count leading option tokens belonging to a wrapper program.

    Handles combined short groups where the last letter takes a value, e.g.
    ``sudo -Eu root`` (``u`` takes ``root``) versus ``sudo -E`` (flag only).
    """
    opts = VALUE_OPTS.get(prog, set())
    value_letters = {o[1] for o in opts if o.startswith("-") and not o.startswith("--")}
    long_values = {o for o in opts if o.startswith("--")}
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a == "--":
            i += 1
            break
        if a.startswith("--"):
            takes = a.split("=", 1)[0] in long_values and "=" not in a
            i += 2 if takes and i + 1 < len(args) else 1
            continue
        if a[1:] and a[-1] in value_letters and i + 1 < len(args):
            i += 2
        else:
            i += 1
    return i


def check_pipe(argv: list[str]) -> None:
    segs = segments(argv)
    for i, seg in enumerate(segs[:-1]):
        if not seg or prog_of(seg[0]) not in {"curl", "wget"}:
            continue
        nxt = segs[i + 1]
        j = 0
        # Step over wrapper programs and their flags (`sudo -E bash` -> bash).
        while j < len(nxt):
            p = prog_of(nxt[j])
            if p in ("sudo", "timeout", "xargs"):
                j += 1
                j += skip_wrapper_opts(p, nxt[j:])
                if p == "timeout" and j < len(nxt):
                    j += 1  # skip the duration
                continue
            if p in WRAP_PREFIX or nxt[j].startswith("-"):
                j += 1
                continue
            break
        if j < len(nxt) and prog_of(nxt[j]) in INTERPRETERS:
            deny(f"Refusing to pipe {prog_of(seg[0])} output directly into {prog_of(nxt[j])}.")


def short_flag_group_with(tok: str, letter: str) -> bool:
    """True for a short-flag group like ``-lc`` or ``-ec`` that contains ``letter``."""
    return tok.startswith("-") and not tok.startswith("--") and letter in tok[1:]


def unwrap(seg: list[str]) -> list[str]:
    """Inner command strings hidden behind a wrapper in this segment."""
    if not seg:
        return []
    prog = prog_of(seg[0])
    args = seg[1:]
    if prog in WRAP_SHELLS:
        # `-c`, and any short group containing c (`-lc`, `-ec`, `-xec`).
        for k, a in enumerate(args):
            if short_flag_group_with(a, "c") and k + 1 < len(args) and args[k + 1]:
                return [args[k + 1]]
        return []
    if prog in ("sudo", "timeout", "xargs"):
        i = skip_wrapper_opts(prog, args)
        if prog == "timeout" and i < len(args):
            i += 1  # skip the duration
        return [" ".join(args[i:])] if args[i:] else []
    if prog == "command":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 1
        return [" ".join(args[i:])] if args[i:] else []
    if prog in ("nohup", "time", "setsid", "stdbuf", "nice", "ionice"):
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 1
        return [" ".join(args[i:])] if args[i:] else []
    if prog == "env":
        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("-"):
                i += 1
                continue
            if re.match(r"[A-Za-z_][A-Za-z0-9_]*=", a):
                i += 1
                continue
            break
        return [" ".join(args[i:])] if args[i:] else []
    if prog == "eval":
        return [" ".join(args)] if args else []
    return []


PROC_SUB = re.compile(
    r"(?<![\w])(bash|sh|zsh|dash|ksh|fish|source|python3?|node|perl|ruby)\s+<\(\s*(curl|wget)\b"
)
SUBST_DOLLAR = re.compile(r"\$\(([^()]*)\)")
SUBST_TICK = re.compile(r"`([^`]*)`")

# A heredoc body is code only when a shell (or source/eval) consumes it. For every
# other consumer (cat, tee, python, node, ...) the body is data and is ignored.
HEREDOC_CONSUMERS = WRAP_SHELLS | {"source", "eval"}


def _segment_program(seg: list[str]) -> str:
    """The real program of a simple command, past wrapper prefixes and env assigns."""
    i = 0
    while i < len(seg):
        tok = seg[i]
        p = prog_of(tok)
        if p in ("sudo", "timeout", "xargs"):
            i += 1
            i += skip_wrapper_opts(p, seg[i:])
            if p == "timeout" and i < len(seg):
                i += 1
            continue
        if re.match(r"[A-Za-z_][A-Za-z0-9_]*=", tok):
            i += 1
            continue
        if p in WRAP_PREFIX:
            i += 1
            continue
        return p
    return ""


def _heredoc_specs(line: str) -> list[tuple[str, bool]]:
    """(delimiter, strip_tabs) for each ``<<``/``<<-`` on a header line.

    ``<<<`` is a herestring, not a heredoc, so it never matches. Quotes around the
    delimiter are already removed by the tokenizer.
    """
    toks = tokens(line)
    specs: list[tuple[str, bool]] = []
    k = 0
    while k < len(toks):
        if toks[k] == "<<":
            strip_tabs = False
            k += 1
            d: str | None = None
            if k < len(toks):
                if toks[k] == "-":
                    strip_tabs = True
                    k += 1
                    d = toks[k] if k < len(toks) else None
                elif toks[k].startswith("-") and len(toks[k]) > 1:
                    strip_tabs = True
                    d = toks[k][1:]
                else:
                    d = toks[k]
            if d is not None:
                specs.append((d.strip('"').strip("'"), strip_tabs))
            k += 1
        else:
            k += 1
    return specs


def _heredoc_consumer(line: str) -> str:
    """The program that reads the heredoc declared on this header line.

    Usually the program of the segment that carries the ``<<``. One extra case: when
    that segment is piped into a shell (``cat <<EOF | bash``), the body reaches the
    shell through the pipe, so the shell is the consumer.
    """
    segs = segments(tokens(line))
    for idx, seg in enumerate(segs):
        if "<<" in seg:
            prog = _segment_program(seg)
            if prog in HEREDOC_CONSUMERS:
                return prog
            if idx + 1 < len(segs) and _segment_program(segs[idx + 1]) in WRAP_SHELLS:
                return _segment_program(segs[idx + 1])
            return prog
    return ""


def extract_heredocs(command: str) -> tuple[str, list[tuple[str, str]]]:
    """Strip heredoc bodies from a command.

    Returns the command with each body (and its terminator) removed, plus a list of
    ``(consumer_program, body)``. An unterminated heredoc takes the rest of the
    command as its body. ``<<-`` strips leading tabs when matching the terminator.
    """
    lines = command.split("\n")
    kept: list[str] = []
    bodies: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        specs = _heredoc_specs(line)
        kept.append(line)
        i += 1
        if not specs:
            continue
        consumer = _heredoc_consumer(line)
        for delim, strip_tabs in specs:
            body: list[str] = []
            while i < len(lines):
                cand = lines[i].lstrip("\t") if strip_tabs else lines[i]
                if cand == delim:
                    break
                body.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # drop the terminator line
            bodies.append((consumer, "\n".join(body)))
    return "\n".join(kept), bodies


def _herestring_code(seg: list[str]) -> list[str]:
    """Here-string operands of a shell consumer, which are executed as code."""
    if not seg or _segment_program(seg) not in HEREDOC_CONSUMERS:
        return []
    out: list[str] = []
    for k, tok in enumerate(seg):
        if tok == "<<<" and k + 1 < len(seg):
            out.append(seg[k + 1])
    return out


def check_all(command: str, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        return
    command = command.strip()
    if not command:
        return
    command, bodies = extract_heredocs(command)
    # A newline separates commands; a trailing backslash continues the line.
    for line in re.sub(r"\\\n", " ", command).split("\n"):
        if not line.strip():
            continue
        argv = tokens(line)
        for seg in segments(argv):
            if not seg:
                continue
            check_git(seg)
            check_rm(seg)
            check_secret_print(seg)
            for inner in unwrap(seg):
                check_all(inner, depth + 1)
            for inner in _herestring_code(seg):
                check_all(inner, depth + 1)
        check_pipe(argv)
    for m in SUBST_DOLLAR.finditer(command):
        check_all(m.group(1), depth + 1)
    for m in SUBST_TICK.finditer(command):
        check_all(m.group(1), depth + 1)
    if PROC_SUB.search(command):
        deny("Refusing to run a downloaded script via process substitution (<(...)).")
    for consumer, body in bodies:
        if consumer in HEREDOC_CONSUMERS:
            check_all(body, depth + 1)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(
            "account-library guard: could not read the hook payload as JSON; allowing.",
            file=sys.stderr,
        )
        return 0
    if not isinstance(payload, dict):
        print(
            "account-library guard: hook payload is not an object; allowing.",
            file=sys.stderr,
        )
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return 0
    check_all(command)
    return 0


if __name__ == "__main__":
    sys.exit(main())

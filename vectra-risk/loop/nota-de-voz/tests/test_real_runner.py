"""El ejecutor real (`SubprocessRunner`) con procesos inofensivos: un interprete de Python que duerme o escribe un archivo. Sin `gh` y sin grabador."""

from __future__ import annotations

import stat
import sys
import time
from pathlib import Path

from vectra_nota_de_voz.audio import record
from vectra_nota_de_voz.commands import SubprocessRunner

WRITER = "import sys, time, pathlib; pathlib.Path(sys.argv[1]).write_bytes(b'RIFF'); time.sleep(60)"


def wait_for(path: Path) -> None:
    deadline = time.monotonic() + 10
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)


def test_a_spawned_process_creates_private_files_and_is_stopped_with_sigint(tmp_path: Path) -> None:
    out = tmp_path / "nota.wav"
    log = tmp_path / "grabador.log"
    process = SubprocessRunner().spawn([sys.executable, "-c", WRITER, str(out)], log)
    wait_for(out)
    assert process.poll() is None
    assert stat.S_IMODE(out.stat().st_mode) == 0o600, "umask 077 en el hijo: el archivo nace privado"
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    started = time.monotonic()
    process.stop()
    assert process.poll() is not None and time.monotonic() - started < 5
    assert "KeyboardInterrupt" in log.read_text(), "lo paro SIGINT, como a un grabador"
    process.stop()  # parar dos veces no falla


def test_a_process_that_ignores_sigint_is_killed(tmp_path: Path) -> None:
    code = "import signal, sys, time, pathlib; signal.signal(signal.SIGINT, signal.SIG_IGN); pathlib.Path(sys.argv[1]).write_text('x'); time.sleep(60)"
    ready = tmp_path / "listo"
    process = SubprocessRunner().spawn([sys.executable, "-c", code, str(ready)], tmp_path / "log")
    wait_for(ready)
    process.stop()
    assert process.poll() == -9


def test_run_captures_output_and_a_missing_program_is_a_return_code_not_a_trace() -> None:
    runner = SubprocessRunner()
    done = runner.run(
        [sys.executable, "-c", "import os, sys; print(os.environ.get('X')); sys.exit(3)"], {"X": "uno"}
    )
    assert (done.returncode, done.stdout.strip()) == (3, "uno")
    assert runner.run(["/no/existe/gh"], {}).returncode == 127
    assert runner.interactive(["/no/existe/editor"]) == 127
    assert runner.interactive([sys.executable, "-c", "raise SystemExit(4)"]) == 4
    assert runner.which("sh") and runner.which("no-existe-este-programa") is None


def test_record_with_a_real_child_process_stops_it_on_enter(tmp_path: Path, monkeypatch) -> None:
    """`audio.record` de punta a punta con un proceso de verdad en el lugar del grabador (la orden del grabador se sustituye; no se graba nada)."""
    import vectra_nota_de_voz.audio as audio

    monkeypatch.setattr(
        audio, "recorder_command", lambda program, wav, seconds: [sys.executable, "-c", WRITER, str(wav)]
    )

    class Waiter:
        def wait_enter(self, seconds: float) -> bool:
            wait_for(tmp_path / "nota.wav")
            return True

    wav = record(SubprocessRunner(), Waiter(), "arecord", tmp_path, 30)
    assert wav == tmp_path / "nota.wav" and stat.S_IMODE(wav.stat().st_mode) == 0o600

# judge/sandbox.py
import subprocess
import tempfile
import os
import sys
import time

# detect platform
IS_WINDOWS = sys.platform == 'win32'

# ── resource limits (Unix/Mac only) ──
if not IS_WINDOWS:
    import resource

    def _apply_limits(memory_mb, cpu_seconds):
        """
        Runs inside the child process before user code executes.
        Sets hard limits on memory, CPU, file size, and processes.
        Unix/Mac only.
        """
        mem = memory_mb * 1024 * 1024

        # total virtual memory
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        # CPU time in seconds
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        # max file size user can write (10MB)
        resource.setrlimit(resource.RLIMIT_FSIZE,
                           (10 * 1024 * 1024, 10 * 1024 * 1024))
        # max child processes (defeats fork bombs)
        resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
        # max open file descriptors
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

else:
    def _apply_limits(memory_mb, cpu_seconds):
        # Windows: no resource module
        # Timeout via subprocess is our only protection here
        pass


def make_preexec(memory_mb=256, cpu_seconds=6):
    """
    Returns a zero-argument callable for subprocess preexec_fn.
    On Windows, returns None (preexec_fn not supported on Windows).
    """
    if IS_WINDOWS:
        return None

    def _inner():
        _apply_limits(memory_mb, cpu_seconds)

    return _inner


# ── verdict constants ──
AC      = 'AC'
WA      = 'WA'
TLE     = 'TLE'
RE      = 'RE'
CE      = 'CE'


def compile_cpp(code: str, tmpdir: str) -> dict:
    """Compile C++ source. Returns {'success': True, 'binary': path} or {'success': False, 'stderr': ...}"""
    src    = os.path.join(tmpdir, 'solution.cpp')
    binary = os.path.join(tmpdir, 'solution.exe' if IS_WINDOWS else 'solution')

    with open(src, 'w', encoding='utf-8') as f:
        f.write(code)

    # on Windows: needs MinGW (g++) installed
    # on Mac/Linux: g++ is usually pre-installed
    try:
        result = subprocess.run(
            ['g++', '-o', binary, src, '-O2', '-std=c++17', '-lm'],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return {
            'success': False,
            'stderr': 'g++ compiler not found. Install MinGW on Windows or Xcode tools on Mac.'
        }

    if result.returncode != 0:
        return {'success': False, 'stderr': result.stderr}

    return {'success': True, 'binary': binary}


def compile_java(code: str, tmpdir: str) -> dict:
    """Compile Java source."""
    src = os.path.join(tmpdir, 'Solution.java')
    with open(src, 'w', encoding='utf-8') as f:
        f.write(code)

    try:
        result = subprocess.run(
            ['javac', src],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return {'success': False, 'stderr': 'javac not found. Install JDK.'}

    if result.returncode != 0:
        return {'success': False, 'stderr': result.stderr}

    return {'success': True, 'classpath': tmpdir}


def run_code_sync(
    code: str,
    language: str,
    stdin_data: str,
    expected_output: str,
    time_limit: float = 5.0,
    memory_limit_mb: int = 256,
) -> dict:
    """
    Runs user code against ONE test case.

    Returns dict with keys:
        verdict:  AC | WA | TLE | RE | CE
        time_ms:  float (execution time)
        stdout:   str
        stderr:   str
        expected: str
    """
    with tempfile.TemporaryDirectory() as tmpdir:

        # ── build the command based on language ──
        if language == 'python':
            filepath = os.path.join(tmpdir, 'solution.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            # -u = unbuffered so print() flushes before timeout
            cmd = [sys.executable, '-u', filepath]
            preexec = make_preexec(memory_limit_mb, int(time_limit) + 1)

        elif language == 'cpp':
            compile_result = compile_cpp(code, tmpdir)
            if not compile_result['success']:
                return {
                    'verdict': CE,
                    'time_ms': 0,
                    'stdout': '',
                    'stderr': compile_result['stderr'],
                    'expected': expected_output,
                }
            cmd = [compile_result['binary']]
            preexec = make_preexec(memory_limit_mb, int(time_limit) + 1)

        elif language == 'java':
            compile_result = compile_java(code, tmpdir)
            if not compile_result['success']:
                return {
                    'verdict': CE,
                    'time_ms': 0,
                    'stdout': '',
                    'stderr': compile_result['stderr'],
                    'expected': expected_output,
                }
            cmd = ['java', '-cp', compile_result['classpath'],
                   '-Xmx{}m'.format(memory_limit_mb), 'Solution']
            preexec = None  # java handles its own memory via -Xmx

        else:
            return {'verdict': RE, 'time_ms': 0,
                    'stdout': '', 'stderr': f'Unknown language: {language}',
                    'expected': expected_output}

        # ── execute ──
        start = time.perf_counter()
        try:
            # preexec_fn only works on Unix — on Windows it's None
            run_kwargs = dict(
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=time_limit,
                cwd=tmpdir,
            )
            if preexec is not None:
                run_kwargs['preexec_fn'] = preexec

            proc = subprocess.run(cmd, **run_kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # ── runtime error ──
            if proc.returncode != 0:
                return {
                    'verdict': RE,
                    'time_ms': round(elapsed_ms, 2),
                    'stdout': proc.stdout[:5000],
                    'stderr': proc.stderr[:2000],
                    'expected': expected_output,
                }

            # ── compare output ──
            actual   = proc.stdout.strip()
            expected = expected_output.strip()

            return {
                'verdict': AC if actual == expected else WA,
                'time_ms': round(elapsed_ms, 2),
                'stdout':  actual,
                'stderr':  proc.stderr[:500],
                'expected': expected,
            }

        except subprocess.TimeoutExpired:
            return {
                'verdict': TLE,
                'time_ms': time_limit * 1000,
                'stdout': '',
                'stderr': f'Time limit of {time_limit}s exceeded.',
                'expected': expected_output,
            }

        except Exception as e:
            return {
                'verdict': RE,
                'time_ms': 0,
                'stdout': '',
                'stderr': str(e),
                'expected': expected_output,
            }
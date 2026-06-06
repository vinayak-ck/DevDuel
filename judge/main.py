# judge/main.py
import asyncio
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
from contextlib import asynccontextmanager
from sandbox import run_code_sync


# ── request/response models ──

class TestCase(BaseModel):
    input:  str
    output: str

class ExecuteRequest(BaseModel):
    code:            str
    language:        Literal['python', 'cpp', 'java']
    test_cases:      list[TestCase]     # Django sends these — judge doesn't touch DB
    time_limit:      float = 5.0
    memory_limit_mb: int   = 256

class TestCaseResult(BaseModel):
    passed:   bool
    stdout:   str
    expected: str
    time_ms:  float

class ExecuteResponse(BaseModel):
    verdict:       Literal['AC', 'WA', 'TLE', 'RE', 'CE']
    time_ms:       float
    test_results:  list[TestCaseResult]
    stderr:        str = ''
    tests_passed:  int = 0
    tests_total:   int = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[Judge] Starting — Python {sys.version}")
    print(f"[Judge] Platform: {sys.platform}")
    print("[Judge] Stateless judge ready — no DB needed")
    yield
    print("[Judge] Shutting down")


app = FastAPI(
    title="DevDuel Judge API",
    description="Stateless sandboxed code execution. Test cases passed in request.",
    version="2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {
        "status":   "judge online",
        "platform": sys.platform,
        "python":   sys.version,
        "version":  "2.0 (stateless)",
    }


@app.post("/execute", response_model=ExecuteResponse)
async def execute_code(body: ExecuteRequest):
    if not body.test_cases:
        raise HTTPException(
            status_code=400,
            detail="No test cases provided in request body"
        )

    test_results = []
    overall      = 'AC'
    max_time_ms  = 0.0
    last_stderr  = ''
    loop         = asyncio.get_event_loop()

    for tc in body.test_cases:
        result = await loop.run_in_executor(
            None,
            run_code_sync,
            body.code,
            body.language,
            tc.input,
            tc.output,
            body.time_limit,
            body.memory_limit_mb,
        )

        # CE — stop immediately
        if result['verdict'] == 'CE':
            return ExecuteResponse(
                verdict='CE',
                time_ms=0,
                test_results=[],
                stderr=result['stderr'],
                tests_passed=0,
                tests_total=len(body.test_cases),
            )

        # TLE or RE — record and stop
        if result['verdict'] in ('TLE', 'RE'):
            overall     = result['verdict']
            last_stderr = result['stderr']
            test_results.append(TestCaseResult(
                passed=False,
                stdout=result['stdout'],
                expected=tc.output.strip(),
                time_ms=result['time_ms'],
            ))
            break

        # WA — record, continue running rest of test cases
        if result['verdict'] == 'WA' and overall == 'AC':
            overall = 'WA'

        max_time_ms = max(max_time_ms, result['time_ms'])
        last_stderr = result['stderr']

        test_results.append(TestCaseResult(
            passed=result['verdict'] == 'AC',
            stdout=result['stdout'],
            expected=tc.output.strip(),
            time_ms=result['time_ms'],
        ))

    tests_passed = sum(1 for r in test_results if r.passed)

    return ExecuteResponse(
        verdict=overall,
        time_ms=round(max_time_ms, 2),
        test_results=test_results,
        stderr=last_stderr,
        tests_passed=tests_passed,
        tests_total=len(body.test_cases),
    )
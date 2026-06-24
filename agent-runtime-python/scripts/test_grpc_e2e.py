import asyncio
import grpc
import json
import requests
import sys
import time

sys.path.insert(0, ".")

from app.grpc import code_generation_pb2, code_generation_pb2_grpc

BASE_URL = "http://localhost:8700/api"

session = requests.Session()
failures: list[str] = []


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def fail(step: str, message: object):
    text = f"  {step}: FAIL - {message}"
    failures.append(text)
    print(text)


async def wait_for_python_grpc(timeout_seconds: int = 60) -> bool:
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        channel = grpc.aio.insecure_channel("localhost:9091")
        stub = code_generation_pb2_grpc.CodeGenerationServiceStub(channel)
        try:
            resp = await stub.ValidatePrompt(
                code_generation_pb2.ValidatePromptRequest(prompt="health check"),
                timeout=3,
            )
            await channel.close()
            if resp.valid:
                return True
        except Exception as e:
            last_error = e
            await channel.close()
            await asyncio.sleep(2)
    fail("5.0 Python gRPC readiness", last_error or "timeout")
    return False


def test_e2e():
    print("=" * 60)
    print("TEST 5: End-to-End - Java HTTP -> gRPC -> Python StreamGenerate")
    print("=" * 60)

    if not asyncio.run(wait_for_python_grpc()):
        return 1

    # 5.1 Login
    try:
        resp = session.post(f"{BASE_URL}/user/login", json={
            "userAccount": "admin",
            "userPassword": "Adcage@2024"
        })
        data = resp.json()
        if data.get("code") != 0:
            # try another password
            resp = session.post(f"{BASE_URL}/user/login", json={
                "userAccount": "admin",
                "userPassword": "12345678"
            })
            data = resp.json()
        if data.get("code") != 0:
            fail("5.1 Login", data)
            print("  Trying to find valid credentials...")
            # Try common passwords
            for pwd in ["admin123", "password", "123456", "admin", "Adcage123"]:
                resp = session.post(f"{BASE_URL}/user/login", json={
                    "userAccount": "admin",
                    "userPassword": pwd
                })
                data = resp.json()
                if data.get("code") == 0:
                    print(f"  5.1 Login: PASS (password={pwd})")
                    break
            else:
                fail("5.1 Login", "cannot find valid credentials, skipping E2E test")
                return 1
        else:
            print(f"  5.1 Login: PASS")
    except Exception as e:
        fail("5.1 Login", e)
        return 1

    # 5.2 Get user info
    try:
        resp = session.get(f"{BASE_URL}/user/get/login")
        data = resp.json()
        if data.get("code") == 0:
            user_id = data["data"]["id"]
            print(f"  5.2 GetLoginUser: PASS - userId={user_id}")
        else:
            fail("5.2 GetLoginUser", data)
            return 1
    except Exception as e:
        fail("5.2 GetLoginUser", e)
        return 1

    # 5.3 Create an app
    try:
        resp = session.post(f"{BASE_URL}/app/add", json={
            "appName": "gRPC E2E Test App",
            "codeGenType": "vue_project",
            "initPrompt": "Create a simple counter app",
        })
        data = resp.json()
        if data.get("code") == 0:
            app_id = data["data"]
            print(f"  5.3 CreateApp: PASS - appId={app_id}")
        else:
            fail("5.3 CreateApp", data)
            return 1
    except Exception as e:
        fail("5.3 CreateApp", e)
        return 1

    # 5.4 Trigger code generation via SSE stream (this goes through gRPC to Python)
    try:
        print(f"  5.4 StreamGenerate (E2E): Calling /app/chat/gen/code/stream?appId={app_id}&message=...")
        start = time.time()
        resp = session.get(
            f"{BASE_URL}/app/chat/gen/code/stream",
            params={"appId": app_id, "message": "Create a simple counter app with Vue 3"},
            stream=True,
            headers={"Accept": "text/event-stream"},
        )
        if resp.status_code != 200:
            fail("5.4 StreamGenerate (E2E)", f"HTTP {resp.status_code}: {resp.text[:300]}")
            return 1
        resp.encoding = "utf-8"

        events = []
        event_types = []
        session_id = None
        for line in resp.iter_lines(decode_unicode=True):
            if line:
                events.append(line)
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload:
                        try:
                            payload_obj = json.loads(payload)
                            if "sessionId" in payload_obj:
                                session_id = payload_obj["sessionId"]
                        except json.JSONDecodeError:
                            pass
                        event_types.append(payload[:80])
                        payload_lower = payload.lower()
                        if (
                            "生成失败" in payload
                            or "unavailable" in payload_lower
                            or "exception" in payload_lower
                            or "\"error\"" in payload_lower
                        ):
                            fail("5.4 StreamGenerate (E2E)", f"failure payload: {payload[:300]}")
                            return 1
                if len(events) > 200:
                    break

        elapsed = time.time() - start
        if not events:
            fail("5.4 StreamGenerate (E2E)", "no SSE events received")
            return 1
        if not event_types:
            fail("5.4 StreamGenerate (E2E)", f"no data events received, lines={events[:5]}")
            return 1
        if session_id is None:
            fail("5.4 StreamGenerate (E2E)", f"sessionId not found in SSE meta, lines={events[:5]}")
            return 1
        print(f"  5.4 StreamGenerate (E2E): PASS")
        print(f"       - {len(events)} SSE lines in {elapsed:.1f}s")
        print(f"       - Event types seen: {len(event_types)} data events")
        for et in event_types[:5]:
            print(f"         > {et}")
        if len(event_types) > 5:
            print(f"         > ... and {len(event_types) - 5} more")
    except Exception as e:
        fail("5.4 StreamGenerate (E2E)", e)
        return 1

    # 5.5 Verify persisted AI history is successful after async build/version creation
    try:
        print("  5.5 Verify build/history status: Checking chat history...")
        latest_ai_record = None
        for _ in range(90):
            resp = session.post(f"{BASE_URL}/app/chat/history/page", json={
                "appId": app_id,
                "sessionId": session_id,
                "pageNum": 1,
                "pageSize": 10,
            })
            data = resp.json()
            if data.get("code") != 0:
                fail("5.5 Verify build/history status", data)
                return 1
            records = data.get("data", {}).get("records", [])
            ai_records = [record for record in records if record.get("messageType") == "ai"]
            if ai_records:
                latest_ai_record = ai_records[-1]
                status = latest_ai_record.get("status")
                message = latest_ai_record.get("message") or ""
                if status == "failed" or "生成失败" in message or "构建失败" in message:
                    fail("5.5 Verify build/history status", latest_ai_record)
                    return 1
                if status == "success":
                    print("  5.5 Verify build/history status: PASS - AI history status=success")
                    break
            time.sleep(2)
        else:
            fail("5.5 Verify build/history status", latest_ai_record or "AI history not created")
            return 1
    except Exception as e:
        fail("5.5 Verify build/history status", e)
        return 1

    # 5.6 Verify the runtime used was python-agent via gRPC
    try:
        # Check backend logs for gRPC-related entries
        print(f"  5.6 Verify gRPC path: Checking backend logs...")
        import subprocess
        result = subprocess.run(
            ["powershell", "-Command", f"Get-Content 'E:\\Programme\\Project\\protoflow-ai\\logs\\backend.log' -Tail 100 | Select-String -Pattern 'grpc|GrpcPythonAgentRuntime|StreamGenerate' | Select-Object -First 5"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        stdout = (result.stdout or "").strip()
        if stdout:
            lines = stdout.split("\n")
            print(f"  5.6 Verify gRPC path: PASS - Found {len(lines)} gRPC-related log entries")
            for line in lines[:3]:
                print(f"       > {line.strip()[:100]}")
        else:
            fail("5.6 Verify gRPC path", "No gRPC log entries found")
            return 1
    except Exception as e:
        fail("5.6 Verify gRPC path", e)
        return 1

    print()
    print("=" * 60)
    print("E2E TEST COMPLETE")
    print("=" * 60)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(test_e2e())

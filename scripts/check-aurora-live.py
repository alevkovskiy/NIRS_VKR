import json
import subprocess
import uuid
from pathlib import Path

# Manual integration test for the local project, never an external deployment.
# Uses a fresh disposable account and removes only its rows in finally.
root = Path(__file__).resolve().parents[1]
email = "aurora-live-" + uuid.uuid4().hex + "@example.org"
sfdk = str(root / "sdk/AuroraBT-5.2.1/Qt Creator.app/Contents/MacOS/sfdk")
key = str(root / "sdk/AuroraBT-5.2.1/vmshare/ssh/private_keys/sdk")
known = str(root / "sdk/emulator-known-hosts")
log_path = root / "artifacts/aurora-bt-check/emulator-live-api.log"
summary = {"platform": "Aurora 5.2.1 ARM64", "ui_automation": False}
cleanup = """
import os
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from database import get_engine
from models import User, Chat, Message, Run
from models.entities import AccessSession
email=os.environ['NIRS_CLEANUP_EMAIL']
assert email.startswith('aurora-live-') and email.endswith('@example.org')
with Session(get_engine()) as db:
 uid=db.scalar(select(User.id).where(User.email==email))
 if uid is not None:
  assert db.scalar(select(Run.id).where(Run.user_id==uid).limit(1)) is None
  chats=select(Chat.id).where(Chat.user_id==uid)
  db.execute(delete(Message).where(Message.chat_id.in_(chats)))
  db.execute(delete(Chat).where(Chat.user_id==uid))
  db.execute(delete(AccessSession).where(AccessSession.user_id==uid))
  db.execute(delete(User).where(User.id==uid))
  db.commit()
 print({'temporary_account_removed': uid is not None})
"""
try:
    subprocess.run(
        [
            "scp",
            "-q",
            "-P",
            "2223",
            "-o",
            "BatchMode=yes",
            "-o",
            "UserKnownHostsFile=" + known,
            "-i",
            key,
            str(root / "artifacts/aurora-bt-check/source/live-build/live-api-tests"),
            "defaultuser@127.0.0.1:/home/defaultuser/nirs-live-api-tests",
        ],
        cwd=root,
        check=True,
        timeout=30,
    )
    with log_path.open("w") as log:
        result = subprocess.run(
            [
                sfdk,
                "emulator",
                "exec",
                "--",
                "env",
                "NIRS_LIVE_API_URL=http://10.0.2.2:8000",
                "NIRS_LIVE_TEST_EMAIL=" + email,
                "/home/defaultuser/nirs-live-api-tests",
            ],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=180,
        )
    summary["test_exit_code"] = result.returncode
finally:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            "NIRS_CLEANUP_EMAIL=" + email,
            "app",
            "python",
            "-",
        ],
        input=cleanup,
        text=True,
        cwd=root,
        capture_output=True,
        timeout=30,
    )
    summary["temporary_data_cleanup_passed"] = result.returncode == 0
    if result.returncode:
        print("Cleanup requires retry for disposable account:", email)
    subprocess.run(
        [
            sfdk,
            "emulator",
            "exec",
            "--",
            "rm",
            "-f",
            "/home/defaultuser/nirs-live-api-tests",
        ],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    (root / "artifacts/validation/aurora-live-api-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
print(json.dumps(summary, ensure_ascii=False))
raise SystemExit(
    0
    if summary.get("test_exit_code") == 0
    and summary.get("temporary_data_cleanup_passed")
    else 1
)

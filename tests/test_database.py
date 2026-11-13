import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models import Artifact, Chat, Job, Message, Pipeline, Run, User


def create_run(session):
    user = User(email="database-test@example.invalid", password_hash="test-only")
    pipeline = Pipeline(name="Aurora client", workflow_file="portal.yml")
    session.add_all([user, pipeline])
    session.flush()
    run = Run(pipeline_id=pipeline.id, user_id=user.id, name="SDK build", branch="main")
    session.add(run)
    session.flush()
    return run


def test_run_lifecycle_and_related_records(session):
    run = create_run(session)
    assert run.status == "pending"
    assert run.external_run_id is None
    assert run.created_at.tzinfo is not None
    run.external_run_id = 98765432100
    run.status = "queued"
    session.flush()
    run.status = "completed"
    run.result = "succeeded"
    job = Job(run_id=run.id, external_job_id="123", name="Build")
    artifact = Artifact(run_id=run.id, name="RPM", external_artifact_id="456")
    chat = Chat(user_id=run.user_id, run_id=run.id)
    session.add_all([job, artifact, chat])
    session.flush()
    session.add(Message(chat_id=chat.id, role="user", content="Explain this build"))
    session.flush()
    session.expire_all()
    stored = session.scalar(select(Run).where(Run.id == run.id))
    assert stored.result == "succeeded"
    assert session.scalar(select(Message).where(Message.chat_id == chat.id)).content


def test_reject_result_before_completion(session):
    run = create_run(session)
    run.result = "succeeded"
    with pytest.raises(IntegrityError):
        session.flush()


def test_reject_missing_pipeline(session):
    run = create_run(session)
    run.pipeline_id = -1
    with pytest.raises(IntegrityError):
        session.flush()

"""Local GitHub Actions administration. Tokens are read only from settings."""

import argparse
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_engine
from models import Pipeline
from services.github import get_github


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    pipeline = commands.add_parser("add-pipeline")
    pipeline.add_argument("--workflow", required=True)
    pipeline.add_argument("--name", required=True)
    pipeline.add_argument("--description", default="Сборка и проверка клиента")
    pipeline.add_argument("--branch", default="main")
    pipeline.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.ya?ml", args.workflow):
        parser.error("Use a workflow filename such as aurora.yml")
    if args.verify:
        get_github().workflow(args.workflow)
    with Session(get_engine()) as db:
        record = db.scalar(
            select(Pipeline).where(Pipeline.workflow_file == args.workflow)
        )
        if record is None:
            record = Pipeline(workflow_file=args.workflow)
            db.add(record)
        record.name, record.description = args.name, args.description
        record.default_branch = args.branch
        db.commit()
        print(f"Pipeline saved: local={record.id}, workflow={record.workflow_file}")


if __name__ == "__main__":
    main()

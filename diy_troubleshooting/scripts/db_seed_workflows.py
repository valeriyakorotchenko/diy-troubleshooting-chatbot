"""
Database Seeder.

Run this script to populate the PostgreSQL database with the
hardcoded workflows defined in data/hardcoded_workflows.py.

Usage:
    python -m scripts.seed_db
"""
import os
import sys
from dataclasses import asdict

# Add the project root to the Python path for imports.
sys.path.append(os.getcwd())

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from diy_troubleshooting.data.hardcoded_workflows import HARDCODED_WORKFLOWS
from diy_troubleshooting.infrastructure.database.connection import engine, init_db
from diy_troubleshooting.infrastructure.database.tables import WorkflowDBModel

def seed_workflows():
    print("Initializing Database Connection...")

    # Create tables if they do not exist.
    init_db()

    with Session(engine) as session:
        print(f"Found {len(HARDCODED_WORKFLOWS)} workflows to seed.")

        for wf_id, workflow in HARDCODED_WORKFLOWS.items():
            print(f"Processing workflow: {wf_id}")

            # Serialize the workflow to a JSON-compatible dict using FastAPI's encoder.
            wf_data_json = jsonable_encoder(workflow)

            # Derive title from the workflow, falling back to a formatted name if missing.
            wf_title = getattr(workflow, "title", workflow.name.replace("_", " ").title())

            # Upsert logic: update existing records or insert new ones.
            statement = select(WorkflowDBModel).where(WorkflowDBModel.workflow_id == wf_id)
            existing_wf = session.exec(statement).first()

            if existing_wf:
                print(f"--> Updating existing record.")
                existing_wf.title = wf_title
                existing_wf.workflow_data = wf_data_json
                session.add(existing_wf)
            else:
                print(f"--> Creating new record.")
                new_wf = WorkflowDBModel(
                    workflow_id=wf_id,
                    title=wf_title,
                    workflow_data=wf_data_json
                )
                session.add(new_wf)

        session.commit()
        print("Workflows seeding complete.")

if __name__ == "__main__":
    seed_workflows()
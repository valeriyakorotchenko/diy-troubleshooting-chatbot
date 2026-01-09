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

# Ensure the project root is in python path
sys.path.append(os.getcwd())

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from diy_troubleshooting.data.hardcoded_workflows import HARDCODED_WORKFLOWS
from diy_troubleshooting.infrastructure.database.connection import engine, init_db
from diy_troubleshooting.infrastructure.database.tables import WorkflowDBModel

def seed_workflows():
    print("Initializing Database Connection...")

    # Create tables if they don't exist
    init_db()

    with Session(engine) as session:
        print(f"Found {len(HARDCODED_WORKFLOWS)} workflows to seed.")

        for wf_id, workflow in HARDCODED_WORKFLOWS.items():
            print(f"Processing workflow: {wf_id}")

            # Serialize the Dataclass to JSON-compatible dict
            # jsonable_encoder handles nested objects, UUIDs, Enums, etc.
            wf_data_json = jsonable_encoder(workflow)

            # Derive Title (Fallback to name if title field missing in dataclass)
            wf_title = getattr(workflow, "title", workflow.name.replace("_", " ").title())

            # Check for existing record, update if exists, insert if not (Upsert Logic)
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
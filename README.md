## Getting Started

Install the requirements. In the root directory, run:

```bash
pip install -r requirements.txt
```

### Environment Configuration

Create a `.env` file in the root directory of the project:

```bash
touch .env
```

Add the following configuration (adjust the API key as needed):

```ini
# .env
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4-turbo
DATABASE_URL=postgresql://diy_user:diy_password@localhost:5432/diy_troubleshooting
```

### Database Setup

We use Docker to run a local instance of PostgreSQL and a Python script to seed it with initial data.

**Start the Database Container**
Run the following command to spin up the Postgres service in the background:
```bash
docker-compose up -d
```
*Wait a few seconds for the database to initialize.*

**Seed the Database**
Run the seeding script to create the tables and populate the hardcoded troubleshooting workflows (e.g., "Lukewarm Water"):
```bash
python -m scripts.seed_db
```
*Expected Output:* `Seeding Complete.`

### Running the Application

Start the FastAPI server using Uvicorn:

```bash
uvicorn diy_troubleshooting.app.main:app --reload
```

The API will be accessible at: `http://localhost:8000`

### Verification

You can verify the setup by visiting the interactive Swagger UI documentation:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

Or test the health of the system by creating a new session via curl:

```bash
curl -X POST "http://localhost:8000/sessions"
# Should return: {"session_id": "uuid..."}
```

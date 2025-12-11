# diy-troubleshooting-chatbot

Here are the step-by-step instructions for running the server and testing the endpoints. You can include this in your `README.md` or just follow along to verify the system works.

### **1. Environment Setup**

First, ensure your environment is configured correctly.

1.  **Create the `.env` file** in your project root (`diy-troubleshooting-chatbot/`) and add your API key:

    ```bash
    OPENAI_API_KEY=sk-proj-...
    ```

2.  **Install Dependencies:**
    Make sure you have all the required packages installed.

    ```bash
    pip install fastapi uvicorn openai pydantic pydantic-settings
    ```

### **2. Running the Server**

Start the FastAPI server from the project root directory.

```bash
# Run from the root folder (diy-troubleshooting-chatbot/)
uvicorn diy_troubleshooting.api.main:app --reload
```

  * `--reload`: Enabling this flag ensures the server automatically restarts whenever you make code changes.
  * You should see output indicating the server is running at `http://127.0.0.1:8000`.

### **3. Testing the Endpoints**

You can test the API using `curl` commands in your terminal or by using the built-in Swagger UI.

#### **Option A: Using Swagger UI (Recommended)**

FastAPI provides an interactive UI to test endpoints easily.

1.  Open your browser and navigate to: `http://127.0.0.1:8000/docs`
2.  **Create a Session:**
      * Click on **`POST /sessions`**.
      * Click **Try it out** -\> **Execute**.
      * Copy the `session_id` from the response body (e.g., `"session_id": "abc-123..."`).
3.  **Send a Message:**
      * Click on **`POST /sessions/{session_id}/messages`**.
      * Click **Try it out**.
      * Paste your `session_id` into the path field.
      * In the Request Body, enter: `{"text": "My shower water is lukewarm"}`.
      * Click **Execute**.
      * You should receive a JSON response with the agent's reply.

#### **Option B: Using CURL (Terminal)**

**Step 1: Create a Session**

```bash
curl -X POST "http://127.0.0.1:8000/sessions"
```

  * *Copy the ID returned in the JSON response.*

**Step 2: Start the Workflow**
Replace `{SESSION_ID}` with the ID you copied.

```bash
curl -X POST "http://127.0.0.1:8000/sessions/{SESSION_ID}/messages" \
     -H "Content-Type: application/json" \
     -d '{"text": "My shower water is lukewarm"}'
```

**Step 3: Continue the Conversation**
Use the same command with your next reply:

```bash
curl -X POST "http://127.0.0.1:8000/sessions/{SESSION_ID}/messages" \
     -H "Content-Type: application/json" \
     -d '{"text": "I checked it, it is set to 120."}'
```

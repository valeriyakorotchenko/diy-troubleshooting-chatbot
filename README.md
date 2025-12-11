# diy-troubleshooting-chatbot

### **Environment Setup**

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

### **Running the Server**

Start the FastAPI server from the project root directory.

```bash
# Run from the root folder (diy-troubleshooting-chatbot/)
uvicorn diy_troubleshooting.api.main:app --reload
```

  * `--reload`: Enabling this flag ensures the server automatically restarts whenever you make code changes.
  * You should see output indicating the server is running at `http://127.0.0.1:8000`.

### **Testing the Endpoints**

You can test the API using `curl` commands in your terminal or by using the built-in Swagger UI.

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

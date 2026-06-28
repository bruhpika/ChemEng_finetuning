import unittest
from fastapi.testclient import TestClient
import app

class TestBackendStatus(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)
        # Backup original globals
        self.orig_retriever_load_attempted = app._retriever_load_attempted
        self.orig_model_load_attempted = app._model_load_attempted
        self.orig_model_mode = app._model_mode
        self.orig_retriever = app._retriever
        self.orig_model = app._model

    def tearDown(self):
        # Restore original globals
        app._retriever_load_attempted = self.orig_retriever_load_attempted
        app._model_load_attempted = self.orig_model_load_attempted
        app._model_mode = self.orig_model_mode
        app._retriever = self.orig_retriever
        app._model = self.orig_model

    def test_status_loading(self):
        # Mocking loading state
        app._retriever_load_attempted = False
        app._model_load_attempted = False
        
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "loading")
        self.assertEqual(data["retriever_ready"], False)
        self.assertEqual(data["model_ready"], False)

        # Chat should return 503 during loading
        chat_response = self.client.post("/api/chat", json={"question": "What is DWSIM?", "software": "DWSIM"})
        self.assertEqual(chat_response.status_code, 503)
        self.assertIn("Model is currently loading", chat_response.json()["detail"])

    def test_status_fallback(self):
        # Mocking fallback state (RAG-only)
        app._retriever_load_attempted = True
        app._model_load_attempted = True
        app._model_mode = "rag_only"
        app._retriever = object() # Not None
        app._model = None
        
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "fallback")
        self.assertEqual(data["mode"], "rag_only")
        self.assertEqual(data["retriever_ready"], True)
        self.assertEqual(data["model_ready"], False)

    def test_status_ready_base(self):
        # Mocking ready state with base model
        app._retriever_load_attempted = True
        app._model_load_attempted = True
        app._model_mode = "base"
        app._retriever = object()
        app._model = object()
        
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["mode"], "base")
        self.assertEqual(data["retriever_ready"], True)
        self.assertEqual(data["model_ready"], True)

if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
E2E Test Suite for verifying the model loading state UX of the ChemE-LLM application.
This script launches the FastAPI backend in a separate process, passes MOCK_MODEL_LOADING_TIME=5
to it, and performs four tiers of E2E verification:
Tier 1: Loading state UX coverage (GET /api/status -> 200 loading, POST /api/chat -> 503 error)
Tier 2: Boundary UX (Wait for loading, GET /api/status -> 200 ready/fallback, POST /api/chat -> 200 ok)
Tier 3: Concurrent requests during loading (Fire multiple parallel requests -> all return 503 quickly without blocking)
Tier 4: Seamless transition (Launch, poll until ready, first request succeeds)
"""

import os
import sys
import time
import subprocess
import json
import concurrent.futures
import requests

# Port configurations
PORT_TEST_1_2 = 8081
PORT_TEST_3 = 8082
PORT_TEST_4 = 8083

# Payloads
CHAT_PAYLOAD = {"question": "What is DWSIM?", "software": "DWSIM"}

def clean_log_files():
    """Remove any existing log files from previous runs."""
    for port in [PORT_TEST_1_2, PORT_TEST_3, PORT_TEST_4]:
        for prefix in ["stdout", "stderr"]:
            path = f"backend_{port}_{prefix}.log"
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

def launch_backend(port, loading_time=5):
    """Launch the FastAPI server in a background process."""
    print(f"\n[Harness] Launching FastAPI backend on port {port} with MOCK_MODEL_LOADING_TIME={loading_time}...")
    env = os.environ.copy()
    env["MOCK_MODEL_LOADING_TIME"] = str(loading_time)
    
    stdout_path = f"backend_{port}_stdout.log"
    stderr_path = f"backend_{port}_stderr.log"
    
    stdout_file = open(stdout_path, "w", encoding="utf-8")
    stderr_file = open(stderr_path, "w", encoding="utf-8")
    
    # Run uvicorn on localhost/127.0.0.1
    # We use sys.executable -m uvicorn app:app to run inside the same python environment
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=stdout_file,
        stderr=stderr_file
    )
    
    return process, stdout_file, stderr_file, stdout_path, stderr_path

def shutdown_backend(process, stdout_file, stderr_file, stdout_path, stderr_path, clean_on_success=False):
    """Gracefully terminate backend and close file logs."""
    print(f"[Harness] Shutting down backend on PID {process.pid if process else 'unknown'}...")
    if process:
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("[Harness] Backend failed to terminate within 5 seconds. Force killing...")
                process.kill()
                process.wait()
        except Exception as e:
            print(f"[Harness] Error while killing backend process: {e}")
            
    if stdout_file:
        try:
            stdout_file.close()
        except Exception:
            pass
    if stderr_file:
        try:
            stderr_file.close()
        except Exception:
            pass

    # Print a snippet of logs if things went wrong
    if not clean_on_success:
        try:
            if os.path.exists(stderr_path):
                with open(stderr_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        print(f"\n--- Backend (port {stderr_path.split('_')[1]}) STDERR logs snippet ---")
                        print("\n".join(content.splitlines()[-30:]))
                        print("------------------------------------------\n")
            if os.path.exists(stdout_path):
                with open(stdout_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        print(f"\n--- Backend (port {stdout_path.split('_')[1]}) STDOUT logs snippet ---")
                        print("\n".join(content.splitlines()[-30:]))
                        print("------------------------------------------\n")
        except Exception as e:
            print(f"[Harness] Could not print backend logs: {e}")
    else:
        # Delete logs on success
        try:
            os.remove(stdout_path)
            os.remove(stderr_path)
        except Exception:
            pass

def wait_for_server(port, timeout=10):
    """Wait for the server to be responsive to HTTP requests."""
    url = f"http://127.0.0.1:{port}"
    print(f"[Harness] Waiting for server at {url} to respond (timeout={timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # We hit /api/status. Connection success (even if 404 or 503) means uvicorn is listening.
            requests.get(f"{url}/api/status", timeout=1)
            print(f"[Harness] Server is listening at {url}.")
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.2)
    print(f"[Harness] Server at {url} did not respond within {timeout} seconds.")
    return False

def run_test_1_and_2():
    """Run verification for Tier 1 and Tier 2."""
    print("\n" + "="*80)
    print("STARTING TEST RUN 1: TIER 1 (Loading State UX) & TIER 2 (Post-Loading UX)")
    print("="*80)
    
    port = PORT_TEST_1_2
    url = f"http://127.0.0.1:{port}"
    process, stdout_file, stderr_file, stdout_path, stderr_path = launch_backend(port, loading_time=5)
    
    success = False
    try:
        if not wait_for_server(port):
            raise AssertionError("Server failed to start or respond in time.")
            
        # --- Tier 1 (Feature Coverage: Loading State UX) ---
        print("\n--- [Tier 1] Feature Coverage: Loading State UX ---")
        
        # 1. GET /api/status
        status_url = f"{url}/api/status"
        print(f"Sending GET {status_url}...")
        res_status = requests.get(status_url, timeout=5)
        print(f"Response status code: {res_status.status_code}")
        print(f"Response JSON: {res_status.text}")
        
        if res_status.status_code != 200:
            raise AssertionError(f"Tier 1 GET /api/status: Expected status code 200, got {res_status.status_code}")
            
        try:
            status_json = res_status.json()
        except Exception as e:
            raise AssertionError(f"Tier 1 GET /api/status: Response is not valid JSON: {e}")
            
        for field in ["status", "mode", "retriever_ready", "model_ready"]:
            if field not in status_json:
                raise AssertionError(f"Tier 1 GET /api/status: Missing contract field '{field}' in response")
                
        if status_json["status"] != "loading":
            raise AssertionError(f"Tier 1 GET /api/status: Expected status to be 'loading', got '{status_json['status']}'")
            
        # 2. POST /api/chat during loading
        chat_url = f"{url}/api/chat"
        print(f"Sending POST {chat_url} during loading state...")
        res_chat = requests.post(chat_url, json=CHAT_PAYLOAD, timeout=5)
        print(f"Response status code: {res_chat.status_code}")
        print(f"Response JSON: {res_chat.text}")
        
        if res_chat.status_code != 503:
            raise AssertionError(f"Tier 1 POST /api/chat: Expected status code 503 Service Unavailable, got {res_chat.status_code}")
            
        try:
            chat_json = res_chat.json()
        except Exception as e:
            raise AssertionError(f"Tier 1 POST /api/chat: Response is not valid JSON: {e}")
            
        if "detail" not in chat_json:
            raise AssertionError("Tier 1 POST /api/chat: Expected 'detail' field in response")
            
        expected_detail = "Model is currently loading. Please try again shortly."
        if chat_json["detail"] != expected_detail:
            raise AssertionError(f"Tier 1 POST /api/chat: Expected detail '{expected_detail}', got '{chat_json['detail']}'")
            
        print("[Tier 1] Verification passed successfully! ✅")
        
        # --- Tier 2 (Boundary & Corner Cases: Post-Loading Normal UX) ---
        print("\n--- [Tier 2] Boundary & Corner Cases: Post-Loading UX ---")
        
        print("Polling /api/status until status is 'ready' or 'fallback'...")
        start_poll = time.time()
        ready = False
        while time.time() - start_poll < 15:
            res_status_poll = requests.get(status_url, timeout=2)
            if res_status_poll.status_code == 200:
                js = res_status_poll.json()
                print(f"Polled status: '{js.get('status')}' (elapsed: {time.time() - start_poll:.1f}s)")
                if js.get("status") in ["ready", "fallback"]:
                    ready = True
                    break
            time.sleep(0.5)
            
        if not ready:
            raise AssertionError("Tier 2: Server did not transition to 'ready' or 'fallback' status within 15 seconds")
            
        # Verify status is correct
        res_status_final = requests.get(status_url, timeout=5)
        status_final_json = res_status_final.json()
        if status_final_json["status"] not in ["ready", "fallback"]:
            raise AssertionError(f"Tier 2: Expected ready/fallback status, got '{status_final_json['status']}'")
            
        # Perform chat request post-loading
        print("Sending POST /api/chat post-loading...")
        res_chat_final = requests.post(chat_url, json=CHAT_PAYLOAD, timeout=10)
        print(f"Response status code: {res_chat_final.status_code}")
        print(f"Response JSON keys: {list(res_chat_final.json().keys()) if res_chat_final.status_code == 200 else res_chat_final.text}")
        
        if res_chat_final.status_code != 200:
            raise AssertionError(f"Tier 2 POST /api/chat: Expected status code 200, got {res_chat_final.status_code}")
            
        chat_final_json = res_chat_final.json()
        for field in ["answer", "sources_md", "mode", "sources"]:
            if field not in chat_final_json:
                raise AssertionError(f"Tier 2 POST /api/chat: Missing expected field '{field}' in response")
                
        print("[Tier 2] Verification passed successfully! ✅")
        success = True
        
    finally:
        shutdown_backend(process, stdout_file, stderr_file, stdout_path, stderr_path, clean_on_success=success)
        
    return success

def run_test_3():
    """Run verification for Tier 3: Concurrent requests during loading."""
    print("\n" + "="*80)
    print("STARTING TEST RUN 2: TIER 3 (Concurrent Request Handling During Loading)")
    print("="*80)
    
    port = PORT_TEST_3
    url = f"http://127.0.0.1:{port}"
    # Use 10 seconds loading time to make sure we don't accidentally finish loading before sending requests
    process, stdout_file, stderr_file, stdout_path, stderr_path = launch_backend(port, loading_time=10)
    
    success = False
    try:
        if not wait_for_server(port):
            raise AssertionError("Server failed to start or respond in time.")
            
        print("\n--- [Tier 3] Cross-Feature Combinations: Concurrent Request Handling ---")
        chat_url = f"{url}/api/chat"
        
        def send_chat_request(req_id):
            try:
                t0 = time.time()
                res = requests.post(chat_url, json=CHAT_PAYLOAD, timeout=5)
                duration = time.time() - t0
                return req_id, res.status_code, res.text, duration, None
            except Exception as e:
                return req_id, None, None, 0, e

        num_requests = 5
        print(f"Firing {num_requests} concurrent chat requests during loading state...")
        
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(send_chat_request, i+1) for i in range(num_requests)]
            results = [f.result() for f in futures]
        total_time = time.time() - start_time
        
        print(f"All concurrent requests returned in {total_time:.3f} seconds.")
        
        for req_id, status_code, text, duration, err in results:
            print(f"Request {req_id}: status={status_code}, duration={duration:.3f}s, error={err}")
            if err is not None:
                raise AssertionError(f"Request {req_id} failed with exception: {err}")
            if status_code != 503:
                raise AssertionError(f"Request {req_id} got status {status_code}, expected 503")
                
            try:
                js = json.loads(text)
            except Exception as e:
                raise AssertionError(f"Request {req_id} response is not valid JSON: {e}")
                
            if js.get("detail") != "Model is currently loading. Please try again shortly.":
                raise AssertionError(f"Request {req_id} detail mismatch: '{js.get('detail')}'")
                
        print("[Tier 3] Verification passed successfully! ✅")
        success = True
        
    finally:
        shutdown_backend(process, stdout_file, stderr_file, stdout_path, stderr_path, clean_on_success=success)
        
    return success

def run_test_4():
    """Run verification for Tier 4: Seamless transition."""
    print("\n" + "="*80)
    print("STARTING TEST RUN 3: TIER 4 (Seamless Transition)")
    print("="*80)
    
    port = PORT_TEST_4
    url = f"http://127.0.0.1:{port}"
    process, stdout_file, stderr_file, stdout_path, stderr_path = launch_backend(port, loading_time=5)
    
    success = False
    try:
        if not wait_for_server(port):
            raise AssertionError("Server failed to start or respond in time.")
            
        print("\n--- [Tier 4] Real-World Application Scenarios: Seamless Transition ---")
        status_url = f"{url}/api/status"
        chat_url = f"{url}/api/chat"
        
        # Poll until transitions
        print("Polling /api/status until status is ready/fallback...")
        start_poll = time.time()
        ready = False
        while time.time() - start_poll < 15:
            res = requests.get(status_url, timeout=2)
            if res.status_code == 200:
                js = res.json()
                print(f"Polled status: '{js.get('status')}' (elapsed: {time.time() - start_poll:.1f}s)")
                if js.get("status") in ["ready", "fallback"]:
                    ready = True
                    break
            time.sleep(0.5)
            
        if not ready:
            raise AssertionError("Tier 4: Server did not transition to ready/fallback within 15 seconds")
            
        # Verify the FIRST request immediately after transition succeeds
        print("Sending the first POST /api/chat request immediately after transition...")
        res_chat = requests.post(chat_url, json=CHAT_PAYLOAD, timeout=10)
        print(f"Response status code: {res_chat.status_code}")
        print(f"Response JSON keys: {list(res_chat.json().keys()) if res_chat.status_code == 200 else res_chat.text}")
        
        if res_chat.status_code != 200:
            raise AssertionError(f"Tier 4 POST /api/chat: Expected status code 200 immediately after transition, got {res_chat.status_code}")
            
        chat_json = res_chat.json()
        for field in ["answer", "sources_md", "mode", "sources"]:
            if field not in chat_json:
                raise AssertionError(f"Tier 4 POST /api/chat: Missing expected field '{field}' in response")
                
        print("[Tier 4] Verification passed successfully! ✅")
        success = True
        
    finally:
        shutdown_backend(process, stdout_file, stderr_file, stdout_path, stderr_path, clean_on_success=success)
        
    return success

def main():
    clean_log_files()
    
    print("="*80)
    print("ChemE-LLM E2E Loading State UX Test Suite")
    print("="*80)
    
    try:
        t1_t2_success = run_test_1_and_2()
        t3_success = run_test_3()
        t4_success = run_test_4()
        
        if t1_t2_success and t3_success and t4_success:
            print("\n" + "="*80)
            print("ALL TIERS PASSED SUCCESSFULLY! E2E SUITE SUCCESS ✅")
            print("="*80)
            sys.exit(0)
        else:
            print("\n" + "="*80)
            print("SOME TIERS FAILED. E2E SUITE FAILED ❌")
            print("="*80)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n[Harness] Test execution aborted with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

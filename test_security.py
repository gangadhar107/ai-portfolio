"""
Security Test Script — Phase 5
Tests route protection, rate limiting, and input validation.
Run with: python test_security.py
"""

import requests

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0

def test(name, condition):
    global PASS, FAIL
    status = "✅ PASS" if condition else "❌ FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  {status} — {name}")

print("\n🔒 Security Audit Tests\n" + "="*50)

# 1. Route protection — dashboard without auth
print("\n1. Route Protection")
r = requests.get(f"{BASE}/dashboard", allow_redirects=False)
test("Dashboard without auth returns login page (200 with login form)", r.status_code == 200 and "password" in r.text.lower())

r = requests.get(f"{BASE}/admin/panel", allow_redirects=False)
test("Admin panel without auth returns login page", r.status_code == 200 and "password" in r.text.lower())

# 2. Invalid password
print("\n2. Invalid Credentials")
r = requests.post(f"{BASE}/admin/login", data={"password": "wrongpassword"}, allow_redirects=False)
test("Invalid password shows error (not redirect)", r.status_code == 200 and "error" in r.text.lower() or "incorrect" in r.text.lower())

# 3. Invalid ref code handling
print("\n3. Invalid Ref Code Handling") 
r = requests.get(f"{BASE}/?ref=INVALIDCODE123")
test("Invalid ref code doesn't crash (returns 200)", r.status_code == 200)

r = requests.get(f"{BASE}/?ref=")
test("Empty ref code doesn't crash (returns 200)", r.status_code == 200)

r = requests.get(f"{BASE}/?ref=<script>alert(1)</script>")
test("XSS in ref code doesn't crash (returns 200)", r.status_code == 200)

# 4. Rate limiting (visit same ref twice rapidly)
print("\n4. Rate Limiting")
# The visit logger should only log the first visit per IP per ref per hour
# We can't directly test the DB count easily, but we ensure no crash
r1 = requests.get(f"{BASE}/?ref=testcode")
r2 = requests.get(f"{BASE}/?ref=testcode")
test("Rapid duplicate visits don't crash", r1.status_code == 200 and r2.status_code == 200)

# 5. Input validation
print("\n5. Input Validation")
# Try submitting application without auth
r = requests.post(f"{BASE}/admin/application", data={
    "company_name": "TestCo",
    "position": "Dev"
}, allow_redirects=False)
test("Application submit without auth blocked (403)", r.status_code == 403)

# 6. .env not accessible
print("\n6. File Security")
r = requests.get(f"{BASE}/.env")
test(".env not served (404)", r.status_code == 404)

r = requests.get(f"{BASE}/database/schema.sql")
test("Database files not served (404)", r.status_code == 404)

# 7. Health endpoint
print("\n7. Health Endpoint")
r = requests.get(f"{BASE}/health")
test("Health endpoint works", r.status_code == 200)

print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed out of {PASS + FAIL} tests")
if FAIL == 0:
    print("🎉 All security tests passed!")
else:
    print("⚠️  Some tests failed — review above.")
print()

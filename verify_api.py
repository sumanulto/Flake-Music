
import urllib.request
import urllib.error

# Configuration
API_URL = "http://localhost:8000/api/v1/allowed-guilds/"

def test_endpoints():
    print(f"Testing {API_URL} endpoint...")
    try:
        req = urllib.request.Request(API_URL)
        with urllib.request.urlopen(req) as response:
            print(f"GET /allowed-guilds/ status: {response.getcode()}")
            print("SUCCESS: Endpoint exists and is accessible.")
    except urllib.error.HTTPError as e:
        print(f"GET /allowed-guilds/ status: {e.code}")
        if e.code == 404:
            print("FAILED: Endpoint not found.")
        elif e.code == 401:
            print("SUCCESS: Endpoint exists and is protected (401 Unauthorized expected without token).")
        else:
            print(f"unknown status: {e.code}")
    except urllib.error.URLError as e:
        print(f"Error connecting to API: {e.reason}")
    except Exception as e:
        print(f"An error occurred: {e}")

def test_auth_guilds():
    url = "http://localhost:8000/api/v1/auth/guilds"
    print(f"Testing {url} endpoint...")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            print(f"GET /auth/guilds status: {response.getcode()}")
    except urllib.error.HTTPError as e:
        print(f"GET /auth/guilds status: {e.code}")
        if e.code == 404:
            print("FAILED: Endpoint not found.")
        elif e.code == 401:
            print("SUCCESS: Endpoint exists and is protected (401 Unauthorized expected without token).")
        else:
            print(f"unknown status: {e.code}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_endpoints()
    test_auth_guilds()

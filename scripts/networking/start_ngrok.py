import json
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "config" / "elastic.config.json"

LOCAL_PORT = 8000
NGROK_API = "http://127.0.0.1:4040/api/tunnels"


def check_fastapi():
    url = f"http://localhost:{LOCAL_PORT}/health"

    try:
        with urlopen(url, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError("FastAPI health check failed.")
    except URLError as exc:
        raise RuntimeError(
            f"FastAPI is not reachable at {url}. "
            "Start Uvicorn before running this script."
        ) from exc


def get_ngrok_public_url():
    for _ in range(20):
        try:
            with urlopen(NGROK_API, timeout=2) as response:
                data = json.load(response)

            for tunnel in data.get("tunnels", []):
                public_url = tunnel.get("public_url", "")

                if public_url.startswith("https://"):
                    return public_url

        except URLError:
            pass

        time.sleep(1)

    raise RuntimeError("Could not get ngrok public URL.")


def update_elastic_config(public_url):
    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = json.load(f)

    config["webhook_url"] = (
        f"{public_url.rstrip('/')}/webhooks/elastic"
    )

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    return config["webhook_url"]


def main():
    check_fastapi()
    print("FastAPI is healthy.")

    process = subprocess.Popen(
        ["ngrok", "http", str(LOCAL_PORT)],
      #   stdout=subprocess.DEVNULL,
      #   stderr=subprocess.DEVNULL,
    )

    try:
        public_url = get_ngrok_public_url()
        webhook_url = update_elastic_config(public_url)

        print(f"ngrok URL:    {public_url}")
        print(f"Webhook URL:  {webhook_url}")
        print("Elastic config updated.")
        print()
        print("ngrok is running. Press Ctrl+C to stop.")

        process.wait()

    except KeyboardInterrupt:
        print("\nStopping ngrok...")

    finally:
        process.terminate()
        process.wait()


if __name__ == "__main__":
    main()
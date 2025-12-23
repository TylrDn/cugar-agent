import json
import sys


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            if payload.get("method") == "health":
                result = {"result": "ok"}
            else:
                result = {"result": payload.get("params")}
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"result": None, "error": "bad json"}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

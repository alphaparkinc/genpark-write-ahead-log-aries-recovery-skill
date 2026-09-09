import sys
import json
from client import ARIESRecoveryEngine

def handle_request(req):
    method = req.get("method")
    params = req.get("params", {})
    if method == "simulate_recovery":
        engine = ARIESRecoveryEngine()
        engine.begin_tx(1)
        engine.update_page(1, "p1", 0, 100)
        engine.commit_tx(1)
        engine.begin_tx(2)
        engine.update_page(2, "p2", 0, 200)
        engine.crash()
        return engine.recover()
    return {"error": "Unknown method"}

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        res = handle_request(req)
        print(json.dumps(res))
        sys.stdout.flush()

if __name__ == '__main__':
    main()

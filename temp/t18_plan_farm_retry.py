import json
import subprocess
from multiprocessing import Pool

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["title", "steps"]
}

def run_plan(task_desc: str):
    prompt = (
        f"Create an implementation plan for: {task_desc}. "
        "Return ONLY JSON object that matches schema. "
        "No markdown, no extra text."
    )
    cmd = [
        "npx", "claude", "-p", prompt,
        "--permission-mode", "plan",
        "--tools", "Read,Grep,Glob",
        "--output-format", "json",
        "--json-schema", json.dumps(SCHEMA)
    ]
    attempts = []
    for i in range(1, 4):
        cp = subprocess.run(
            cmd,
            text=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=180
        )
        attempts.append({"attempt": i, "returncode": cp.returncode})
        if cp.returncode == 0:
            payload = json.loads(cp.stdout)
            return {
                "task": task_desc,
                "ok": True,
                "returncode": cp.returncode,
                "num_turns": payload.get("num_turns"),
                "result_preview": str(payload.get("result", ""))[:180],
                "attempts": attempts
            }
    return {
        "task": task_desc,
        "ok": False,
        "returncode": attempts[-1]["returncode"],
        "attempts": attempts,
        "stderr_preview": cp.stderr[:180],
        "stdout_preview": cp.stdout[:240]
    }

if __name__ == "__main__":
    tasks = ["add logging", "add error handling", "add input validation"]
    with Pool(3) as p:
        results = p.map(run_plan, tasks)
    with open("temp/T18_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))

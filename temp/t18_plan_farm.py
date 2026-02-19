import json
import subprocess
from multiprocessing import Pool

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "estimate": {"type": "string"}
    },
    "required": ["title", "steps"]
}

def run_plan(task_desc: str):
    cmd = [
        "npx", "claude",
        "-p", f"Plan how to: {task_desc}",
        "--permission-mode", "plan",
        "--tools", "Read,Grep,Glob",
        "--output-format", "json",
        "--json-schema", json.dumps(SCHEMA)
    ]
    out = subprocess.check_output(
        cmd,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=180
    )
    payload = json.loads(out)
    return {
        "task": task_desc,
        "type": payload.get("type"),
        "is_error": payload.get("is_error"),
        "num_turns": payload.get("num_turns"),
        "result_preview": str(payload.get("result", ""))[:180]
    }

if __name__ == "__main__":
    tasks = ["add logging", "add error handling", "add input validation"]
    with Pool(3) as p:
        results = p.map(run_plan, tasks)
    with open("temp/T18_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))

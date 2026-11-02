"""Spike #43 bench: ask a worker model questions about a file corpus; record tokens, cost, latency, answer.
Usage: python3 -I bench.py <corpus.txt> <system.txt> <out.json> claude:<model> | ollama:<model>
"""
import json
import subprocess
import sys
import time
import urllib.request

QUESTIONS = {
    "q1_git": "List every function (def) that itself calls subprocess to run `git` (the list passed to subprocess starts with \"git\"). Give function name, file and the line of its `def`.",
    "q2_config": "List every project.toml setting these files read through `project().get(...)` or `wf.project().get(...)`: section.key, the default value used when it is missing, and file:line.",
    "q3_deny": "In tools/gate_guard.py, list every rule of SHELL_DENY: its reason text (the second element) verbatim and the line number where that reason appears.",
}


def ask_claude(model, system, prompt):
    t = time.time()
    r = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", "--system-prompt", system, "--tools", "",
                        "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence"],
                       input=prompt, capture_output=True, text=True, timeout=300, env={**__import__("os").environ, "MAX_THINKING_TOKENS": "0"})
    d = json.loads(r.stdout)
    u = d["usage"]
    return {"answer": d["result"], "seconds": round(time.time() - t, 1), "cost_usd": d["total_cost_usd"], "model": list(d.get("modelUsage", {})),
            "input": u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"], "output": u["output_tokens"]}


def ask_ollama(model, system, prompt):
    t = time.time()
    body = json.dumps({"model": model, "stream": False, "options": {"num_ctx": 49152, "temperature": 0.2},
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", body, {"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=1200))
    return {"answer": d["message"]["content"], "seconds": round(time.time() - t, 1), "cost_usd": 0.0,
            "input": d.get("prompt_eval_count"), "output": d.get("eval_count")}


def main():
    corpus, system, out, worker = open(sys.argv[1]).read(), open(sys.argv[2]).read(), sys.argv[3], sys.argv[4]
    backend, model = worker.split(":", 1)
    res = {"worker": worker, "corpus_chars": len(corpus)}
    for q, text in QUESTIONS.items():
        prompt = f"{corpus}\n\nQuestion: {text}"
        try:
            res[q] = (ask_claude if backend == "claude" else ask_ollama)(model, system, prompt)
        except Exception as e:  # keep the other questions
            res[q] = {"error": repr(e)}
        print(q, {k: v for k, v in res[q].items() if k != "answer"}, flush=True)
    json.dump(res, open(out, "w"), indent=2)


if __name__ == "__main__":
    main()

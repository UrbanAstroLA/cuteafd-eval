#!/usr/bin/env python3
"""Compare the capture launch rendered by `DRY_RUN=1 start-v092-capture.sh`
with the served container (read-only `docker inspect`).

usage: compare_launch.py launch-dryrun.txt [container]
"""
import json
import subprocess
import sys


def parse_run(path):
    args = [l.split("\t", 1)[1].rstrip("\n") for l in open(path) if l.startswith("DOCKER-RUN-ARG\t")]
    assert args[0] == "run", args[:3]
    a = args[1:]
    opts, env, vols, i = {}, {}, [], 0
    while i < len(a) and a[i].startswith("--"):
        k = a[i]
        if "=" in k:
            n, _, v = k.partition("=")
            opts[n] = v
            i += 1
            continue
        if k in ("--detach", "--init"):
            opts[k] = True
            i += 1
            continue
        v = a[i + 1]
        if k == "--env":
            n, _, val = v.partition("=")
            env[n] = val
        elif k == "--volume":
            vols.append(v)
        else:
            opts[k] = v
        i += 2
    return opts, env, vols, a[i], a[i + 1:]


def main():
    dry = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else "glm53-flash-exl3-b12x-vllm"
    ins = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
    img_env = dict(e.split("=", 1) for e in json.loads(subprocess.check_output(
        ["docker", "image", "inspect", ins["Image"], "--format", "{{json .Config.Env}}"])))
    opts, env, vols, image, serve = parse_run(dry)
    run_env = dict(e.split("=", 1) for e in ins["Config"]["Env"])
    served_explicit = {k: v for k, v in run_env.items() if img_env.get(k) != v}
    diffs = []

    def cmp(label, a, b):
        same = a == b
        print(f"{'same' if same else 'DIFF':4s}  {label}: {'' if same else f'served={a!r} capture={b!r}'}")
        if not same:
            diffs.append(label)

    cmp("image", ins["Image"], image)
    cmp("serve args", ins["Args"], serve)
    cmp("container name", ins["Name"].lstrip("/"), opts.get("--name"))
    pb = ins["HostConfig"]["PortBindings"]["8001/tcp"][0]
    cmp("port binding", f"{pb['HostIp']}:{pb['HostPort']}:8001", opts.get("--publish"))
    cmp("restart policy", ins["HostConfig"]["RestartPolicy"]["Name"], opts.get("--restart"))
    cmp("gpus", "all", opts.get("--gpus"))
    cmp("ipc / shm", (ins["HostConfig"]["IpcMode"], ins["HostConfig"]["ShmSize"]),
        (opts.get("--ipc"), 32 * 1024 ** 3 if opts.get("--shm-size") == "32g" else opts.get("--shm-size")))
    served_vols = ins["HostConfig"]["Binds"]
    extra_vols = [v for v in vols if v not in served_vols]
    missing_vols = [v for v in served_vols if v not in vols]
    print(f"{'same' if not missing_vols else 'DIFF':4s}  served mounts all present: missing={missing_vols}")
    print(f"note  extra mounts (expected 3, all /kld-*): {extra_vols}")
    if missing_vols or len(extra_vols) != 3 or not all(":/kld-" in v for v in extra_vols):
        diffs.append("mounts")
    # env: explicit --env of the served run vs capture
    keys = sorted(set(served_explicit) | set(env))
    env_diff = {k: (served_explicit.get(k, img_env.get(k)), env.get(k)) for k in keys
                if served_explicit.get(k, img_env.get(k)) != env.get(k)}
    expected = {"VLLM_PLUGINS", "PYTHONPATH", "GLM53_CAP_ENABLE", "GLM53_CAP_REGISTRY", "GLM53_CAP_OUT"}
    for k, (s, c) in env_diff.items():
        print(f"{'note' if k in expected else 'DIFF':4s}  env {k}: served={s!r} capture={c!r}")
    unexpected = set(env_diff) - expected
    if unexpected:
        diffs.append(f"env {sorted(unexpected)}")
    print("RESULT:", "only the documented differences" if not diffs else f"UNEXPECTED: {diffs}")
    sys.exit(1 if diffs else 0)


if __name__ == "__main__":
    main()

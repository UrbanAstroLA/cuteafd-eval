#!/usr/bin/env python3
"""New GPQA Diamond questions for the stop-decision replication (PROTOCOL.md): 30 drawn at random, Random(20261106), from
the 198 minus the 12 documents already used by the thinking-length trace sets (looping probes 79, 13, 127, 88, 121, 90;
knife-edge set 186, 12, 81, 120, 86, 74). Writes questions.json. Standard library only."""
import json, random
USED = {79, 13, 127, 88, 121, 90, 186, 12, 81, 120, 86, 74}
pool = sorted(set(range(198)) - USED)
docs = sorted(random.Random(20261106).sample(pool, 30))
json.dump({"seed": 20261106, "excluded": sorted(USED), "docs": docs}, open("<nq-run>/questions.json", "w"), indent=1)
print(",".join(map(str, docs)))

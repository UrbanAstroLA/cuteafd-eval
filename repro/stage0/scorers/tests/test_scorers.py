#!/usr/bin/env python3
"""CPU tests with known answers for plans.py, score_pa.py, score_pb.py, score_q2.py, validate_pb.py.

Run:  <venv>/bin/python -B tests/test_scorers.py [-v]
Writes only under scorers/_tmp (removed at the end) and scorers/tests/results.json.
The long real-data checks (teacher self-score, v0.8.0 regression) are in selfcheck.sh, not here.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True
import common as C  # noqa: E402
import plans  # noqa: E402
import score_pa  # noqa: E402
import score_pb as PB  # noqa: E402
import score_q2  # noqa: E402

TMP = os.path.join(ROOT, "_tmp")
PY = sys.executable
GLMF = "<cuteafd>/scripts/bench/glmf-teacher-kl.py"
KLD = "<kld>/kld_score.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def run(*args):
    p = subprocess.run([PY, "-B", *args], capture_output=True, text=True, cwd=ROOT)
    return p.returncode, p.stdout, p.stderr


def peaked_rows(tokens, rows, V, rng, peak=8.0, noise=1.0):
    """Logits that put most mass on tokens[r+1] (an aligned toy LM)."""
    z = rng.normal(0, noise, size=(len(rows), V)).astype(np.float32)
    z[np.arange(len(rows)), np.asarray(tokens)[np.asarray(rows) + 1]] += peak
    return z


# ------------------------------------------------------------------------------------------
class T1_Numerics(unittest.TestCase):
    def test_identical_rows_zero(self):
        rng = np.random.default_rng(1)
        z = rng.normal(0, 6, size=(32, 4096)).astype(np.float32)
        self.assertEqual(float(np.abs(C.kl_rows_f64(z, z)).max()), 0.0)
        lp = C.log_softmax_f64(z)
        self.assertEqual(float(np.abs(C.kl_from_logprobs(lp, lp)).max()), 0.0)
        self.assertLess(float(np.abs(C.js_from_logprobs(lp, lp)).max()), 1e-15)

    def test_bit_equal_to_kld_score(self):
        k = load_module("kld_score_orig", KLD)          # sys.dont_write_bytecode: nothing written there
        rng = np.random.default_rng(2)
        a = rng.normal(0, 7, size=(16, C.VOCAB)).astype(np.float32)
        b = (a + rng.normal(0, 0.3, size=a.shape)).astype(np.float32)
        self.assertTrue(np.array_equal(k.log_softmax_f64(a), C.log_softmax_f64(a)))
        self.assertTrue(np.array_equal(k.kl_rows_f64(a, b), C.kl_rows_f64(a, b)))
        # score_pa's inline form (pt * (lpt - lpc)).sum() is the same expression
        lpt, lpc = C.log_softmax_f64(a), C.log_softmax_f64(b)
        self.assertTrue(np.array_equal((np.exp(lpt) * (lpt - lpc)).sum(-1), k.kl_rows_f64(a, b)))

    def test_analytic_uniform_vs_tilted(self):
        V = C.VOCAB
        for d in (0.5, 2.0, 8.0, 20.0):
            zt = np.zeros((1, V))
            zc = np.zeros((1, V))
            zc[0, 0] = d
            want = math.log1p(math.expm1(d) / V) - d / V
            self.assertLess(abs(float(C.kl_rows_f64(zt, zc)[0]) - want), 1e-14)

    def test_analytic_two_point_and_js(self):
        p, q = 0.7, 0.2
        lpa = np.log(np.array([[p, 1 - p]]))
        lpb = np.log(np.array([[q, 1 - q]]))
        want = p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))
        self.assertLess(abs(C.kl_from_logprobs(lpa, lpb)[0] - want), 1e-15)
        m = np.array([(p + q) / 2, (2 - p - q) / 2])
        js = 0.5 * (p * math.log(p / m[0]) + (1 - p) * math.log((1 - p) / m[1])) + \
            0.5 * (q * math.log(q / m[0]) + (1 - q) * math.log((1 - q) / m[1]))
        self.assertLess(abs(C.js_from_logprobs(lpa, lpb)[0] - js), 1e-15)
        # disjoint supports: JS = ln 2 exactly, KL = the logit gap
        a = C.log_softmax_f64(np.array([[0.0, -1e4]]))
        b = C.log_softmax_f64(np.array([[-1e4, 0.0]]))
        self.assertEqual(float(C.js_from_logprobs(a, b)[0]), math.log(2.0))
        self.assertAlmostEqual(float(C.kl_from_logprobs(a, b)[0]), 1e4, places=9)

    def test_scipy_reference(self):
        from scipy.special import rel_entr, log_softmax
        rng = np.random.default_rng(3)
        a = rng.normal(0, 5, size=(8, 20000))
        b = a + rng.normal(0, 0.4, size=a.shape)
        ref = rel_entr(np.exp(log_softmax(a, -1)), np.exp(log_softmax(b, -1))).sum(-1)
        got = C.kl_from_logprobs(C.log_softmax_f64(a), C.log_softmax_f64(b))
        self.assertLess(float(np.abs(got / ref - 1).max()), 1e-10)

    def test_tie_rules(self):
        x = np.array([[0.0, 5.0, 1.0, 5.0, 5.0]])
        self.assertEqual(int(C.argmax_lowid(x)[0]), 1)
        self.assertEqual(C.top3_lowid(x)[0].tolist(), [1, 3, 4])
        y = np.array([[9.0, 1.0, 1.0, 1.0, 1.0, 0.0]])
        self.assertEqual(C.top3_lowid(y)[0].tolist(), [0, 1, 2])
        rng = np.random.default_rng(4)
        z = rng.normal(size=(50, 300))
        ref = np.array([sorted(range(300), key=lambda i: (-z[r, i], i))[:3] for r in range(50)])
        self.assertTrue(np.array_equal(C.top3_lowid(z), ref))

    def test_bf16_decode(self):
        x = np.array([1.0, -2.5, 3.140625, 1e-3, 65280.0], dtype=np.float32)
        bits = C.f32_to_bf16_bits(x)
        back = C.to_f64(bits, "BF16")
        self.assertTrue(np.array_equal(back[:3], x[:3].astype(np.float64)))
        self.assertLess(abs(back[3] / 1e-3 - 1), 2 ** -8)


# ------------------------------------------------------------------------------------------
class T2_Alignment(unittest.TestCase):
    def test_off_by_one_detector(self):
        rng = np.random.default_rng(5)
        V, n = 200, 300
        tokens = rng.integers(0, V, size=n + 2)
        rows = np.arange(n)
        good = C.log_softmax_f64(peaked_rows(tokens, rows, V, rng))
        v = C.alignment_verdict(C.alignment_nll(good, tokens, rows))
        self.assertTrue(v["aligned"], v)
        # rows labelled r but holding row r+1's content (engine one ahead)
        ahead = C.log_softmax_f64(peaked_rows(tokens, rows + 1, V, rng))
        self.assertFalse(C.alignment_verdict(C.alignment_nll(ahead, tokens, rows))["aligned"])
        # rows labelled r but holding row r-1's content (engine one behind)
        behind = C.log_softmax_f64(peaked_rows(tokens, np.maximum(rows - 1, 0), V, rng))
        self.assertFalse(C.alignment_verdict(C.alignment_nll(behind[1:], tokens, rows[1:]))["aligned"])


# ------------------------------------------------------------------------------------------
class T3_Bootstrap(unittest.TestCase):
    def test_splitmix_vector(self):
        r = C.SplitMix64(0)
        self.assertEqual(r.next(), 0xE220A8397B1DCDAF)

    def test_splitmix_matches_c(self):
        src = os.path.join(TMP, "sm.c")
        exe = os.path.join(TMP, "sm")
        with open(src, "w") as f:
            f.write(r'''#include <stdio.h>
#include <stdint.h>
/* transcription of cuteafd-bench/src/fidelity.rs:125-140 with native u64 wraparound */
static uint64_t s;
static uint64_t next(void){ s += 0x9e3779b97f4a7c15ULL; uint64_t z = s;
 z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL; z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL; return z ^ (z >> 31); }
static uint64_t idx(uint64_t n){ uint64_t t = (0 - n) % n; for(;;){ uint64_t x = next(); if (x >= t) return x % n; } }
int main(void){ s = 20260829ULL; for (int i = 0; i < 2000; i++) printf("%llu\n", (unsigned long long)idx(53));
 s = 7ULL; for (int i = 0; i < 2000; i++) printf("%llu\n", (unsigned long long)idx(3)); return 0; }''')
        subprocess.run(["gcc", "-O1", "-o", exe, src], check=True)
        c = [int(x) for x in subprocess.run([exe], capture_output=True, text=True, check=True).stdout.split()]
        r = C.SplitMix64(20260829)
        py = [r.index(53) for _ in range(2000)]
        r = C.SplitMix64(7)
        py += [r.index(3) for _ in range(2000)]
        self.assertEqual(c, py)

    def test_paired_identical_and_shift(self):
        rng = np.random.default_rng(6)
        cl = np.repeat(np.arange(10), 50)
        x = rng.normal(size=500)
        one = np.ones(500)
        spec = C.BootSpec(2000, 1, "numpy")
        r = C.paired_metrics({"m": (x, one)}, {"m": (x, one)}, cl, np.ones(500, bool), spec)["m"]
        self.assertEqual(r["B_minus_A"], 0.0)
        self.assertEqual(r["ci95"], [0.0, 0.0])
        r = C.paired_metrics({"m": (x, one)}, {"m": (x + 0.25, one)}, cl, np.ones(500, bool), spec)["m"]
        self.assertAlmostEqual(r["B_minus_A"], 0.25, places=12)
        self.assertAlmostEqual(r["ci95"][0], 0.25, places=12)
        self.assertAlmostEqual(r["ci95"][1], 0.25, places=12)
        s = C.summarize_metrics({"m": (x, one)}, cl, np.ones(500, bool), spec)["m"]
        self.assertAlmostEqual(s["value"], float(x.mean()), places=14)
        self.assertLess(s["ci95"][0], s["value"])
        self.assertGreater(s["ci95"][1], s["value"])


# ------------------------------------------------------------------------------------------
class T4_PA(unittest.TestCase):
    """score_pa.score_window with small dimensions (monkeypatched), known answers."""

    def setUp(self):
        self.V, self.R = 64, 31
        self._old = (C.VOCAB, score_pa.ROWS)
        C.VOCAB, score_pa.ROWS = self.V, self.R
        self.d = os.path.join(TMP, "pa")
        os.makedirs(os.path.join(self.d, "teacher"), exist_ok=True)
        rng = np.random.default_rng(7)
        self.tokens = rng.integers(0, self.V, size=self.R + 1)
        zt = peaked_rows(self.tokens, np.arange(self.R), self.V, rng, peak=3.0)
        zt = C.to_f64(C.f32_to_bf16_bits(zt), "BF16").astype(np.float32)          # BF16-exact like the real teacher
        zt[0, :] = 0.0
        zt[0, 5] = zt[0, 9] = 4.0                                                 # a teacher top-1 tie (5 vs 9)
        self.zt = zt
        C.write_safetensors(os.path.join(self.d, "teacher", "window-0000.safetensors"), [("logits", "F32", zt)])

    def tearDown(self):
        C.VOCAB, score_pa.ROWS = self._old

    def _arm(self, name, tensors, meta=None):
        p = os.path.join(self.d, name)
        os.makedirs(p, exist_ok=True)
        C.write_safetensors(os.path.join(p, "final-0000.safetensors"), tensors, meta)
        return p

    def _score(self, arms):
        return score_pa.score_window((0, "final-0000", self.tokens.tolist(), os.path.join(self.d, "teacher"),
                                      arms, 8))

    def test_teacher_as_engine_and_layouts(self):
        rows = np.arange(self.R, dtype=np.int32)
        lp32 = C.log_softmax_f64(self.zt).astype(np.float32)
        arms = {
            "teacher": os.path.join(self.d, "teacher"),
            "bf16_logits": self._arm("b", [("logprobs", "BF16", C.f32_to_bf16_bits(self.zt)), ("rows", "I32", rows)],
                                     {"tokens_sha256": C.tokens_sha256(self.tokens)}),
            "glmf_layout": self._arm("g", [("positions", "I32", rows), ("logits", "F32", lp32)]),
            "f16": self._arm("h", [("logprobs", "F16", self.zt.astype(np.float16)), ("rows", "I64", rows.astype(np.int64))]),
        }
        r = self._score(arms)
        T = r["T"]
        for n in ("teacher", "bf16_logits"):
            self.assertEqual(float(np.abs(r["A"][n]["kl"]).max()), 0.0, n)
            self.assertTrue(np.array_equal(r["A"][n]["nll"], T["teacher_nll"]), n)
            self.assertTrue(np.array_equal(r["A"][n]["argmax"], T["teacher_argmax"]), n)
        self.assertLess(float(np.abs(r["A"]["glmf_layout"]["kl"]).max()), 1e-12)   # F32 log-prob storage
        self.assertLess(float(np.abs(r["A"]["glmf_layout"]["nll"] - T["teacher_nll"]).max()), 1e-6)
        self.assertLess(float(np.abs(r["A"]["f16"]["kl"]).max()), 1e-12)          # BF16 values are exact in F16 unless subnormal
        self.assertEqual(int(T["teacher_argmax"][0]), 5)                           # tie -> lower id
        self.assertTrue(bool(T["teacher_top1_tie"][0]))
        self.assertTrue(r["align"]["teacher"]["aligned"] and r["align"]["__teacher__"]["aligned"])
        self.assertEqual(r["sources"]["bf16_logits"]["token_meta_checked"], "tokens_sha256")
        # summary metrics through the same code path as the CLI
        d = {"window_ids": np.array(["final-0000"]), "window_index": np.zeros(self.R, int), "row": np.arange(self.R),
             "next": r["next"], **{k: T[k] for k in ("teacher_nll", "teacher_p1", "teacher_argmax", "teacher_top1_tie")},
             **{k: r["A"]["teacher"][k] for k in ("kl", "nll", "argmax", "top3")}}
        s = score_pa.summarize(d, C.BootSpec(100, 1))
        self.assertEqual(s["overall"]["kl"]["value"], 0.0)
        self.assertEqual(s["overall"]["top1"]["value"], 1.0)
        self.assertEqual(s["overall"]["dnll"]["value"], 0.0)

    def test_known_metrics(self):
        """Engine = teacher with row 3 moved to a different argmax: exact top1/top3/KL for that row."""
        z = self.zt.astype(np.float64).copy()
        ta = int(np.argmax(z[3]))
        order = sorted(range(self.V), key=lambda i: (-z[3, i], i))
        second, fourth = order[1], order[3]
        z_top3 = z.copy()
        z_top3[3, second] = z[3, ta] + 1.0          # engine argmax = teacher's 2nd: top1 miss, top3 hit
        z_miss = z.copy()
        z_miss[3, fourth] = z[3, ta] + 1.0          # engine argmax = teacher's 4th: top1 and top3 miss
        arms = {"t3": self._arm("k3", [("logprobs", "F32", z_top3.astype(np.float32)), ("rows", "I32", np.arange(self.R, dtype=np.int32))]),
                "miss": self._arm("km", [("logprobs", "F32", z_miss.astype(np.float32)), ("rows", "I32", np.arange(self.R, dtype=np.int32))])}
        r = self._score(arms)
        for n, hit3 in (("t3", True), ("miss", False)):
            a = r["A"][n]
            agree = a["argmax"] == r["T"]["teacher_argmax"]
            self.assertEqual(agree.sum(), self.R - 1)
            self.assertFalse(agree[3])
            self.assertEqual(bool(a["top3"][3]), hit3)
            want = float(C.kl_rows_f64(z[3:4], (z_top3 if n == "t3" else z_miss)[3:4])[0])
            self.assertLess(abs(a["kl"][3] - want), 1e-15)
            self.assertEqual(float(np.abs(np.delete(a["kl"], 3)).max()), 0.0)

    def test_row_mismatch_and_token_mismatch_rejected(self):
        rows = np.arange(1, self.R, dtype=np.int32)
        p = self._arm("short", [("logprobs", "F32", self.zt[1:]), ("rows", "I32", rows)])
        with self.assertRaises(ValueError):
            self._score({"short": p})
        p = self._arm("tok", [("logprobs", "F32", self.zt), ("rows", "I32", np.arange(self.R, dtype=np.int32))],
                      {"tokens_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            self._score({"tok": p})

    def test_off_by_one_engine_flagged(self):
        shifted = np.roll(self.zt, -1, axis=0)        # file row r holds teacher row r+1
        p = self._arm("shift", [("logprobs", "F32", shifted), ("rows", "I32", np.arange(self.R, dtype=np.int32))])
        r = self._score({"shift": p})
        self.assertFalse(r["align"]["shift"]["aligned"])
        self.assertGreater(float(r["A"]["shift"]["kl"].mean()), 1.0)


# ------------------------------------------------------------------------------------------
def pb_window(top_p, tail_p, next_tok, V, tokens=None, pos=1):
    """A one-position P-B window from probabilities (renormalised like the loader)."""
    k = len(top_p)
    lps = np.log(np.array(top_p + [tail_p], dtype=np.float64)) if tail_p > 0 else \
        np.concatenate([np.log(np.array(top_p)), [-np.inf]])
    mass = PB.normalize_rust(lps[None, :])
    if tokens is None:
        tokens = np.zeros(pos + 1, dtype=np.int64)
        tokens[pos] = next_tok
    return {"id": "t", "top_ids": np.arange(k)[None, :], "top_lp": mass[:, :k], "tail_lp": mass[:, k],
            "next": np.array([next_tok]), "tokens": np.asarray(tokens), "positions": np.array([pos])}


class T5_PB_Rule(unittest.TestCase):
    V = 5

    def eng(self, q):
        return np.log(np.array([q], dtype=np.float64))

    def test_identical_partition_zero(self):
        w = pb_window([0.5, 0.3], 0.2, 1, self.V)
        r = PB.score_rows(w, self.eng([0.5, 0.3, 0.1, 0.05, 0.05]), 0, True)
        self.assertLess(abs(r["kl"][0]), 1e-16)
        self.assertAlmostEqual(r["nll"][0], -math.log(0.3), places=15)
        self.assertTrue(r["agree"][0] and r["top3"][0] and r["agree_text"][0] is np.False_)

    def test_analytic_tail_cases(self):
        w = pb_window([0.5, 0.3], 0.2, 0, self.V)
        q = [0.4, 0.4, 0.1, 0.05, 0.05]                     # engine tail 0.2, same as reference
        want = 0.5 * math.log(0.5 / 0.4) + 0.3 * math.log(0.3 / 0.4)
        self.assertAlmostEqual(PB.score_rows(w, self.eng(q), 0, True)["kl"][0], want, places=15)
        q = [0.4, 0.5, 0.06, 0.02, 0.02]                    # engine tail 0.1
        want = 0.5 * math.log(0.5 / 0.4) + 0.3 * math.log(0.3 / 0.5) + 0.2 * math.log(0.2 / 0.1)
        r = PB.score_rows(w, self.eng(q), 0, True)
        self.assertAlmostEqual(r["kl"][0], want, places=15)
        self.assertEqual(int(r["argmax"][0]), 1)
        self.assertFalse(r["agree"][0])                    # ref top[0] is id 0
        self.assertTrue(r["top3"][0])
        # how the engine spreads its tail does not matter (coarse KL sees the tail as one cell)
        q2 = [0.4, 0.5, 0.0999, 0.00005, 0.00005]
        self.assertAlmostEqual(PB.score_rows(w, self.eng(q2), 0, True)["kl"][0], want, places=15)
        # zero reference tail (tail_lp = -inf): the tail term is skipped (fidelity_rows.rs:191)
        w0 = pb_window([0.6, 0.4], 0.0, 0, self.V)
        q = [0.5, 0.3, 0.1, 0.05, 0.05]
        want = 0.6 * math.log(0.6 / 0.5) + 0.4 * math.log(0.4 / 0.3)
        self.assertAlmostEqual(PB.score_rows(w0, self.eng(q), 0, True)["kl"][0], want, places=15)
        self.assertTrue(PB.score_rows(w0, self.eng(q), 0, True)["confident"][0])   # 0.6 >= 0.5

    def test_tail_uses_complement_logsumexp_not_one_minus_mass(self):
        """Engine tail of 1e-13: 1 - sum(top q) cancels in f64 (reference.rs:302); the complement LSE does not."""
        tail = 1e-13
        w = pb_window([0.5, 0.5 - 1e-10], 1e-10, 0, self.V)
        q = np.array([0.5, 0.5 - tail], dtype=np.float64)
        lq = np.log(np.concatenate([q, [tail / 3] * 3]))
        r = PB.score_rows(w, lq[None, :], 0, True)
        p = np.exp(w["top_lp"][0])
        pt = math.exp(w["tail_lp"][0])
        want = float(np.sum(p * (np.log(p) - lq[:2]))) + pt * (math.log(pt) - math.log(tail))
        self.assertLess(abs(r["kl"][0] - want), 1e-15)

    def test_his_rust_unit_vectors(self):
        """fidelity_rows.rs:203-267: f16 0xb98b twice normalises to uniform; one-id support + tail -ln2."""
        h = PB.half_to_f64(np.array([0xB98B, 0xB98B], dtype=np.uint16))
        self.assertAlmostEqual(PB.normalize_rust(h[None, :])[0, 0], -math.log(2), places=15)
        w = {"id": "A1", "top_ids": np.array([[0]]), "top_lp": np.array([[-math.log(2)]]),
             "tail_lp": np.array([-math.log(2)]), "next": np.array([0]), "tokens": np.array([0, 0]),
             "positions": np.array([1])}
        r = PB.score_rows(w, np.array([[0.0, 0.0]]), 0, True)
        self.assertEqual(r["kl"][0], 0.0)
        self.assertLess(abs(r["nll"][0] - math.log(2)), 1e-12)
        self.assertEqual(PB.half_to_f64(np.array([0x3C00, 0xC000, 1, 0xFC00], dtype=np.uint16)).tolist(),
                         [1.0, -2.0, 2.0 ** -24, -math.inf])

    def test_clamp_and_guard(self):
        p = np.array([0.5, 0.5 - 1e-3])                     # inconsistent reference (sum < 1), only to drive the guard
        base = {"id": "g", "top_ids": np.array([[0, 1]]), "top_lp": np.log(p)[None, :], "tail_lp": np.array([-np.inf]),
                "next": np.array([0]), "tokens": np.array([0, 0]), "positions": np.array([1])}
        for eps, raises in ((1e-13, False), (1e-6, True)):
            q = p * (1 + eps)
            lq = np.log(np.concatenate([q, [(1 - q.sum()) / 3] * 3]))[None, :]
            if raises:
                with self.assertRaises(ValueError):
                    PB.score_rows(base, lq, 0, True)
            else:
                r = PB.score_rows(base, lq, 0, True)
                self.assertLess(r["kl_unclamped"][0], 0.0)
                self.assertEqual(r["kl"][0], 0.0)

    def test_engine_tie_and_nonfinite(self):
        w = pb_window([0.5, 0.3], 0.2, 2, self.V)
        w["top_ids"] = np.array([[3, 1]])
        e = np.log(np.array([[0.1, 0.35, 0.1, 0.35, 0.1]]))
        r = PB.score_rows(w, e, 0, True)
        self.assertEqual(int(r["argmax"][0]), 1)            # tie 1 vs 3 -> lower id
        self.assertFalse(r["agree"][0])                      # ref top[0] is id 3 (stored order)
        self.assertTrue(r["top3"][0])
        with self.assertRaises(ValueError):
            PB.score_rows(w, np.array([[0.0, np.nan, 0, 0, 0]]), 0, True)

    def test_rust_vs_numpy_order(self):
        rng = np.random.default_rng(8)
        V, k = 4000, 64
        z = rng.normal(0, 3, size=(4, V))
        top = np.argsort(-z[0])[:k]
        lp = C.log_softmax_f64(z[:1])[0]
        tail = np.log(np.exp(np.delete(lp, top)).sum())
        w = {"id": "o", "top_ids": np.tile(top, (4, 1)), "top_lp": np.tile(lp[top], (4, 1)),
             "tail_lp": np.full(4, tail), "next": np.zeros(4, int), "tokens": np.zeros(5, int), "positions": np.arange(1, 5)}
        a = PB.score_rows(w, z, 0, True)
        b = PB.score_rows(w, z, 0, False)
        self.assertLess(float(np.abs(a["kl"] - b["kl"]).max()), 1e-13)
        self.assertLess(abs(a["kl"][0]), 1e-13)


# ------------------------------------------------------------------------------------------
def write_dump_leaf(leaf, positions, rows_f32):
    """A CuteAFD probe dump leaf, byte layout of cuteafd-api/src/openai/probe/rows.rs:59-86."""
    os.makedirs(leaf)
    V = rows_f32.shape[1]
    with open(os.path.join(leaf, "manifest.jsonl"), "w") as man:
        for i, (p, row) in enumerate(zip(positions, rows_f32)):
            name = f"row-{i:08d}.safetensors"
            header = json.dumps({"log_probs": {"dtype": "F32", "shape": [V], "data_offsets": [0, 4 * V]}}).encode()
            header += b" " * (-len(header) % 8)
            with open(os.path.join(leaf, name), "wb") as f:
                f.write(len(header).to_bytes(8, "little") + header + np.asarray(row, "<f4").tobytes())
            man.write(json.dumps({"position": int(p), "vocab_size": V, "file": name, "tensor": "log_probs",
                                  "dtype": "F32", "byte_order": "little"}) + "\n")


def synth_engine_from_reference(w, V, shift=0):
    """Engine log-probs equal to the reference partition: top ids get the renormalised top lps, the
    complement shares the tail mass uniformly. shift=+1 puts row r+1's content at row r."""
    k = len(w["positions"])
    out = np.empty((k, V), dtype=np.float32)
    for i in range(k):
        j = min(max(i + shift, 0), k - 1)
        row = np.full(V, w["tail_lp"][j] - math.log(V - 1024))
        row[w["top_ids"][j]] = w["top_lp"][j]
        out[i] = row.astype(np.float32)
    return out


class T6_PB_RealReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = PB.load_reference(verify_hashes=True)
        cls.d = os.path.join(TMP, "pb")
        os.makedirs(cls.d, exist_ok=True)

    def test_reference_loader_counts(self):
        ws = self.ref["windows"]
        self.assertEqual(len(ws), 64)
        self.assertEqual(sum(len(w["positions"]) for w in ws), 32768)
        gen = sum(sum(r == "gen" for r in w["roles"]) for w in ws)
        self.assertEqual(gen, 15104)
        nb = {}
        gb = {}
        for w in ws:
            nb[w["bucket"]] = nb.get(w["bucket"], 0) + 1
            gb[w["bucket"]] = gb.get(w["bucket"], 0) + sum(r == "gen" for r in w["roles"])
            self.assertTrue(w["bucket_check"], w["id"])
        self.assertEqual(nb, {"0-2K": 30, "2-8K": 16, "8-16K": 18})
        self.assertEqual(gb, {"0-2K": 4035, "2-8K": 3547, "8-16K": 7522})
        # the reference's own next-token log-prob agrees with its top-1024 entry for that token
        # (alignment of positions/next ids inside the published reference)
        hit, n, worst, gen_hit, gen_n = 0, 0, 0.0, 0, 0
        for w in ws:
            for i in range(len(w["positions"])):
                n += 1
                gen_n += w["roles"][i] == "gen"
                j = np.flatnonzero(w["top_ids"][i] == w["next"][i])
                if j.size:
                    hit += 1
                    gen_hit += w["roles"][i] == "gen"
                    worst = max(worst, abs(w["top_lp"][i, j[0]] - w["next_lp"][i]) / (1e-3 + abs(w["next_lp"][i])))
                else:
                    self.assertLessEqual(w["next_lp"][i], w["top_lp"][i, -1] + 1e-2)
        self.assertEqual(gen_hit, gen_n)          # greedy-generated tokens are always in the reference top-1024
        self.assertGreater(hit / n, 0.95)         # 32,311 / 32,768 overall (human ctx text: 91.8%)
        self.assertLess(worst, 5e-3)
        # renormalised 1025-cell partitions sum to 1
        for w in ws[:8]:
            tot = np.exp(w["top_lp"]).sum(1) + np.exp(w["tail_lp"])
            self.assertLess(float(np.abs(tot - 1).max()), 1e-12)

    def test_end_to_end_files_dump_and_validator(self):
        V = self.ref["vocab"]
        ids = ["legacy", "a00", "c00"]                               # full-tier indices 0, 1, 39
        all_ids = [w["id"] for w in self.ref["windows"]]
        files = os.path.join(self.d, "files")
        dump = os.path.join(self.d, "dump")
        shifted = os.path.join(self.d, "shifted")
        for p in (files, shifted):
            os.makedirs(p, exist_ok=True)
        expect_agree = {}
        for wid in ids:
            w = next(x for x in self.ref["windows"] if x["id"] == wid)
            e = synth_engine_from_reference(w, V)
            rows = (w["positions"] - 1).astype(np.int32)
            C.write_safetensors(os.path.join(files, f"{wid}.safetensors"), [("logprobs", "F32", e), ("rows", "I32", rows)],
                                {"tokens_sha256": C.tokens_sha256(w["tokens"])})
            write_dump_leaf(os.path.join(dump, f"window-{all_ids.index(wid):03d}"), w["positions"], e)
            C.write_safetensors(os.path.join(shifted, f"{wid}.safetensors"),
                                [("logprobs", "F32", synth_engine_from_reference(w, V, shift=1)), ("rows", "I32", rows)])
            mx = e.max(axis=1)
            expect_agree[wid] = (np.array([np.flatnonzero(e[i] == mx[i])[0] for i in range(len(e))]) == w["top_ids"][:, 0])
        out = os.path.join(self.d, "out")
        common = ["--windows", ",".join(ids), "--jobs", "1", "--iters", "200", "--skip-hashes"]
        rc, so, se = run("score_pb.py", "score", "--engine", files, "--arm", "files", "--out", out, *common)
        self.assertEqual(rc, 0, se)
        rc, so, se = run("score_pb.py", "score", "--engine", dump, "--layout", "cuteafd-dump", "--cli-order", "full",
                         "--arm", "dump", "--out", out, *common)
        self.assertEqual(rc, 0, se)
        A = json.load(open(os.path.join(out, "pb-files.records.json")))
        B = json.load(open(os.path.join(out, "pb-dump.records.json")))
        self.assertEqual(A, B)                                        # dump reader == file reader, bit for bit
        kl = np.array([r["kl"] for r in A])
        self.assertLess(float(kl.max()), 1e-6)                        # f32 storage of the reference partition
        got = np.array([r["agree"] for r in A])
        self.assertTrue(np.array_equal(got, np.concatenate([expect_agree[w] for w in ids])))
        s = json.load(open(os.path.join(out, "pb-files.json")))
        self.assertEqual(s["layout"], "files")
        self.assertTrue(all(v["token_meta_checked"] == "tokens_sha256" for v in s["sources"].values()))
        # off-by-one engine rows are refused
        rc, so, se = run("score_pb.py", "score", "--engine", shifted, "--arm", "shifted", "--out", out, *common)
        self.assertEqual(rc, 2)
        self.assertIn("alignment check failed", se)
        # validator: a CLI-shaped run file built from the dump records passes; a 1e-9 perturbation fails
        run_json = {"schema": "cuteafd.fidelity.run/2", "arm": "x", "score": {
            "positions": len(B), "missing": 0, "non_finite": 0, "records": B,
            "kl": float(np.mean([r["kl"] for r in B])), "top1": float(np.mean([r["agree"] for r in B]))}}
        cli = os.path.join(self.d, "cli.json")
        json.dump(run_json, open(cli, "w"))
        rc, so, se = run("validate_pb.py", "records", "--cli", cli, "--port", os.path.join(out, "pb-files.records.json"),
                         "--out", os.path.join(self.d, "v.json"))
        self.assertEqual(rc, 0, so + se)
        B[5]["kl"] += 1e-9
        json.dump(run_json, open(cli, "w"))
        rc, so, se = run("validate_pb.py", "records", "--cli", cli, "--port", os.path.join(out, "pb-files.records.json"),
                         "--out", os.path.join(self.d, "v2.json"))
        self.assertEqual(rc, 3)
        # rows comparison: dump vs files of the same rows are bit identical
        rc, so, se = run("validate_pb.py", "rows", "--a", dump, "--a-order", "full", "--b", files,
                         "--windows", ",".join(ids), "--out", os.path.join(self.d, "rows.json"))
        self.assertEqual(rc, 0, se)
        rr = json.load(open(os.path.join(self.d, "rows.json")))
        self.assertEqual(rr["totals"]["bit_identical"], rr["totals"]["rows"])
        # paired mode: an arm against itself is zero everywhere; his compare stats are zero
        rc, so, se = run("score_pb.py", "pair", "--a", os.path.join(out, "pb-files.rows.npz"),
                         "--b", os.path.join(out, "pb-dump.rows.npz"), "--out", os.path.join(out, "pair.json"),
                         "--iters", "200")
        self.assertEqual(rc, 0, se)
        pr = json.load(open(os.path.join(out, "pair.json")))
        self.assertEqual(pr["gen"]["overall"]["kl"]["B_minus_A"], 0.0)
        self.assertEqual(pr["cuteafd_compare"]["kl_delta"], 0.0)
        self.assertEqual(pr["cuteafd_compare"]["top1_loss"], 0.0)


# ------------------------------------------------------------------------------------------
class T7_Q2(unittest.TestCase):
    def test_q2_end_to_end(self):
        V = 64
        old = C.VOCAB
        C.VOCAB = V
        try:
            d = os.path.join(TMP, "q2")
            rng = np.random.default_rng(9)
            items = []
            for i, (doc, typ, lb) in enumerate([("d0", "prose", "32K"), ("d1", "code", "32K"),
                                                ("d0", "prose", "64K"), ("d2", "code", "64K")]):
                items.append({"window_id": f"w{i}", "doc_id": doc, "doc_type": typ, "length_bucket": lb,
                              "tokens": rng.integers(0, V, size=80).tolist(), "n_score": 40})
            os.makedirs(d, exist_ok=True)
            json.dump(items, open(os.path.join(d, "in.json"), "w"))
            w, m = plans.build_q2(os.path.join(d, "in.json"))
            pdir = os.path.join(d, "plans")
            os.makedirs(pdir, exist_ok=True)
            plans._write(pdir, "q2", w, m)
            reg = json.load(open(os.path.join(pdir, "q2.vllm-registry.json")))
            self.assertEqual(reg["windows"][0]["rows"], list(range(39, 79)))
            dirs = {k: os.path.join(d, k) for k in ("A", "A2", "B")}
            for p in dirs.values():
                os.makedirs(p, exist_ok=True)
            want = {}
            for x in reg["windows"]:
                rows = np.array(x["rows"])
                za = peaked_rows(x["tokens"], rows, V, rng)
                zb = za + rng.normal(0, 0.5, size=za.shape).astype(np.float32)
                for k, z in (("A", za), ("A2", za), ("B", zb)):
                    if k == "A2" and x["window_id"] in ("w1", "w3"):
                        continue                                  # repeats only for a subset
                    C.write_safetensors(os.path.join(dirs[k], f"{x['window_id']}.safetensors"),
                                        [("logprobs", "F32", z), ("rows", "I32", rows.astype(np.int32))])
                la, lb = C.log_softmax_f64(za), C.log_softmax_f64(zb)
                want[x["window_id"]] = float(C.kl_rows_f64(za, zb).mean())
                self.assertLess(abs(float(C.kl_from_logprobs(la, lb).mean()) - want[x["window_id"]]), 1e-15)
            out = os.path.join(d, "out")
            sys_argv = sys.argv
            sys.argv = ["score_q2.py", "--plans", pdir, "--a", f"A={dirs['A']}", "--b", f"B={dirs['B']}",
                        "--a-repeat", dirs["A2"], "--out", out, "--jobs", "1", "--iters", "300"]
            try:
                rc = score_q2.main()
            finally:
                sys.argv = sys_argv
            self.assertEqual(rc, 0)
            r = json.load(open(os.path.join(out, "q2-A-vs-B.json")))
            for wid, kl in want.items():
                self.assertLess(abs(r["per_window"][wid]["kl_ab"] - kl), 1e-15)
            fl = r["groups"]["overall"]["noise_floor_A"]
            self.assertEqual(fl["kl_ab"]["value"], 0.0)
            self.assertEqual(fl["top1_agree"]["value"], 1.0)
            self.assertEqual(fl["dnll_repeat"]["B_minus_A"], 0.0)
            self.assertEqual(fl["rows"], 80)                       # w0 and w2 only
            self.assertLessEqual(r["groups"]["overall"]["between_engines"]["js"]["value"], math.log(2))
            self.assertIn("length=64K,type=code", r["groups"])
            self.assertEqual(r["groups"]["overall"]["between_engines"]["clusters"], 3)   # d0, d1, d2
        finally:
            C.VOCAB = old


# ------------------------------------------------------------------------------------------
class T8_Plans(unittest.TestCase):
    def test_q2_index_position_to_row(self):
        """Prompt-set files use tpurtell's POSITION convention (p scored from tokens 0..p-1); plans use rows r = p-1."""
        q = os.path.join(TMP, "q2idx", "q2")
        os.makedirs(q, exist_ok=True)
        L = 32768
        tok = list(range(L))
        w = {"window_id": "q2-code-x-032k", "kind": "code", "length": L, "tokens": tok,
             "rows": list(range(L - 4096, L)), "source": {"document": "x"}}
        json.dump(w, open(os.path.join(q, "q2-code-x-032k.json"), "w"))
        json.dump({"rule": "t", "windows": [{"window_id": w["window_id"], "kind": "code", "length": L, "document": "x",
                                             "first_row": L - 4096, "last_row": L - 1,
                                             "file": "q2/q2-code-x-032k.json"}]}, open(os.path.join(q, "index.json"), "w"))
        ws, _ = plans.build_q2_index(q)
        self.assertEqual(ws[0]["rows"], list(range(L - 4097, L - 1)))
        self.assertEqual(ws[0]["rows"][-1], L - 2)
        self.assertTrue(all(tok[r + 1] == p for r, p in zip(ws[0]["rows"], w["rows"])))
        self.assertEqual((ws[0]["length_bucket"], ws[0]["doc_type"], ws[0]["doc_id"]), ("32K", "code", "x"))
        w["rows"] = list(range(L - 4095, L + 1))                    # position L is out of range
        json.dump(w, open(os.path.join(q, "q2-code-x-032k.json"), "w"))
        with self.assertRaises(SystemExit):
            plans.build_q2_index(q)

    def test_plans_real_and_glmf_layout(self):
        out = os.path.join(TMP, "plans")
        rc, so, se = run("plans.py", "--out", out, "--panels", "pa,pb")
        self.assertEqual(rc, 0, se)
        glmf = load_module("glmf", GLMF)
        pa = json.load(open(os.path.join(out, "pa.cuteafd-plan.json")))
        pb = json.load(open(os.path.join(out, "pb.cuteafd-plan.json")))
        self.assertEqual(set(pa), {"vocab", "windows"})
        self.assertEqual(set(pa["windows"][0]), {"window_id", "tokens", "tokens_sha256", "positions"})
        self.assertEqual(len(pa["windows"]), 25)
        self.assertEqual(pa["windows"][0]["positions"], list(range(2047)))
        ref = PB.load_reference(verify_hashes=False)
        for pw, rw in zip(pb["windows"], ref["windows"]):
            self.assertEqual(pw["window_id"], rw["id"])
            self.assertEqual(pw["tokens_sha256"], glmf.tokens_sha256(pw["tokens"]))
            spec = glmf.probe_spec(pw, "prefill", 64, "leaf")
            self.assertEqual(spec["score_positions"], rw["positions"].tolist())   # predicted positions match the reference
            self.assertEqual(spec["score_from"], 1)                                # see README: geometry differs from his CLI
        reg = json.load(open(os.path.join(out, "pb.vllm-registry.json")))
        self.assertEqual([w["rows"] for w in reg["windows"]], [w["positions"] for w in pb["windows"]])
        self.assertEqual(sum(len(w["rows"]) for w in reg["windows"]), 32768)
        # glmf-teacher-kl.py's own collect()/write_safetensors() output is read by our WindowRows
        V = 32
        leaf = os.path.join(TMP, "glmf-leaf")
        rows = [3, 4, 9]
        vals = np.random.default_rng(10).normal(size=(3, V)).astype(np.float32)
        write_dump_leaf(leaf, [r + 1 for r in rows], vals)
        data = glmf.collect(leaf, rows, V)
        p = os.path.join(TMP, "glmf-out.safetensors")
        from array import array
        glmf.write_safetensors(p, [("positions", "I32", [3], array("i", rows).tobytes()),
                                   ("logits", "F32", [3, V], data)], {"window_id": "w", "tokens_sha256": "x"})
        r = C.WindowRows(p, V)
        self.assertEqual(r.rows.tolist(), rows)
        self.assertEqual(r.values_name, "logits")
        self.assertTrue(np.array_equal(r.block(0, 3), vals.astype(np.float64)))
        dd = C.DumpDirRows(leaf, V)
        self.assertEqual(dd.rows.tolist(), rows)
        self.assertTrue(np.array_equal(dd.block(0, 3), vals.astype(np.float64)))


if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True)
    try:
        prog = unittest.main(exit=False, verbosity=2 if "-v" in sys.argv else 1)
        res = prog.result
        summary = {"ran": res.testsRun, "failures": len(res.failures), "errors": len(res.errors),
                   "failed": [str(t) for t, _ in res.failures + res.errors], "ok": res.wasSuccessful()}
        C.dump_json(os.path.join(HERE, "results.json"), summary)
        print(json.dumps(summary))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(0 if summary["ok"] else 1)

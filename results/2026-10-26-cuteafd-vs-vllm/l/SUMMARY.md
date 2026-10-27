# Block L summary

Generated from the analysis files in this folder by `tools/build_readme.py`. Per stage and content: requests that finished on their own (`stop`), that reached the cap, and that ended in a terminal loop (R50 ≥ 0.5 at the end of the reply); the content check (code: hidden pytest suite; JSON: schema, count, ids; reasoning: MATH-500 answer; prose: words written over words required); median decode rate.

| Stage | Cap | Content | Requests | vLLM: finished / at cap / terminal loops | vLLM: check | vLLM: decode tok/s | vLLM: median tokens | CuteAFD: finished / at cap / terminal loops | CuteAFD: check | CuteAFD: decode tok/s | CuteAFD: median tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 8K | prose | 8 | 0 / 8 / 0 | words/required 0.00 | 43.0 | 8,192 | 0 / 8 / 0 | words/required 0.00 | 40.7 | 8,192 |
| L1 | 8K | code | 8 | 0 / 8 / 0 | all tests pass 0/8 | 54.2 | 8,192 | 0 / 8 / 0 | all tests pass 0/8 | 54.9 | 8,192 |
| L1 | 8K | reasoning | 8 | 8 / 0 / 0 | correct 8/8 | 71.9 | 626 | 8 / 0 / 0 | correct 8/8 | 106.2 | 596 |
| L1 | 8K | json | 8 | 0 / 8 / 0 | valid 0/8 | 55.1 | 8,192 | 0 / 8 / 0 | valid 0/8 | 59.9 | 8,192 |
| L2 | 32K | prose | 8 | 1 / 7 / 0 | words/required 0.83 | 43.7 | 32,768 | 0 / 8 / 0 | words/required 0.48 | 40.1 | 32,768 |
| L2 | 32K | code | 8 | 0 / 8 / 0 | all tests pass 0/8 | 55.0 | 32,768 | 4 / 4 / 2 | all tests pass 4/8 | 59.3 | 32,692 |
| L2 | 32K | reasoning | 8 | 8 / 0 / 0 | correct 8/8 | 69.8 | 802 | 8 / 0 / 0 | correct 8/8 | 98.7 | 614 |
| L2 | 32K | json | 8 | 2 / 6 / 0 | valid 2/8 | 60.8 | 32,768 | 2 / 6 / 0 | valid 2/8 | 73.4 | 32,768 |
| L3 | 128K | prose | 8 | 8 / 0 / 0 | words/required 0.95 | 41.5 | 48,832 | 8 / 0 / 0 | words/required 1.05 | 39.3 | 39,344 |
| L3 | 128K | code | 8 | 8 / 0 / 6 | all tests pass 7/8 | 55.6 | 51,298 | 8 / 0 / 4 | all tests pass 7/8 | 58.2 | 38,190 |
| L3 | 128K | reasoning | 8 | 8 / 0 / 0 | correct 8/8 | 71.3 | 566 | 8 / 0 / 0 | correct 8/8 | 89.2 | 634 |
| L3 | 128K | json | 8 | 6 / 2 / 0 | valid 6/8 | 65.5 | 74,589 | 7 / 1 / 0 | valid 4/8 | 81.8 | 67,381 |
| L3s | 128K, 1 stream | prose | 1 | 1 / 0 / 0 | words/required 0.77 | 113.6 | 30,382 | 1 / 0 / 0 | words/required 0.78 | 126.5 | 33,168 |
| L3s | 128K, 1 stream | code | 1 | 1 / 0 / 1 | all tests pass 1/1 | 139.8 | 85,441 | 1 / 0 / 0 | all tests pass 1/1 | 165.4 | 56,847 |
| L3s | 128K, 1 stream | reasoning | 1 | 1 / 0 / 0 | correct 1/1 | 170.3 | 675 | 1 / 0 / 0 | correct 1/1 | 238.7 | 629 |
| L3s | 128K, 1 stream | json | 1 | 1 / 0 / 0 | valid 1/1 | 156.8 | 17,151 | 1 / 0 / 0 | valid 1/1 | 195.0 | 12,367 |

# SPDX-License-Identifier: GPL-2.0-only
"""Execute the version-3 linker-centre guard against the ordinary W strips.

The ordinary W recurrence marks a stripped linker centre with INFINITE_ENERGY.
Version 3 gives the ordinary WMB nucleotide-addition terms the same marker.
This harness extracts both code sites from the installed linker-3 source and
checks on synthetic tables that they apply an identical marker in every flag
and boundary combination. Costs are stand-ins, not physical energies.
"""

import hashlib
import json
import os
from pathlib import Path
import unittest

import test_trace_states


COMPONENT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <random>
using std::min;
const int INFINITE_ENERGY = 14000, INTER = 16;
struct Grid {
    int values[64][64], infinite = INFINITE_ENERGY;
    int &f(int i, int j) { return i > j ? infinite : values[i][j]; }
    void reset(int value) { for (auto &row: values) for (auto &cell: row) cell = value; }
};
struct CT { int shape[64]; int SHAPEss_give_value(int i) { return shape[i]; } };
int main() {
    Grid w, wmb, fce; CT cc; CT *ct = &cc;
    bool lfce[64]; int number = 30, e[6], mbl_nucleotide;
    const int BIG = 1000000;
    int guarded[2] = {0, 0}, plain[2] = {0, 0}, absent[2] = {0, 0}, boundary[2] = {0, 0};
    std::mt19937 gen(6605);
    for (int trial = 0; trial < 40000; ++trial) {
        int i = 1 + gen() % 58, j = i + 1 + gen() % (59 - i);
        if (trial % 7 == 0) i = number;        // strand boundary i == N
        if (trial % 11 == 0) j = number + 1;   // strand boundary j == N + 1
        if (i >= j) continue;
        w.reset(0); wmb.reset(0); fce.reset(0);
        for (int a = 0; a < 64; ++a) {
            lfce[a] = gen() % 4 == 0; cc.shape[a] = gen() % 6;
            for (int b = 0; b < 64; ++b) {
                w.values[a][b] = int(gen() % 601) - 300;
                wmb.values[a][b] = int(gen() % 601) - 300;
            }
        }
        mbl_nucleotide = gen() % 4;
        const bool inter_i = gen() % 2, inter_j = gen() % 2;
        if (inter_i) fce.f(i, i) |= INTER;
        if (inter_j) fce.f(j, j) |= INTER;
        e[4] = e[5] = INFINITE_ENERGY;
        // The ordinary W strips, exactly as the fill guards them.
        if (i != number) { @W_E4@ }
        if (j != number + 1) { if (j != 1) { @W_E5@ } }
        // Isolate each WMB addition term by making every alternative enormous.
        const int saved_ij = wmb.f(i, j), saved_left = wmb.f(i + 1, j), saved_right = wmb.f(i, j - 1);
        wmb.f(i, j) = BIG; wmb.f(i, j - 1) = BIG;
        @WMB_ADD@
        const int term_i = wmb.f(i, j);
        wmb.f(i, j) = BIG; wmb.f(i, j - 1) = saved_right; wmb.f(i + 1, j) = BIG;
        @WMB_ADD@
        const int term_j = wmb.f(i, j);
        wmb.f(i + 1, j) = saved_left; wmb.f(i, j) = saved_ij;
        if (i == number || lfce[i]) {
            assert(e[4] == INFINITE_ENERGY && term_i >= BIG); ++absent[0];
        } else {
            const int marker_w = e[4] - w.f(i + 1, j) - mbl_nucleotide - (inter_i ? 0 : cc.shape[i]);
            const int marker_wmb = term_i - saved_left - mbl_nucleotide - cc.shape[i];
            assert(marker_w == (inter_i ? INFINITE_ENERGY : 0));
            assert(marker_wmb == marker_w);
            ++(inter_i ? guarded[0] : plain[0]);
        }
        if (j == number + 1 || lfce[j]) {
            assert(e[5] == INFINITE_ENERGY && term_j >= BIG); ++absent[1];
        } else {
            const int marker_w = e[5] - w.f(i, j - 1) - mbl_nucleotide - (inter_j ? 0 : cc.shape[j]);
            const int marker_wmb = term_j - saved_right - mbl_nucleotide - cc.shape[j];
            assert(marker_w == (inter_j ? INFINITE_ENERGY : 0));
            assert(marker_wmb == marker_w);
            ++(inter_j ? guarded[1] : plain[1]);
        }
        if (i == number) ++boundary[0];
        if (j == number + 1) ++boundary[1];
    }
    assert(guarded[0] > 0 && guarded[1] > 0 && plain[0] > 0 && plain[1] > 0);
    assert(absent[0] > 0 && absent[1] > 0 && boundary[0] > 0 && boundary[1] > 0);
    std::cout << "WMB linker-centre marker matches ordinary W strips: "
              << guarded[0] + guarded[1] << " guarded, " << plain[0] + plain[1] << " plain, "
              << absent[0] + absent[1] << " absent, " << boundary[0] + boundary[1] << " boundary cells\n";
}
'''

E4_START = "\t\t\t\tif (!lfce[i]) \n\t\t\t\t{\n\t\t\t\t\tif (!(fce.f(i, i) & INTER)) \n"
E4_END = "INFINITE_ENERGY; \n\t\t\t\t\t}\n\t\t\t\t}\n"
E5_START = "\t\t\t\t\tif (!lfce[j]) \n\t\t\t\t\t{\n\t\t\t\t\t\tif (!(fce.f(j, j) & INTER)) \n"
E5_END = "else e[5] = w.f(i, j - 1) + mbl_nucleotide + INFINITE_ENERGY;\n\t\t\t\t\t}\n"
WMB_START = "\t\t\t\tif (i != number)\n\t\t\t\t\tif (!lfce[i]) wmb.f(i, j) = min(wmb.f(i, j), wmb.f(i + 1, j)"
WMB_END = "\n\n\t\t\t\te[1] = INFINITE_ENERGY;"
GUARD_I = "\n\t\t\t\t\t\t+ ((fce.f(i, i) & INTER) ? INFINITE_ENERGY : 0)"
GUARD_J = "\n\t\t\t\t\t\t+ ((fce.f(j, j) & INTER) ? INFINITE_ENERGY : 0)"


def extract(source, start, end):
    """Return one uniquely anchored block of the installed source."""
    if source.count(start) != 1:
        raise ValueError(f"Anchor count {source.count(start)}: {start[:40]!r}")
    begin = source.index(start)
    stop = source.index(end, begin) + len(end)
    return source[begin:stop]


class LinkerFillTests(unittest.TestCase):
    base = test_trace_states.TraceStateTests()

    @classmethod
    def setUpClass(cls):
        cls.linker3 = Path(os.environ["RNASTRUCTURE66_LINKER3"])
        cls.patched = Path(os.environ["RNASTRUCTURE66_PATCHED"])
        manifest = json.loads((COMPONENT / "manifest-linker-3.json").read_text())
        cls.source = (cls.linker3 / "src/algorithm.cpp").read_text()
        digest = hashlib.sha256((cls.linker3 / "src/algorithm.cpp").read_bytes()).hexdigest()
        if digest != manifest["patch"]["patched_source_sha256"]:
            raise ValueError("Installed linker-3 source hash mismatch")

    def make_program(self, mutate=None):
        e4 = extract(self.source, E4_START, E4_END)
        e5 = extract(self.source, E5_START, E5_END)
        wmb = extract(self.source, WMB_START, WMB_END)
        self.assertEqual(wmb.count(GUARD_I), 1)
        self.assertEqual(wmb.count(GUARD_J), 1)
        if mutate == "remove-guard":
            wmb = wmb.replace(GUARD_I, "").replace(GUARD_J, "")
        elif mutate == "swap-coordinate":
            wmb = wmb.replace("(fce.f(i, i) & INTER) ? INFINITE_ENERGY", "(fce.f(j, j) & INTER) ? INFINITE_ENERGY")
        return HARNESS.replace("@W_E4@", e4).replace("@W_E5@", e5).replace("@WMB_ADD@", wmb)

    def test_wmb_guard_matches_ordinary_w_marker(self):
        result = self.base.run_harness(self.make_program())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        print(result.stdout.strip())

    def test_guard_mutations_are_detected(self):
        for mutation in ("remove-guard", "swap-coordinate"):
            with self.subTest(mutation=mutation):
                result = self.base.run_harness(self.make_program(mutation))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("marker_wmb == marker_w", result.stderr)
        print("Removed and misplaced WMB guards rejected by the harness.")

    def test_traceback2_handlers_unchanged_in_linker3(self):
        # The W2/WMB2 extraction and the two traceback handlers are byte-identical
        # between the installations; the existing harness passes on version 3.
        program = self.base.make_program(root=self.linker3, manifest_name="manifest-linker-3.json")
        self.assertEqual(program, self.base.make_program(root=self.patched))
        result = self.base.run_harness(program)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        print("Version-3 source: " + result.stdout.strip())


if __name__ == "__main__":
    unittest.main()

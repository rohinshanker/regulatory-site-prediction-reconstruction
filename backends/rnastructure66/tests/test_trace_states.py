# SPDX-License-Identifier: GPL-2.0-only
"""Execute the actual new handlers against the independently extracted fill.

Small synthetic DP tables expose ties, strand boundaries and modified-base
predicates without relying on sequence panels to happen to visit every choice.
Thermodynamic functions are deterministic stand-ins; real energies are checked
by test_component against the standalone tools.
"""

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest


HARNESS = r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <random>
#include <vector>
using std::min;
const int INFINITE_ENERGY = 14000, SINGLE = 1, INTER = 2, minloop = 3;
struct Grid {
    int values[64][64], infinite = INFINITE_ENERGY;
    int &f(int i, int j) { return i > j ? infinite : values[i][j]; }
    void reset(int value) { for (auto &row: values) for (auto &cell: row) cell = value; }
};
struct Item { int i, j, open, energy, pair; };
struct Stack {
    std::vector<Item> items;
    void push(int i, int j, int o, int e, int p) { items.push_back({i,j,o,e,p}); }
};
struct Data { int init = 41; };
struct CT {};
std::vector<std::pair<int,int>> registered;
bool pairable[64][64];
void registerbasepair(CT *, int i, int j) { registered.push_back({i,j}); }
void errmsg(int, int) {}
bool can_pair(int i, int j) { return pairable[i][j]; }
int ptr_to_penalty(int, int, CT *, Data *) { return 7; }
int ptr_to_erg1(int, int, int, int, CT *, Data *) { return 11; }
int ptr_to_erg4(int, int, int, int, CT *, Data *, bool forced) {
    return forced ? INFINITE_ENERGY : 3;
}
int multi_tstkm(int, int, int, int, CT *) { return 5; }
int checknp(bool a, bool b) { return a || b ? INFINITE_ENERGY : 0; }
int main() {
    Grid vv, ww2, wwm2, ff;
    Grid *v=&vv, *w2=&ww2, *wmb2=&wwm2, *fce=&ff;
    Data dd; Data *data=&dd; CT cc; CT *ct=&cc;
    Stack ss; Stack *stack=&ss;
    bool mod[64], lfce[64], found;
    int number=30, e[6], ii, k, tracebackerror;
    // i==N, j==N+1, j==1; short/long spans and wrapped exterior cells.
    const int intervals[][2]={{2,20},{30,40},{20,31},{1,1},{2,4},{2,40}};
    int hits[5]={0}, modified=0, strips=0, dangles[3]={0};
    std::mt19937 gen(6604);
    for (const auto &interval: intervals) {
        for (int trial=0; trial<2000; ++trial) {
            const int i=interval[0], j=interval[1];
            vv.reset(1000); ww2.reset(1000); wwm2.reset(1000); ff.reset(0);
            for (int a=0;a<64;++a) {
                mod[a]=gen()%2; lfce[a]=gen()%2;
                for (int b=0;b<64;++b) {
                    pairable[a][b]=gen()%2;
                    ff.values[a][b]=gen()%2 ? SINGLE : 0;
                }
            }
            for (int a=i;a<=i+2;++a) for (int b=j-2;b<=j;++b) {
                if (b>=0) vv.values[a][b]=int(gen()%401)-200;
            }
            ww2.values[i+1][j]=int(gen()%401)-200;
            if (j>0) ww2.values[i][j-1]=int(gen()%401)-200;
            wwm2.values[i][j]=int(gen()%401)-200;
            if (trial%20==0) {
                // All legal stems tie at 7 or above; both strips tie at 7.
                vv.reset(0); ww2.reset(7); wwm2.reset(7);
                std::fill(mod,mod+64,false); std::fill(lfce,lfce+64,false);
            }
            // The oracle is the unchanged source fill, not a rewritten formula.
            @W2_FILL@
            if ((j-i-1)>(2*minloop+2) || j>number)
                w2->f(i,j)=min(w2->f(i,j),wmb2->f(i,j));
            const int energy=w2->f(i,j), pair=4;
            tracebackerror=0; ss.items.clear(); registered.clear();
            do {
                @HANDLERS@
                assert(false); // A new state must never reach ordinary W.
            } while (false);
            assert(!tracebackerror && ss.items.size()==1);
            auto child=ss.items[0]; ++hits[child.pair];
            assert(child.i<=child.j);
            if (child.pair==4) {
                assert(child.energy==energy);
                assert((child.i==i+1 && child.j==j && i!=number) ||
                       (child.i==i && child.j==j-1 && j!=number+1 && j!=1));
                ++strips;
            } else if (child.pair==3) {
                assert(child.i==i && child.j==j && child.energy==energy);
                assert((j-i-1)>(2*minloop+2) || j>number);
            } else {
                assert(child.pair==1);
                int a=child.i, b=child.j, cost=7;
                if (!registered.empty()) {
                    assert(registered.size()==1);
                    a=registered[0].first; b=registered[0].second;
                    assert(child.i==a+1 && child.j==b-1);
                    cost+=11; ++modified;
                }
                const int left=a-i, right=j-b;
                assert(left>=0 && left<=1 && right>=0 && right<=1);
                if (left) assert(i!=number);
                if (right) assert(j!=number+1 && j!=1);
                if (left && right) { cost+=5+checknp(lfce[i],lfce[j]); ++dangles[2]; }
                else if (left || right) { cost+=3; ++dangles[left?0:1]; }
                assert(energy==child.energy+cost);
            }
            if (trial%20==0 && i<j && i!=number) assert(child.pair==4 && child.i==i+1);
        }
    }
    assert(hits[1]>0 && hits[3]>0 && hits[4]>0 && modified>0 && strips>0);
    assert(dangles[0]>0 && dangles[1]>0 && dangles[2]>0);
    // WMB2: separately execute its unchanged fill and verify the selected
    // child values, INTER adjustment and tag preservation, including ties.
    for (int trial=0;trial<2000;++trial) {
        const int i=2,j=40,pair=3;
        ww2.reset(1000); wwm2.reset(1000); ff.reset(0);
        for (int x=i;x<=j;++x) {
            ww2.values[i][x]=int(gen()%201)-100;
            ww2.values[x+1][j]=int(gen()%201)-100;
        }
        wwm2.values[i+1][j]=int(gen()%201)-100;
        wwm2.values[i][j-1]=int(gen()%201)-100;
        // At most one linker centre belongs to an interval.
        if (trial%3==0) ff.values[i][i]=INTER;
        if (trial%3==1) ff.values[j][j]=INTER;
        @WMB2_FILL@
        const int energy=wmb2->f(i,j);
        tracebackerror=0; ss.items.clear(); registered.clear();
        do { @HANDLERS@ assert(false); } while(false);
        assert(!tracebackerror && registered.empty());
        if (ss.items.size()==2) {
            auto a=ss.items[0],b=ss.items[1];
            assert(a.pair==4 && b.pair==4 && a.i==i && b.j==j);
            assert(a.j+1==b.i && a.j!=number && a.energy+b.energy==energy);
        } else {
            assert(ss.items.size()==1);
            auto a=ss.items[0]; assert(a.pair==3);
            int x=a.i==i+1 ? i : j;
            assert(a.energy+((fce->f(x,x)&INTER)?data->init-INFINITE_ENERGY:0)==energy);
        }
    }
    // No matching transition must fail closed for either new state.
    for (int pair: {3,4}) {
        int i=2,j=20,energy=-1234;
        ww2.reset(1000); wwm2.reset(1000); vv.reset(1000); ff.reset(0);
        std::fill(mod,mod+64,false); std::fill(lfce,lfce+64,false);
        tracebackerror=0; ss.items.clear(); registered.clear();
        do { @HANDLERS@ assert(false); } while(false);
        assert(tracebackerror && ss.items.empty() && registered.empty());
    }
    std::cout << "12000 W2 cells, 2000 WMB2 cells, boundary/modification/tie/failure checks passed\n";
}
'''


class TraceStateTests(unittest.TestCase):
    def test_handlers_against_unchanged_fill(self):
        root = Path(os.environ["RNASTRUCTURE66_PATCHED"])
        source = (root / "src/algorithm.cpp").read_text()
        component = Path(__file__).resolve().parents[1]
        manifest = json.loads((component / "manifest.json").read_text())
        self.assertEqual(hashlib.sha256((root / "src/algorithm.cpp").read_bytes()).hexdigest(),
                         manifest["patch"]["patched_source_sha256"])
        w2 = source.split("// keep track of w2:", 1)[1].split("\n\t\t\t}\n", 1)[0]
        w2 = w2.replace("v.f(", "v->f(").replace("fce.f(", "fce->f(")
        wmb2 = source.split("//intermolecular folding:", 1)[1]
        wmb2 = wmb2.split("//search for an open bifurcation:", 1)[1]
        wmb2 = wmb2.split("w2->f(i, j) = min(w2->f(i, j), wmb2->f(i, j));", 1)[0]
        wmb2 = wmb2.replace("fce.f(", "fce->f(")
        handlers = source.split("// State 3 is WMB2:", 1)[1]
        handlers = handlers[handlers.index("if (pair == 3)"):]
        handlers = handlers.split("\t\tfound = true;\n\t\t// keep taking pairs", 1)[0]
        program = HARNESS.replace("@W2_FILL@", w2).replace("@WMB2_FILL@", wmb2)
        program = program.replace("@HANDLERS@", handlers)
        compiler = "clang++" if platform.system() == "Darwin" else "g++"
        with tempfile.TemporaryDirectory() as directory:
            cpp, executable = Path(directory) / "states.cpp", Path(directory) / "states"
            cpp.write_text(program)
            command = [compiler, "-std=c++11", "-O0", "-fsanitize=undefined", str(cpp), "-o", str(executable)]
            if platform.system() == "Darwin":
                subprocess.run(["xcode-select", "-p"], check=True, capture_output=True)
                sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
                command.extend(["-isysroot", sdk, "-isystem", f"{sdk}/usr/include/c++/v1"])
            subprocess.run(command, check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)], capture_output=True, text=True,
                                    env=dict(os.environ, UBSAN_OPTIONS="halt_on_error=1"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            print(result.stdout.strip())

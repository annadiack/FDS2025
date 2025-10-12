
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FDS FS25 – Exercise 1, Task 1 (Vector Clocks & Partial Order Graphs)
Author:Anna, Ehsan, Harshit, Gopal
Python 3

Usage examples:
  python main.py --in data.json --out vector_clocks.json \
                 --dot po_full.dot --dot-min po_reduced.dot \
                 --png po_full.png --png-min po_reduced.png

If you only want vector clocks JSON:
  python main.py --in data.json --out vector_clocks.json

Dependencies:
  pip install networkx matplotlib pydot
"""
import argparse
import json
from collections import defaultdict, deque
from typing import Dict, List
import networkx as nx

# Optional plotting (only if PNGs requested)
try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


def parse_args():
    ap = argparse.ArgumentParser(description="Compute vector clocks and partial order graphs from a Git-like JSON DAG.")
    ap.add_argument("--in", dest="inp", required=True, help="Input JSON path {Branch: {Commit: [parents...]}}")
    ap.add_argument("--out", dest="out_json", required=False, help="Output JSON path for {Commit: [vc...]}")
    ap.add_argument("--dot", dest="dot_full", required=False, help="Output DOT path for full partial order graph")
    ap.add_argument("--dot-min", dest="dot_min", required=False, help="Output DOT path for transitive reduction")
    ap.add_argument("--png", dest="png_full", required=False, help="Output PNG for full partial order graph")
    ap.add_argument("--png-min", dest="png_min", required=False, help="Output PNG for transitive reduction")
    return ap.parse_args()


def load_repo(path: str) -> Dict[str, Dict[str, List[str]]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def elementwise_max(a: List[int], b: List[int]) -> List[int]:
    return [max(x, y) for x, y in zip(a, b)]


def topo_sort(parents: Dict[str, List[str]]) -> List[str]:
    """Kahn's algorithm over parent->child edges."""
    from collections import defaultdict, deque
    children = defaultdict(list)
    indeg = defaultdict(int)
    nodes = set(parents.keys()) | {p for plist in parents.values() for p in plist}
    for child, parlist in parents.items():
        for p in parlist:
            children[p].append(child)
    for n in nodes:
        indeg[n] = 0
    for child, parlist in parents.items():
        for _ in parlist:
            indeg[child] += 1
    q = deque([n for n in nodes if indeg[n] == 0])
    topo = []
    while q:
        n = q.popleft()
        topo.append(n)
        for ch in children[n]:
            indeg[ch] -= 1
            if indeg[ch] == 0:
                q.append(ch)
    if len(topo) != len(nodes):
        raise ValueError("Input graph is not a DAG (cycle detected).")
    return topo


def compute_vector_clocks(repo: Dict[str, Dict[str, List[str]]]) -> (Dict[str, List[int]], Dict[str, str], Dict[str, int]):
    # Map branches to process indices (sorted for determinism)
    branches = sorted(repo.keys())
    proc_idx = {b: i for i, b in enumerate(branches)}
    N = len(branches)

    # Collect commit -> branch and parents
    commit_branch: Dict[str, str] = {}
    parents: Dict[str, List[str]] = defaultdict(list)
    for b, commits in repo.items():
        for c, parlist in commits.items():
            if c in commit_branch and commit_branch[c] != b:
                raise ValueError(f"Commit {c} appears in multiple branches: {commit_branch[c]} and {b}")
            commit_branch[c] = b
            parents[c].extend(parlist)

    topo = topo_sort(parents)
    zeros = [0] * N
    vc: Dict[str, List[int]] = {}

    for n in topo:
        base = zeros[:] if not parents[n] else zeros[:]
        for p in parents[n]:
            base = elementwise_max(base, vc[p])
        b = commit_branch.get(n)
        if b is None:
            raise ValueError(f"Commit {n} has no branch assignment in input.")
        base[proc_idx[b]] += 1
        vc[n] = base

    return vc, commit_branch, proc_idx


def causally_precedes(a: List[int], b: List[int]) -> bool:
    """Return True iff a <= b elementwise and a != b."""
    leq = all(x <= y for x, y in zip(a, b))
    lt = any(x < y for x, y in zip(a, b))
    return leq and lt


def build_partial_order(vc: Dict[str, List[int]]) -> nx.DiGraph:
    G = nx.DiGraph()
    commits = list(vc.keys())
    G.add_nodes_from(commits)
    for u in commits:
        for v in commits:
            if u == v:
                continue
            if causally_precedes(vc[u], vc[v]):
                G.add_edge(u, v)
    return G


def write_dot(graph: nx.DiGraph, path: str):
    try:
        nx.drawing.nx_pydot.write_dot(graph, path)
    except Exception as e:
        raise RuntimeError(f"Failed to write DOT to {path}: {e}")


def draw_png(graph: nx.DiGraph, path: str, title: str):
    global plt
    if plt is None:
        print(f"[WARN] matplotlib not available; skipping PNG '{path}'. Install 'matplotlib' to enable.")
        return

    pos = nx.spring_layout(graph, seed=42)
    plt.figure(figsize=(10, 7))
    nx.draw_networkx_nodes(graph, pos, node_size=800)
    nx.draw_networkx_labels(graph, pos, font_size=9)
    nx.draw_networkx_edges(graph, pos, arrows=True, arrowstyle='->')
    plt.title(title)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def main():
    args = parse_args()
    repo = load_repo(args.inp)
    vc, commit_branch, proc_idx = compute_vector_clocks(repo)

    # Write JSON if requested
    if args.out_json:
        vc_sorted = {k: vc[k] for k in sorted(vc.keys())}
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(vc_sorted, f, indent=2)

    # Build graphs if any of DOT/PNG requested
    if any([args.dot_full, args.dot_min, args.png_full, args.png_min]):
        G = build_partial_order(vc)
        GR = nx.transitive_reduction(G)

        if args.dot_full:
            write_dot(G, args.dot_full)
        if args.dot_min:
            write_dot(GR, args.dot_min)
        if args.png_full:
            draw_png(G, args.png_full, "Partial Order (All Causal Edges)")
        if args.png_min:
            draw_png(GR, args.png_min, "Partial Order (Transitive Reduction)")

    # Summary to stdout (useful for quick checks)
    print("Branches/process indices:", {k: v for k, v in proc_idx.items()})
    for c in sorted(vc.keys()):
        print(f"{c}: {vc[c]} (branch={commit_branch[c]})")


if __name__ == "__main__":
    main()

package ch.unibas.dmi.dbis.fds.p2p.chord.impl;

import ch.unibas.dmi.dbis.fds.p2p.chord.api.*;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.data.Identifier;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.data.IdentifierCircle;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.data.IdentifierCircularInterval;

import java.util.Map;
import java.util.Optional;

/**
 * Static-mode Chord peer (Figure 6) – Task 1 solution:
 * - joinAndUpdate (bootstrapping + update_others + data move)
 * - routing: findSuccessor / findPredecessor / closestPrecedingFinger
 * - finger maintenance: updateFingerTable
 * - key placement: lookupNodeForItem
 */
public class ChordPeer extends AbstractChordPeer {

    public ChordPeer(Identifier id, ChordNetwork network) {
        super(id, network);
    }

    /* ------------------ Routing (Figure 4) ------------------ */

    @Override
    public ChordNode findSuccessor(ChordNode caller, Identifier id) {
        ChordNode n0 = findPredecessor(caller, id);
        return n0.successor();
    }

    @Override
    public ChordNode findPredecessor(ChordNode caller, Identifier id) {
        ChordNode n = this;
        // while id ∉ (n, n.successor] on the identifier circle
        while (!inRightClosedInterval(id, n.id(), n.successor().id())) {
            n = n.closestPrecedingFinger(this, id);
        }
        return n;
    }

    @Override
    public ChordNode closestPrecedingFinger(ChordNode caller, Identifier id) {
        final int m = finger().size();
        for (int i = m; i >= 1; i--) {
            Optional<ChordNode> fi = finger().node(i);
            if (fi.isPresent()) {
                ChordNode c = fi.get();
                // c ∈ (n, id) ?
                if (inOpenInterval(c.id(), this.id(), id)) {
                    return c;
                }
            }
        }
        return this;
    }

    /* ------------------ Static join (Figure 6) ------------------ */

    @Override
    public synchronized void joinAndUpdate(ChordNode nprime) {
        final int m = finger().size();
        final IdentifierCircle<Identifier> circle = getNetwork().getIdentifierCircle();

        if (nprime == null) {
            // First node in the network (bootstrap)
            for (int i = 1; i <= m; i++) {
                ((AbstractChordPeer.ChordFingerTable) finger()).setNode(i, this);
            }
            setPredecessor(this);
        } else {
            // Initialize successor from existing network
            ChordNode succ = nprime.findSuccessor(this, this.id());
            ((AbstractChordPeer.ChordFingerTable) finger()).setNode(1, succ);
            setPredecessor(succ.predecessor());
            succ.setPredecessor(this);

            // Build full finger table deterministically (static case)
            for (int i = 2; i <= m; i++) {
                Identifier start = circle.getIdentifierAt(finger().start(i));
                ChordNode fingerI = nprime.findSuccessor(this, start);
                ((AbstractChordPeer.ChordFingerTable) finger()).setNode(i, fingerI);
            }

            // Update others (Figure 6) – corrected variant
            updateOthers();

            // Move keys that now belong to this node from my successor
            moveKeysFromSuccessor();
        }
    }

    private void updateOthers() {
        final int m = finger().size();
        final IdentifierCircle<Identifier> circle = getNetwork().getIdentifierCircle();
        for (int i = 1; i <= m; i++) {
            int offset = (int) Math.pow(2, i - 1);
            int idx = (this.id().getIndex() - offset);
            // wrap modulo 2^m
            int size = (int) Math.pow(2, m);
            if (idx < 0) idx += size;
            Identifier idToSearch = circle.getIdentifierAt(idx);
            ChordNode p = findPredecessor(this, idToSearch);
            // propagate along predecessors while our id still fits the i-th interval at p
            // (handles the 2-node bootstrap edge-case)
            ChordNode cur = p;
            while (true) {
                cur.updateFingerTable(this, i);
                ChordNode prev = cur.predecessor();
                if (prev == null || prev == cur) break;
                // Stop if at prev the interval for i no longer accepts "this"
                IdentifierCircularInterval intervalPrev = prev.finger().interval(i);
                if (!intervalPrev.containsInclusiveLeft(this.id())) break;
                cur = prev;
            }
        }
    }

    @Override
    public synchronized void updateFingerTable(ChordNode s, int i) {
        // If s is the i-th finger of this, update finger[i] and also predecessor chain as in Fig. 6
        Optional<ChordNode> maybeFi = finger().node(i);
        ChordNode fi = maybeFi.orElse(this.successor()); // be robust during early join

        IdentifierCircularInterval interval = finger().interval(i);
        // The well-known correction: left-inclusive on the interval test
        if (interval.containsInclusiveLeft(s.id())) {
            ((AbstractChordPeer.ChordFingerTable) finger()).setNode(i, s);
        }
    }

    /* ------------------ Data placement & transfer ------------------ */

    @Override
    protected ChordNode lookupNodeForItem(String key) {
        var hf = getNetwork().getHashFunction();
        var circle = getNetwork().getIdentifierCircle();
        Identifier kid = circle.getIdentifierAt(hf.hash(key) % getNetwork().size());
        return findSuccessor(this, kid);
    }

    /** Move keys for which this node is now responsible: keys in (predecessor, this] */
    private void moveKeysFromSuccessor() {
        ChordNode succ = successor();
        if (!(succ instanceof AbstractChordPeer)) return; // safety
        Map<String,String> succDump = ((AbstractChordPeer) succ).dump();
        for (Map.Entry<String,String> e : succDump.entrySet()) {
            String k = e.getKey();
            String v = e.getValue();
            if (lookupNodeForItem(k) == this) {
                // store locally via API (will be local because lookup resolves to this)
                this.store(this, k, v);
                // delete from successor
                succ.delete(this, k);
            }
        }
    }

    /* ------------------ Helpers ------------------ */

    private boolean inOpenInterval(Identifier x, Identifier a, Identifier b) {
        // (a, b) on the identifier circle
        return IdentifierCircularInterval.createOpen(a, b).contains(x);
    }

    private boolean inRightClosedInterval(Identifier x, Identifier a, Identifier b) {
        // (a, b] on the identifier circle
        return IdentifierCircularInterval.createLeftOpen(a, b).containsInclusiveRight(x);
    }
}

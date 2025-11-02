package ch.unibas.dmi.dbis.fds.p2p.chord.impl;

import ch.unibas.dmi.dbis.fds.p2p.chord.api.*;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.ChordNetwork;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.data.Identifier;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.data.IdentifierCircle;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.data.IdentifierCircularInterval;
import ch.unibas.dmi.dbis.fds.p2p.chord.api.math.CircularInterval;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Random;

import static ch.unibas.dmi.dbis.fds.p2p.chord.api.data.IdentifierCircularInterval.createOpen;

/**
 * Chord Peer implementation with all corrections from the exercise and Pamela
 * Zave's work.
 *
 * @author loris.sauter
 */
public class ChordPeer extends AbstractChordPeer {

  private Random random = new Random();

  protected ChordPeer(Identifier identifier, ChordNetwork network) {
    super(identifier, network);
  }

  @Override
  public ChordNode findSuccessor(ChordNode caller, Identifier id) {
    ChordNode p = findPredecessor(caller, id);
    if (p == null)
      return this;
    return ((AbstractChordPeer) p).getFingerTable().successor();
  }

  @Override
  public ChordNode findPredecessor(ChordNode caller, Identifier id) {
    ChordNode n = this;
    ChordNode succ = ((AbstractChordPeer) n).getFingerTable().successor();

    // Guard: if ring not initialized yet
    if (succ == null)
      return this;

    // Prevent infinite loops
    int maxIterations = (int) getNetwork().getIdentifierCircle().size();
    int iterations = 0;

    while (iterations++ < maxIterations) {
      Identifier nId = n.getIdentifier();
      Identifier succId = succ.getIdentifier();
      boolean inInterval;

      if (nId.compareTo(succId) < 0) {
        // Normal case: (n, succ]
        inInterval = id.compareTo(nId) > 0 && id.compareTo(succId) <= 0;
      } else if (nId.compareTo(succId) > 0) {
        // Wrap-around case: (n, max] U [0, succ]
        inInterval = id.compareTo(nId) > 0 || id.compareTo(succId) <= 0;
      } else {
        // n == succ, full circle
        inInterval = true;
      }

      if (inInterval) {
        break;
      }

      n = n.closestPrecedingFinger(n, id);
      succ = ((AbstractChordPeer) n).getFingerTable().successor();
      if (succ == null)
        break;
    }

    return n;
  }

  @Override
  public ChordNode closestPrecedingFinger(ChordNode caller, Identifier id) {
    final FingerTable ft = getFingerTable();
    // Scan from m down to 1 (1-based indexing)
    for (int k = ft.size(); k >= 1; k--) {
      Optional<ChordNode> fk = ft.node(k);
      if (fk.isPresent()) {
        ChordNode f = fk.get();
        // CRITICAL: Check liveness before considering this finger
        if (f instanceof AbstractChordPeer && ((AbstractChordPeer) f).status() == NodeStatus.OFFLINE) {
          continue;
        }
        // Check if finger is in open interval (this, id)
        IdentifierCircularInterval open = createOpen(this.getIdentifier(), id);
        if (open.contains(f.getIdentifier())) {
          return f;
        }
      }
    }
    return this;
  }

  @Override
  public void joinAndUpdate(ChordNode nprime) {
    if (nprime != null) {
      initFingerTable(nprime);
      updateOthers();

      // CRITICAL FIX: Move keys from successor (Question 1c)
      transferKeysFromSuccessor();

      // DEBUG: Verify initialization
      System.out.println("Node " + this.id().getIndex() + " joined via " + nprime.getIdentifier().getIndex());
      System.out.println("  Successor: " + this.successor().getIdentifier().getIndex());
      System.out.println("  Predecessor: " + this.predecessor().getIdentifier().getIndex());
    } else {
      // First node in the network
      for (int i = 1; i <= getNetwork().getNbits(); i++) {
        this.fingerTable.setNode(i, this);
      }
      this.setPredecessor(this);

      // DEBUG: Verify first node
      System.out.println("Node " + this.id().getIndex() + " is first node (bootstrap)");
    }
  }

  @Override
  public void joinOnly(ChordNode nprime) {
    setPredecessor(null);

    if (nprime == null) {
      // First node in the network
      ft().setNode(1, this);
      System.out.println("Node " + this.id().getIndex() + " joined as first node");
    } else {
      IdentifierCircle circle = new IdentifierCircle(getNetwork().getNbits());
      Identifier start1 = circle.getIdentifierAt(getFingerTable().start(1));
      ChordNode succ = nprime.findSuccessor(this, start1);
      ft().setNode(1, succ);

      System.out.println("Node " + this.id().getIndex() + " joined via " +
          nprime.getIdentifier().getIndex() + ", successor = " + succ.getIdentifier().getIndex());

      // CRITICAL FIX: Reconcile immediately (from PODC/best version)
      // Prevents ConnectedAppendages violations
      if (succ != null && succ != this) {
        ChordNode succSucc = succ.successor();
        if (succSucc != null && succSucc instanceof AbstractChordPeer &&
            ((AbstractChordPeer) succSucc).status() != NodeStatus.OFFLINE) {
          ft().setNode(2, succSucc);
          System.out.println("  Second successor set to: " + succSucc.getIdentifier().getIndex());
        }
      }
    }
  }

  private void initFingerTable(ChordNode bootstrap) {
    IdentifierCircle circle = new IdentifierCircle(getNetwork().getNbits());

    // 1) successor = find_successor(start(1))
    Identifier start1 = circle.getIdentifierAt(getFingerTable().start(1));
    ChordNode succ = bootstrap.findSuccessor(this, start1);
    if (succ == null) {
      System.err.println("Warning: No successor found for " + this.id());
      ft().setNode(1, this);
      setPredecessor(this);
      return;
    }
    ft().setNode(1, succ);

    // 2) predecessor = successor.predecessor ; successor.predecessor = this
    ChordNode succPred = succ.predecessor();
    if (succPred != null) {
      setPredecessor(succPred);
    } else {
      setPredecessor(this);
    }
    succ.setPredecessor(this);

    // 3) fill remaining fingers
    for (int i = 1; i < getFingerTable().size(); i++) {
      Identifier startNext = circle.getIdentifierAt(getFingerTable().start(i + 1));
      ChordNode fi = getFingerTable().node(i).orElse(succ);

      // Check if startNext is in [n, finger[i])
      IdentifierCircularInterval interval = IdentifierCircularInterval.createRightOpen(
          this.getIdentifier(), fi.getIdentifier());

      if (interval.contains(startNext)) {
        ft().setNode(i + 1, fi);
      } else {
        ft().setNode(i + 1, bootstrap.findSuccessor(this, startNext));
      }
    }
  }

  /**
   * CRITICAL FIX: The paper's formula is WRONG!
   * Should be (n - 2^(i-1) + 1) mod 2^m, NOT (n - 2^(i-1)) mod 2^m
   * 
   * This is crucial for the two-node bootstrap scenario mentioned in the
   * exercise.
   */
  private void updateOthers() {
    IdentifierCircle circle = new IdentifierCircle(getNetwork().getNbits());
    int m = getFingerTable().size();
    int modulo = 1 << m;

    for (int i = 1; i <= m; i++) {
      // CORRECTED FORMULA: Add +1 to fix the paper's bug
      int idx = ((this.getIdentifier().getIndex() - (1 << (i - 1)) + 1) % modulo + modulo) % modulo;
      Identifier start = circle.getIdentifierAt(idx);
      ChordNode p = findPredecessor(this, start);
      p.updateFingerTable(this, i);
    }
  }

  @Override
  public void updateFingerTable(ChordNode s, int i) {
    ChordNode curr = getFingerTable().node(i).orElse(null);
    if (curr == null) {
      ft().setNode(i, s);
      return;
    }

    // Check if s is in [n, finger[i])
    Identifier sId = s.getIdentifier();
    Identifier thisId = this.getIdentifier();
    Identifier currId = curr.getIdentifier();
    boolean inInterval;

    if (thisId.compareTo(currId) < 0) {
      // Normal interval [this, curr)
      inInterval = sId.compareTo(thisId) >= 0 && sId.compareTo(currId) < 0;
    } else if (thisId.compareTo(currId) > 0) {
      // Wrap-around interval [this, max] U [0, curr)
      inInterval = sId.compareTo(thisId) >= 0 || sId.compareTo(currId) < 0;
    } else {
      // thisId == currId, full circle
      inInterval = true;
    }

    if (inInterval) {
      ft().setNode(i, s);
      ChordNode p = this.predecessor();
      // CRITICAL: Check liveness and avoid infinite recursion
      if (p != null && p != this && p instanceof AbstractChordPeer &&
          ((AbstractChordPeer) p).status() != NodeStatus.OFFLINE) {
        p.updateFingerTable(s, i);
      }
    }
  }

  @Override
  public void notify(ChordNode nprime) {
    if (this.status() != NodeStatus.ONLINE)
      return;

    ChordNode pred = this.predecessor();
    boolean shouldUpdate = false;

    if (pred == null) {
      shouldUpdate = true;
    } else {
      Identifier nprimeId = nprime.getIdentifier();
      Identifier predId = pred.getIdentifier();
      Identifier thisId = this.getIdentifier();

      if (predId.compareTo(thisId) < 0) {
        // Normal interval (pred, this)
        shouldUpdate = nprimeId.compareTo(predId) > 0 && nprimeId.compareTo(thisId) < 0;
      } else if (predId.compareTo(thisId) > 0) {
        // Wrap-around interval (pred, max] ∪ [0, this)
        shouldUpdate = nprimeId.compareTo(predId) > 0 || nprimeId.compareTo(thisId) < 0;
      } else {
        // pred == this, full circle
        shouldUpdate = true;
      }
    }

    if (shouldUpdate) {
      ChordNode oldPred = this.predecessor();
      setPredecessor(nprime);

      // Transfer keys from this node to nprime for keys in (oldPred, nprime]
      // Only in dynamic mode - in static mode, keys are transferred during join
      if (getNetwork().isDynamic() && oldPred != null && oldPred != nprime && nprime instanceof AbstractChordPeer) {
        transferKeysToNewPredecessor(nprime, oldPred);
      }
    }
  }

  /**
   * Checks if target lies in the circular interval (from, to)
   * on the identifier circle modulo 2^m.
   *
   * @param target the identifier to check
   * @param from   the start of the interval (exclusive)
   * @param to     the end of the interval (exclusive)
   * @return true if target ∈ (from, to) on the circle
   */
  public static boolean isInInterval(Identifier target, Identifier from, Identifier to) {
    int cmpFromTo = from.compareTo(to);
    int cmpFromTarget = from.compareTo(target);
    int cmpTargetTo = target.compareTo(to);

    if (cmpFromTo < 0) {
      // Normal interval: (from, to)
      return cmpFromTarget < 0 && cmpTargetTo < 0;
    } else if (cmpFromTo > 0) {
      // Wrap-around interval: (from, max] ∪ [0, to)
      return cmpFromTarget < 0 || cmpTargetTo < 0;
    } else {
      // from == to → entire ring
      return true;
    }
  }

  @Override
  public void fixFingers() {
    if (this.status() != NodeStatus.ONLINE)
      return;

    int m = getFingerTable().size();
    if (m <= 1)
      return;

    int i = 1 + random.nextInt(m); // Random finger 1..m
    IdentifierCircle circle = new IdentifierCircle(getNetwork().getNbits());
    Identifier start = circle.getIdentifierAt(getFingerTable().start(i));
    ChordNode newFinger = findSuccessor(this, start);
    if (newFinger == null)
      return;
    ft().setNode(i, newFinger);
  }

  @Override
  public void stabilize() {
    if (this.status() != NodeStatus.ONLINE)
      return;

    ChordNode succ = getFingerTable().successor();
    if (succ == null)
      return;

    ChordNode x = succ.predecessor();
    if (x != null && x instanceof AbstractChordPeer &&
        ((AbstractChordPeer) x).status() != NodeStatus.OFFLINE) {

      Identifier xId = x.getIdentifier();
      Identifier thisId = this.getIdentifier();
      Identifier succId = succ.getIdentifier();
      boolean inInterval;

      if (thisId.compareTo(succId) < 0) {
        // Normal interval (this, succ)
        inInterval = xId.compareTo(thisId) > 0 && xId.compareTo(succId) < 0;
      } else if (thisId.compareTo(succId) > 0) {
        // Wrap-around interval (this, max] U [0, succ)
        inInterval = xId.compareTo(thisId) > 0 || xId.compareTo(succId) < 0;
      } else {
        // this == succ, full circle
        inInterval = true;
      }

      if (inInterval) {
        ft().setNode(1, x);
        succ = x;
      }
    }

    // CRITICAL FIX: Reconcile after potentially updating successor
    if (succ != null && succ instanceof AbstractChordPeer &&
        ((AbstractChordPeer) succ).status() != NodeStatus.OFFLINE) {
      ChordNode succSucc = succ.successor();
      if (succSucc != null && succSucc instanceof AbstractChordPeer &&
          ((AbstractChordPeer) succSucc).status() != NodeStatus.OFFLINE) {
        ft().setNode(2, succSucc);
      }
    }

    // Notify successor
    if (succ instanceof AbstractChordPeer && ((AbstractChordPeer) succ).status() != NodeStatus.OFFLINE) {
      succ.notify(this);
    }
  }

  @Override
  public void checkPredecessor() {
    ChordNode pred = this.predecessor();
    if (pred != null && pred instanceof AbstractChordPeer) {
      if (((AbstractChordPeer) pred).status() == NodeStatus.OFFLINE) {
        setPredecessor(null);
      }
    }
  }

  @Override
  public void checkSuccessor() {
    ChordNode succ = getFingerTable().successor();
    if (succ != null && succ instanceof AbstractChordPeer) {
      if (((AbstractChordPeer) succ).status() == NodeStatus.OFFLINE) {
        // CRITICAL FIX: Look for next alive successor in finger table
        ChordNode newSuccessor = null;
        for (int i = 2; i <= getFingerTable().size(); i++) {
          Optional<ChordNode> fingerOpt = getFingerTable().node(i);
          if (fingerOpt.isPresent()) {
            ChordNode finger = fingerOpt.get();
            if (finger instanceof AbstractChordPeer &&
                ((AbstractChordPeer) finger).status() != NodeStatus.OFFLINE) {
              newSuccessor = finger;
              break;
            }
          }
        }

        if (newSuccessor != null) {
          ft().setNode(1, newSuccessor);
          // Reconcile
          ChordNode succSucc = newSuccessor.successor();
          if (succSucc != null && succSucc instanceof AbstractChordPeer &&
              ((AbstractChordPeer) succSucc).status() != NodeStatus.OFFLINE) {
            ft().setNode(2, succSucc);
          }
        } else {
          // Fallback to self
          ft().setNode(1, this);
        }
      }
    }
  }

  @Override
  protected ChordNode lookupNodeForItem(String key) {
    int m = getFingerTable().size();
    int modulo = 1 << m;
    int idx = (key.hashCode() & 0x7fffffff) % modulo;
    IdentifierCircle circle = new IdentifierCircle(getNetwork().getNbits());
    Identifier id = circle.getIdentifierAt(idx);
    return findSuccessor(this, id);
  }

  // Helper methods for key transfer

  private ChordFingerTable ft() {
    return (ChordFingerTable) getFingerTable();
  }

  /**
   * Transfer keys from successor to this node during join.
   * Keys in range (predecessor, this] should be at this node.
   */
  private void transferKeysFromSuccessor() {
    ChordNode succ = getFingerTable().successor();
    if (!(succ instanceof AbstractChordPeer) || succ == this)
      return;

    AbstractChordPeer s = (AbstractChordPeer) succ;
    Map<String, String> toMove = new HashMap<>();

    // Move keys whose hashed id ∈ (pred, this]
    for (String key : s.keys()) {
      Identifier kid = keyToIdentifier(key);
      Identifier predId = this.predecessor() != null ? this.predecessor().getIdentifier() : this.getIdentifier();
      Identifier thisId = this.getIdentifier();

      boolean inInterval;
      if (predId.compareTo(thisId) < 0) {
        // Normal case: interval (predId, thisId]
        inInterval = kid.compareTo(predId) > 0 && kid.compareTo(thisId) <= 0;
      } else if (predId.compareTo(thisId) > 0) {
        // Wrap-around case: (predId, max] U [0, thisId]
        inInterval = kid.compareTo(predId) > 0 || kid.compareTo(thisId) <= 0;
      } else {
        // predId == thisId, full circle
        inInterval = true;
      }

      if (inInterval) {
        toMove.put(key, s.dump().get(key));
      }
    }

    for (Map.Entry<String, String> e : toMove.entrySet()) {
      s.delete(this, e.getKey());
      this.store(this, e.getKey(), e.getValue());
    }
  }

  /**
   * Transfer keys to new predecessor during notify.
   * Keys in range (oldPred, nprime] should move to nprime.
   */
  private void transferKeysToNewPredecessor(ChordNode nprime, ChordNode oldPred) {
    if (!(nprime instanceof AbstractChordPeer))
      return;

    AbstractChordPeer newPred = (AbstractChordPeer) nprime;
    Map<String, String> toMove = new HashMap<>();

    for (String key : this.keys()) {
      Identifier kid = keyToIdentifier(key);
      Identifier oldPredId = oldPred.getIdentifier();
      Identifier nprimeId = nprime.getIdentifier();

      boolean inInterval;
      if (oldPredId.compareTo(nprimeId) < 0) {
        // Normal case: interval (oldPredId, nprimeId]
        inInterval = kid.compareTo(oldPredId) > 0 && kid.compareTo(nprimeId) <= 0;
      } else if (oldPredId.compareTo(nprimeId) > 0) {
        // Wrap-around case: (oldPredId, max] U [0, nprimeId]
        inInterval = kid.compareTo(oldPredId) > 0 || kid.compareTo(nprimeId) <= 0;
      } else {
        // oldPredId == nprimeId, shouldn't happen but handle gracefully
        inInterval = false;
      }

      if (inInterval) {
        toMove.put(key, this.dump().get(key));
      }
    }

    for (Map.Entry<String, String> e : toMove.entrySet()) {
      this.delete(this, e.getKey());
      newPred.store(this, e.getKey(), e.getValue());
    }
  }

  // private Identifier keyToIdentifier(String key) {
  // int m = getFingerTable().size();
  // int modulo = 1 << m;
  // int idx = (key.hashCode() & 0x7fffffff) % modulo;
  // return new IdentifierCircle(getNetwork().getNbits()).getIdentifierAt(idx);
  // }
  private Identifier keyToIdentifier(String key) {
    try {
      int m = getFingerTable().size();
      int nbits = getNetwork().getNbits();
      int modulo = 1 << m;
      // Compute SHA-1 hash of the key
      MessageDigest sha1 = MessageDigest.getInstance("SHA-1");
      byte[] hashBytes = sha1.digest(key.getBytes(StandardCharsets.UTF_8));

      // Convert first 4 bytes to an int (32-bit)
      int hashInt = ((hashBytes[0] & 0xFF) << 24) |
          ((hashBytes[1] & 0xFF) << 16) |
          ((hashBytes[2] & 0xFF) << 8) |
          (hashBytes[3] & 0xFF);

      // Make it non-negative and modulo the identifier space
      int idx = (hashInt & 0x7FFFFFFF) % modulo;

      // Map to Identifier in the circle
      return new IdentifierCircle(nbits).getIdentifierAt(idx);

    } catch (NoSuchAlgorithmException e) {
      throw new RuntimeException("SHA-1 algorithm not available", e);
    }

  }

  @Override
  public String toString() {
    return String.format("ChordPeer{id=%d}", this.id().getIndex());
  }
}

import time
import threading
import random

# --- Global simulator state (from the template) ---------------------------------
nodes = []
buffer = {}  # items are in the form: node_id -> list of (msg_type, value)


def initialize(N: int):
    """
    Template entry: create N nodes and start their threads.
    """
    global nodes, buffer
    nodes = [Node(i) for i in range(N)]
    for node in nodes:
        node.start()


# --- Node implementation (template + filled-in logic) ---------------------------
class Node:
    """
    Simulator 'Node' as in the template. We keep the structure and only add the asked logic:
    - implement leader election with follower/candidate/leader roles
    - heartbeat sending and detection
    - candidacy backoff, voting, and winner determination
    - deliver() handling for 'HEARTBEAT', 'CANDIDACY', 'VOTE'
    """
    def __init__(self, id: int):
        # Template fields
        buffer[id] = []
        self.id = id
        self.working = True
        self.state = 'follower'  # starts as follower per task description

        # --- Leader election state (added) --------------------------------------
        self.known_leader = None              # currently accepted leader id (or None)
        self.last_hb = time.time()            # last time a heartbeat from any leader was observed
        self.last_own_hb_sent = 0.0           # last time this node (if leader) sent a heartbeat

        self.election_active = False          # are we in an election round?
        self.candidacy_wait_until = None      # random backoff end time (when to announce candidacy)
        self.candidacy_announced = False      # whether this candidate has broadcast its candidacy
        self.vote_collect_until = None        # 2s vote collection deadline after candidacy
        self.voted = False                    # whether this node has already voted in the *current* election
        self.votes = set()                    # ids of nodes that voted for *me* (only relevant if candidate)

    # -------------------------- Template functions ------------------------------
    def start(self):
        print(f'node {self.id} started')
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        """
        Busy-waiting loop from the template. We only add the election logic that
        must be triggered from inside the node's thread (as per instructions).
        """
        TICK = 0.1  # simulator tick (seconds)
        while True:
            now = time.time()

            # 1) Process incoming messages for this node (template pattern)
            while buffer[self.id]:
                msg_type, value = buffer[self.id].pop(0)
                if self.working:
                    self.deliver(msg_type, value)

            # 2) If we are a follower: detect leader crash (no heartbeat for > 1.0s) and prepare election
            if self.working and self.state == 'follower':
                if now - self.last_hb > 1.0:
                    # Assume leader crashed or no leader exists -> become candidate with random backoff
                    self._enter_candidate_mode(now)

            # 3) Candidate logic: handle random backoff, candidacy announcement, and vote counting
            if self.working and self.state == 'candidate':
                # If we were waiting before announcing candidacy, check if the wait time elapsed
                if (self.candidacy_wait_until is not None) and (not self.candidacy_announced) and (now >= self.candidacy_wait_until):
                    # Announce candidacy and self-vote
                    self._announce_candidacy(now)

                # If candidacy was announced, check if vote window elapsed
                if self.candidacy_announced and (self.vote_collect_until is not None) and (now >= self.vote_collect_until):
                    # Evaluate votes
                    self._finalize_election(now)

            # 4) Leader logic: send heartbeats every 0.5s
            if self.working and self.state == 'leader':
                if now - self.last_own_hb_sent >= 0.5:
                    self.broadcast('HEARTBEAT', self.id)
                    self.last_own_hb_sent = now

            time.sleep(TICK)

    def broadcast(self, msg_type, value):
        """
        Provided by the template: broadcast (msg_type, value) to all nodes.
        We only add the 'working' guard as in the template text.
        """
        if self.working:
            for node in nodes:
                buffer[node.id].append((msg_type, value))

    def crash(self):
        """
        Provided by the template: simulate crash -> stop working and clear inbound queue.
        """
        if self.working:
            self.working = False
            buffer[self.id] = []
            # On crash we forget transient election state (optional but helps realistic behavior)
            self.election_active = False
            self.candidacy_wait_until = None
            self.candidacy_announced = False
            self.vote_collect_until = None
            self.voted = False
            self.votes.clear()

    def recover(self):
        """
        Provided by the template: recover a crashed node.
        Keeping structure but ensuring it truly flips from not working to working.
        """
        if not self.working:
            buffer[self.id] = []
            self.working = True
            # On recover, resume as follower with unknown leader until a heartbeat comes
            self.state = 'follower'
            self.known_leader = None
            self.last_hb = time.time()
            self.election_active = False
            self.candidacy_wait_until = None
            self.candidacy_announced = False
            self.vote_collect_until = None
            self.voted = False
            self.votes.clear()

    # --------------------------- Election helpers (added) -----------------------
    def _enter_candidate_mode(self, now: float):
        """Follower -> Candidate with random backoff 1..3 seconds (resets any prior election)."""
        self.state = 'candidate'
        self.election_active = True
        backoff = random.randint(1, 3)  # inclusive 1..3 seconds
        self.candidacy_wait_until = now + backoff
        self.candidacy_announced = False
        self.vote_collect_until = None
        self.voted = False
        self.votes.clear()
        self.known_leader = None
        # No print required by spec, but helpful in the sample
        print(f'node {self.id} is starting an election.')

    def _announce_candidacy(self, now: float):
        """Broadcast candidacy and self-vote; open a 2s vote collection window."""
        self.candidacy_announced = True
        self.vote_collect_until = now + 2.0
        # Self-vote
        self.voted = True
        self.votes.add(self.id)
        print(f'node {self.id} voted to node {self.id}')
        # Broadcast candidacy
        self.broadcast('CANDIDACY', self.id)

    def _finalize_election(self, now: float):
        """Check majority and become leader or fall back to follower."""
        N = len(nodes)
        if len(self.votes) > N / 2.0:
            # Won the election
            self.state = 'leader'
            self.known_leader = self.id
            self.election_active = False
            self.candidacy_wait_until = None
            self.vote_collect_until = None
            print(f'node {self.id} detected node {self.id} as leader')
            # Heartbeats will be sent from the run() loop
        else:
            # Lost the election -> back to follower
            self._reset_to_follower(now)

    def _reset_to_follower(self, now: float):
        """Abort any ongoing election and become a follower again."""
        self.state = 'follower'
        self.election_active = False
        self.candidacy_wait_until = None
        self.candidacy_announced = False
        self.vote_collect_until = None
        self.voted = False
        self.votes.clear()
        # If a leader exists, last_hb will be updated by HEARTBEAT; otherwise keep timeout ticking
        self.last_hb = now

    # --------------------------- Message handling (asked) -----------------------
    def deliver(self, msg_type, value):
        """
        Implemented as requested by the exercise:
        - 'HEARTBEAT': accept sender as leader and abort any election
        - 'CANDIDACY': if we haven't voted yet in this round, vote for candidate; if we are
                        still in pre-announcement backoff as candidate, we resign
        - 'VOTE':      only relevant to candidates; count vote if addressed to self
        """
        now = time.time()

        if msg_type == 'HEARTBEAT':
            leader_id = value
            # Ignore our own heartbeats to prevent accidental state/log spam
            if leader_id == self.id:
                self.known_leader = leader_id
                self.last_hb = now
                return

            # Accept the heartbeat sender as leader and abort election
            prev_leader = self.known_leader
            self.known_leader = leader_id
            self.last_hb = now

            # If we are not leader, we are follower (but avoid re-printing every 0.5s)
            was_leader = (self.state == 'leader')
            if not was_leader:
                self.state = 'follower'

            # Abort any ongoing election (whoever we are)
            if self.election_active:
                self.election_active = False
                self.candidacy_wait_until = None
                self.candidacy_announced = False
                self.vote_collect_until = None
                self.voted = False
                self.votes.clear()

            # Print only when leader CHANGES or we just stepped down to follower
            if prev_leader != leader_id or was_leader:
                print(f'node {self.id} got a heartbeat and followed node {leader_id} as leader')

        elif msg_type == 'CANDIDACY':
            cand_id = value

            # If we are a candidate still in the random backoff (haven't announced yet),
            # we resign per spec and revert to follower.
            if self.state == 'candidate' and self.election_active and not self.candidacy_announced:
                self._reset_to_follower(now)

            # Vote exactly once per election (simple guard with self.voted).
            if not self.voted:
                # Broadcast our vote for cand_id
                self.voted = True
                self.broadcast('VOTE', (self.id, cand_id))
                print(f'node {self.id} voted to node {cand_id}')

        elif msg_type == 'VOTE':
            voter_id, cand_id = value
            # Only a candidate cares, and only if the vote is for this node
            if self.state == 'candidate' and self.candidacy_announced and cand_id == self.id:
                self.votes.add(voter_id)

        # else: ignore unknown message types silently


# --- Simple CLI runner (from the template) -------------------------------------
if __name__ == '__main__':
    try:
        N = int(input('number of nodes? '))
    except Exception:
        N = 3  # default to a small demo
    initialize(N)
    print('actions: state, crash, recover')
    while True:
        act = input('\t$ ').strip().lower()
        if act == 'crash':
            try:
                _id = int(input('\tid > '))
                if 0 <= _id < len(nodes):
                    nodes[_id].crash()
            except Exception:
                pass
        elif act == 'recover':
            try:
                _id = int(input('\tid > '))
                if 0 <= _id < len(nodes):
                    nodes[_id].recover()
            except Exception:
                pass
        elif act == 'state':
            for node in nodes:
                print(f'\t\tnode {node.id}: {node.state}')
        # You can add 'exit' to quit quickly during testing
        elif act in ('exit', 'quit'):
            break

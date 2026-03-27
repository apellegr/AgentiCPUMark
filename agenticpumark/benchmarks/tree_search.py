"""Tree Search benchmark.

AI agents use tree-search-like reasoning to plan sequences of actions:
exploring possible tool-call chains, evaluating outcomes, and backtracking.
This benchmark simulates MCTS and beam search patterns on decision trees
representative of agent planning workloads.
"""

import math
import random
from agenticpumark.benchmarks.base import BaseBenchmark

MCTS_SIMULATIONS = 50_000
MCTS_MAX_DEPTH = 30
BEAM_WIDTH = 64
BEAM_STEPS = 100
VOCAB_SIZE = 200


class MCTSNode:
    """Monte Carlo Tree Search node representing an agent action state."""

    __slots__ = ("children", "visits", "value", "action", "untried_actions")

    def __init__(self, action: int, num_actions: int = 10):
        self.children: list[MCTSNode] = []
        self.visits = 0
        self.value = 0.0
        self.action = action
        self.untried_actions = list(range(num_actions))

    def ucb1(self, parent_visits: int) -> float:
        if self.visits == 0:
            return float("inf")
        exploitation = self.value / self.visits
        exploration = math.sqrt(2.0 * math.log(parent_visits) / self.visits)
        return exploitation + exploration

    def best_child(self) -> "MCTSNode":
        return max(self.children, key=lambda c: c.ucb1(self.visits))

    def expand(self, rng: random.Random) -> "MCTSNode":
        action = self.untried_actions.pop(rng.randint(0, len(self.untried_actions) - 1))
        child = MCTSNode(action, num_actions=rng.randint(3, 10))
        self.children.append(child)
        return child


class TreeSearchBenchmark(BaseBenchmark):
    name = "tree_search"
    description = "MCTS and beam search simulating agent planning/reasoning"
    weight = 0.20

    def run_once(self) -> int:
        ops = 0
        ops += self._run_mcts()
        ops += self._run_beam_search()
        return ops

    def _run_mcts(self) -> int:
        """Run Monte Carlo Tree Search simulating agent action planning."""
        rng = random.Random(42)
        root = MCTSNode(action=-1, num_actions=15)
        ops = 0

        for _ in range(MCTS_SIMULATIONS):
            # Selection: walk down the tree using UCB1
            node = root
            depth = 0
            path = [node]

            while node.untried_actions == [] and node.children and depth < MCTS_MAX_DEPTH:
                node = node.best_child()
                path.append(node)
                depth += 1
                ops += 1

            # Expansion: add a new child if possible
            if node.untried_actions and depth < MCTS_MAX_DEPTH:
                node = node.expand(rng)
                path.append(node)
                ops += 1

            # Simulation: random rollout to estimate value
            rollout_value = 0.0
            for d in range(MCTS_MAX_DEPTH - depth):
                action = rng.randint(0, 9)
                # Simple reward heuristic: some actions are better than others
                rollout_value += (action - 4.5) / (d + 1)
                ops += 1

            # Backpropagation
            for ancestor in path:
                ancestor.visits += 1
                ancestor.value += rollout_value
                ops += 1

        return ops

    def _run_beam_search(self) -> int:
        """Run beam search simulating token-level agent output generation."""
        rng = random.Random(123)
        ops = 0

        # Initialize beam with starting hypotheses
        # Each beam entry: (cumulative_score, token_sequence)
        beam: list[tuple[float, list[int]]] = [(0.0, [0])]

        for step in range(BEAM_STEPS):
            candidates: list[tuple[float, list[int]]] = []

            for score, seq in beam:
                # Simulate scoring each possible next token
                for token_id in range(VOCAB_SIZE):
                    # Simulate a lightweight "score" computation
                    token_score = rng.gauss(0, 1)
                    # Add length penalty
                    length_penalty = 0.6 * math.log(len(seq) + 1)
                    new_score = score + token_score - length_penalty
                    candidates.append((new_score, seq + [token_id]))
                    ops += 1

            # Keep top-k candidates
            candidates.sort(key=lambda x: -x[0])
            beam = candidates[:BEAM_WIDTH]
            ops += len(candidates)  # sorting work

        return ops

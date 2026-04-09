"""
V.E.T. Layer 2: Entity Resolution & Knowledge Graph Construction

Resolves vendor entity identities across multiple data sources and
constructs an ownership graph to detect shell company cascades and
beneficial ownership obfuscation patterns.

This module encodes analytical heuristics developed through KYC/AML
due diligence work at YLG Bullion Group and ASUSTeK Computer, where
cross-border entity resolution was performed manually. V.E.T. automates
and scales these heuristics using graph-based techniques.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EntityNode:
    """A single entity in the V.E.T. knowledge graph."""

    entity_id: str
    name: str
    country: Optional[str] = None
    entity_type: str = "UNKNOWN"       # COMPANY, INDIVIDUAL, TRUST, FUND
    registration_number: Optional[str] = None
    jurisdiction: Optional[str] = None

    # Risk signals
    is_sanctioned: bool = False
    sanctions_proximity: int = 0       # Hops from nearest sanctioned entity
    beneficial_owners: List[str] = field(default_factory=list)  # entity_ids
    subsidiaries: List[str] = field(default_factory=list)        # entity_ids

    # Data provenance
    sources: List[str] = field(default_factory=list)  # which databases contributed
    confidence: float = 1.0            # entity identity confidence (0.0-1.0)


@dataclass
class OwnershipEdge:
    """Directed ownership relationship between two entities."""

    parent_id: str
    child_id: str
    ownership_percentage: Optional[float] = None
    relationship_type: str = "OWNS"    # OWNS, CONTROLS, MANAGES, ASSOCIATED
    source: str = ""


class EntityResolver:
    """
    Resolves entity identities across data sources and builds
    the V.E.T. knowledge graph for ownership chain analysis.

    The key capability is detecting shell company cascades — where
    a sanctioned or high-risk entity hides behind multiple layers
    of seemingly legitimate corporate structures across jurisdictions.

    This pattern was identified by the author during financial auditing
    work as the primary mechanism enabling illicit actors to embed
    themselves in legitimate supply chains (consistent with FATF
    Guidance on Beneficial Ownership for Legal Persons, March 2023).

    Usage:
        resolver = EntityResolver()
        resolver.add_entity(EntityNode(entity_id="E001", name="Acme Ltd"))
        resolver.add_ownership("E001", "E002", pct=51.0)
        risk = resolver.compute_ownership_depth_score("E003")
    """

    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self._nodes: Dict[str, EntityNode] = {}
        self._edges: List[OwnershipEdge] = []
        self._adjacency: Dict[str, List[str]] = {}  # parent -> [children]
        self._reverse_adjacency: Dict[str, List[str]] = {}  # child -> [parents]

    def add_entity(self, entity: EntityNode) -> None:
        """Add an entity node to the knowledge graph."""
        # Check for duplicate — merge if same entity from different source
        existing = self._find_duplicate(entity)
        if existing:
            self._merge_entities(existing, entity)
            logger.debug(f"Merged entity '{entity.name}' into existing '{existing}'")
        else:
            self._nodes[entity.entity_id] = entity
            self._adjacency[entity.entity_id] = []
            self._reverse_adjacency[entity.entity_id] = []
            logger.debug(f"Added entity: {entity.entity_id} — {entity.name}")

    def add_ownership(
        self,
        parent_id: str,
        child_id: str,
        ownership_pct: Optional[float] = None,
        relationship_type: str = "OWNS",
    ) -> None:
        """Add an ownership relationship edge to the graph."""
        if parent_id not in self._nodes or child_id not in self._nodes:
            logger.warning(f"Cannot add edge: one or both entities not found "
                          f"({parent_id} -> {child_id})")
            return

        edge = OwnershipEdge(
            parent_id=parent_id,
            child_id=child_id,
            ownership_percentage=ownership_pct,
            relationship_type=relationship_type,
        )
        self._edges.append(edge)
        self._adjacency[parent_id].append(child_id)
        self._reverse_adjacency[child_id].append(parent_id)

    def get_ownership_chain(
        self, entity_id: str, direction: str = "upstream"
    ) -> List[List[str]]:
        """
        Trace all ownership chains from an entity.

        Args:
            entity_id: Starting entity
            direction: "upstream" (who owns this?) or "downstream" (what does it own?)

        Returns:
            List of ownership chains, each chain is a list of entity_ids
        """
        if entity_id not in self._nodes:
            return []

        chains = []
        adj = (self._reverse_adjacency if direction == "upstream"
               else self._adjacency)

        def dfs(current: str, path: List[str], visited: Set[str]) -> None:
            path.append(current)
            visited.add(current)

            neighbors = adj.get(current, [])
            if not neighbors or len(path) > self.max_depth:
                chains.append(path.copy())
            else:
                for neighbor in neighbors:
                    if neighbor not in visited:  # Prevent cycles
                        dfs(neighbor, path, visited)
                if not any(n for n in neighbors if n not in visited):
                    chains.append(path.copy())

            path.pop()

        dfs(entity_id, [], set())
        return chains

    def compute_ownership_depth_score(self, entity_id: str) -> float:
        """
        Compute a risk score based on beneficial ownership chain depth.

        Deep, complex ownership structures are a primary indicator of
        shell company usage. Score increases with chain depth and
        cross-jurisdictional complexity.

        Score range: 0.0 (simple, transparent) to 1.0 (deeply opaque)
        """
        if entity_id not in self._nodes:
            return 0.0

        chains = self.get_ownership_chain(entity_id, direction="upstream")
        if not chains:
            return 0.0

        max_depth = max(len(chain) for chain in chains)

        # Count unique jurisdictions across the ownership chain
        jurisdictions = set()
        for chain in chains:
            for eid in chain:
                entity = self._nodes.get(eid)
                if entity and entity.jurisdiction:
                    jurisdictions.add(entity.jurisdiction)

        # Depth score: normalized against max_depth config
        depth_score = min(max_depth / self.max_depth, 1.0)

        # Jurisdiction complexity bonus (cross-border structures are higher risk)
        jurisdiction_bonus = min((len(jurisdictions) - 1) * 0.1, 0.3)

        score = min(depth_score + jurisdiction_bonus, 1.0)
        logger.debug(f"Ownership depth score for {entity_id}: {score:.3f} "
                    f"(depth={max_depth}, jurisdictions={len(jurisdictions)})")
        return round(score, 3)

    def propagate_sanctions_risk(self) -> int:
        """
        Propagate sanctions risk through ownership chains.

        If a parent entity is sanctioned, all entities it owns/controls
        are flagged with a proximity score indicating their distance from
        the designated entity.

        This implements the V.E.T. "network-aware" sanctions screening
        described in White Paper Section 3.2.2 — going beyond direct
        name matching to catch shell company structures.

        Returns:
            Number of entities flagged through propagation
        """
        flagged = 0
        sanctioned_ids = {
            eid for eid, entity in self._nodes.items()
            if entity.is_sanctioned
        }

        for sanctioned_id in sanctioned_ids:
            # BFS outward from each sanctioned entity
            queue = [(sanctioned_id, 0)]
            visited = {sanctioned_id}

            while queue:
                current_id, hop = queue.pop(0)
                if hop > 0:
                    entity = self._nodes.get(current_id)
                    if entity:
                        if entity.sanctions_proximity == 0 or hop < entity.sanctions_proximity:
                            entity.sanctions_proximity = hop
                            flagged += 1

                for child_id in self._adjacency.get(current_id, []):
                    if child_id not in visited and hop < self.max_depth:
                        visited.add(child_id)
                        queue.append((child_id, hop + 1))

        logger.info(f"Sanctions risk propagated: {flagged} entities flagged")
        return flagged

    def get_entity(self, entity_id: str) -> Optional[EntityNode]:
        """Retrieve an entity node by ID."""
        return self._nodes.get(entity_id)

    def get_graph_stats(self) -> Dict:
        """Return knowledge graph statistics for monitoring."""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "sanctioned_nodes": sum(1 for e in self._nodes.values() if e.is_sanctioned),
            "nodes_with_sanctions_proximity": sum(
                1 for e in self._nodes.values() if e.sanctions_proximity > 0
            ),
        }

    def _find_duplicate(self, entity: EntityNode) -> Optional[str]:
        """
        Check if an entity already exists in the graph under a different name.
        Uses registration number as the primary deduplication key.
        """
        if entity.registration_number:
            for eid, existing in self._nodes.items():
                if (existing.registration_number == entity.registration_number and
                        existing.jurisdiction == entity.jurisdiction):
                    return eid
        return None

    def _merge_entities(self, existing_id: str, new_entity: EntityNode) -> None:
        """Merge a new entity's data into an existing entity node."""
        existing = self._nodes[existing_id]
        # Add new source
        for source in new_entity.sources:
            if source not in existing.sources:
                existing.sources.append(source)
        # Update sanctions status (if either source says sanctioned, flag it)
        if new_entity.is_sanctioned:
            existing.is_sanctioned = True
        # Increase confidence if multiple sources agree
        existing.confidence = min(existing.confidence + 0.1, 1.0)

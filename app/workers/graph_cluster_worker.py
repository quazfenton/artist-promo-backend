"""
Graph Builder and Cluster Worker - builds relationship graphs and detects communities
"""
import asyncio
import json
import time
from typing import Dict, Any, Optional, List
import logging
from app.workers.queue_adapter import dequeue_job, complete_job, fail_job, push_to_dead_letter, fingerprint, seen_before, mark_seen
from app.models.staging import ResolvedEntity, GraphNode, GraphEdge, ClusterRun
from app.models.database import SessionLocal, Contact, ContactType, Platform
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, and_, or_
import os
import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities
import uuid

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)

class GraphBuilderClusterWorker:
    def __init__(self):
        self.running = True

    def build_graph_from_entities(self, resolved_entities: List[ResolvedEntity]) -> nx.Graph:
        """
        Build a graph from resolved entities based on relationships
        """
        G = nx.Graph()
        
        # Add nodes for each resolved entity
        for entity in resolved_entities:
            node_id = f"entity_{entity.id}"
            G.add_node(node_id, 
                      entity_id=entity.id,
                      name=entity.name,
                      email=entity.email,
                      contact_type=entity.contact_type,
                      follower_count=entity.follower_count,
                      confidence_score=entity.confidence_score)
        
        # Add edges based on relationships
        # This is a simplified example - in reality, you'd have more sophisticated relationship detection
        for i, entity1 in enumerate(resolved_entities):
            for j, entity2 in enumerate(resolved_entities[i+1:], i+1):
                # Add edges based on shared characteristics
                edge_weight = 0
                
                # Same domain in email suggests relationship
                if (entity1.email and entity2.email and 
                    entity1.email.split('@')[1] == entity2.email.split('@')[1]):
                    edge_weight += 10
                
                # Same social handles suggest relationship
                if entity1.social_handles and entity2.social_handles:
                    for platform in ['instagram', 'twitter']:
                        if (entity1.social_handles.get(platform) and 
                            entity2.social_handles.get(platform) and
                            entity1.social_handles[platform] == entity2.social_handles[platform]):
                            edge_weight += 15
                
                # Similar follower counts suggest relationship
                if abs(entity1.follower_count - entity2.follower_count) < 1000:
                    edge_weight += 5
                
                # Add edge if there's a meaningful relationship
                if edge_weight > 0:
                    node1_id = f"entity_{entity1.id}"
                    node2_id = f"entity_{entity2.id}"
                    G.add_edge(node1_id, node2_id, weight=edge_weight, relation_type="similar")
        
        return G

    def detect_communities(self, graph: nx.Graph) -> List[List[str]]:
        """
        Detect communities in the graph using modularity-based clustering
        """
        try:
            communities = list(greedy_modularity_communities(graph))
            # Convert frozensets to lists
            return [list(community) for community in communities]
        except Exception as e:
            logger.error(f"Error detecting communities: {str(e)}")
            # Fallback: return each node as its own community
            return [[node] for node in graph.nodes()]

    def calculate_cluster_metrics(self, graph: nx.Graph, community: List[str]) -> Dict[str, Any]:
        """
        Calculate metrics for a community/cluster
        """
        subgraph = graph.subgraph(community)
        
        # Calculate various metrics
        metrics = {
            "member_count": len(community),
            "total_follower_count": sum(
                graph.nodes[node].get('follower_count', 0) for node in community
            ),
            "avg_confidence_score": sum(
                graph.nodes[node].get('confidence_score', 0) for node in community
            ) / len(community) if community else 0,
            "density": nx.density(subgraph) if len(community) > 1 else 0,
            "avg_clustering_coefficient": nx.average_clustering(subgraph),
            "influence_score": self.calculate_influence_score(graph, community)
        }
        
        return metrics

    def calculate_influence_score(self, graph: nx.Graph, community: List[str]) -> float:
        """
        Calculate influence score for a community based on network centrality
        """
        if not community:
            return 0.0
        
        # Calculate betweenness centrality as a measure of influence
        try:
            betweenness = nx.betweenness_centrality(graph)
            avg_betweenness = sum(betweenness[node] for node in community) / len(community)
        except:
            avg_betweenness = 0.0
        
        # Calculate eigenvector centrality
        try:
            eigenvector = nx.eigenvector_centrality(graph, max_iter=1000)
            avg_eigenvector = sum(eigenvector[node] for node in community) / len(community)
        except:
            avg_eigenvector = 0.0
        
        # Combine metrics for influence score
        influence_score = (avg_betweenness * 0.6) + (avg_eigenvector * 0.4)
        
        # Normalize to 0-100 scale
        return min(influence_score * 1000, 100.0)  # Scale factor to bring to reasonable range

    async def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single graph building and clustering job"""
        job_type = job["type"]
        
        if job_type == "graph:build":
            resolved_job_id = job["params"].get("resolved_job_id")
            
            db = SessionLocal()
            try:
                # Get resolved entities to build graph from
                # For now, we'll get all resolved entities (in practice, you might filter by recent ones)
                resolved_entities = db.query(ResolvedEntity).all()
                
                if not resolved_entities:
                    logger.info("No resolved entities found for graph building")
                    return {
                        "status": "completed",
                        "entities_processed": 0,
                        "nodes_created": 0,
                        "edges_created": 0,
                        "clusters_detected": 0
                    }
                
                # Build graph from entities
                graph = self.build_graph_from_entities(resolved_entities)
                
                # Save nodes to database
                node_mapping = {}  # Map graph node IDs to DB node IDs
                for graph_node_id in graph.nodes():
                    node_attrs = graph.nodes[graph_node_id]
                    db_node = GraphNode(
                        entity_id=node_attrs.get('entity_id'),
                        node_type=node_attrs.get('contact_type', 'unknown'),
                        name=node_attrs.get('name', ''),
                        properties={
                            'email': node_attrs.get('email'),
                            'follower_count': node_attrs.get('follower_count'),
                            'confidence_score': node_attrs.get('confidence_score')
                        }
                    )
                    db.add(db_node)
                    db.flush()  # Get the ID
                    node_mapping[graph_node_id] = db_node.id
                
                # Save edges to database
                for u, v, edge_attrs in graph.edges(data=True):
                    db_edge = GraphEdge(
                        source_node_id=node_mapping[u],
                        target_node_id=node_mapping[v],
                        weight=edge_attrs.get('weight', 1),
                        relation_type=edge_attrs.get('relation_type', 'related')
                    )
                    db.add(db_edge)
                
                db.commit()
                
                # Detect communities/clusters
                communities = self.detect_communities(graph)
                
                # Save cluster runs
                run_id = str(uuid.uuid4())
                cluster_count = 0
                
                for i, community in enumerate(communities):
                    # Calculate metrics for this community
                    metrics = self.calculate_cluster_metrics(graph, community)
                    
                    # Create cluster run record
                    cluster_run = ClusterRun(
                        run_id=run_id,
                        cluster_id=f"cluster_{i}",
                        node_ids=community,
                        cluster_properties=metrics
                    )
                    db.add(cluster_run)
                    cluster_count += 1
                
                db.commit()
                
                # Queue outreach decision job
                from app.workers.queue_adapter import enqueue_job
                enqueue_job(
                    job_type="outreach:decision",
                    params={"cluster_run_id": run_id},
                    source="graph_builder",
                    priority=job.get("priority", 5)
                )
                
                return {
                    "status": "completed",
                    "entities_processed": len(resolved_entities),
                    "nodes_created": len(graph.nodes()),
                    "edges_created": len(graph.edges()),
                    "clusters_detected": cluster_count,
                    "graph_density": nx.density(graph) if len(graph.nodes()) > 1 else 0
                }
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error building graph: {str(e)}")
                raise
            finally:
                db.close()
        else:
            raise ValueError(f"Unknown job type: {job_type}")

    async def run(self):
        """Main worker loop"""
        logger.info("Starting Graph Builder and Cluster Worker...")
        
        while self.running:
            try:
                # Get a job from the graph queue
                job = dequeue_job("queue:graph", timeout=5)
                
                if job:
                    logger.info(f"Processing graph building job: {job['job_id']}")
                    
                    # Check for duplicate job using fingerprint
                    fp = fingerprint(job)
                    if seen_before(fp):
                        logger.info(f"Skipping duplicate graph building job: {job['job_id']}")
                        continue
                    
                    mark_seen(fp)
                    
                    try:
                        # Process the job
                        result = await self.process_job(job)
                        
                        # Mark job as completed
                        complete_job(job["job_id"], result)
                        
                        logger.info(f"Graph building job {job['job_id']} completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Graph building job {job['job_id']} failed: {str(e)}")
                        fail_job(job["job_id"], str(e))
                        push_to_dead_letter(job, str(e))
                else:
                    # No job available, sleep briefly
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Graph Builder Worker interrupted")
                self.running = False
            except Exception as e:
                logger.error(f"Graph Builder Worker error: {str(e)}")
                await asyncio.sleep(5)  # Wait before continuing to avoid rapid error loops

    def stop(self):
        """Stop the worker"""
        self.running = False

# For running as standalone script
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Graph Builder and Cluster Worker")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers")
    args = parser.parse_args()
    
    async def main():
        # Create and run worker(s)
        workers = []
        tasks = []
        for _ in range(args.concurrency):
            worker = GraphBuilderClusterWorker()
            workers.append(worker)
            # Run each worker in a separate task and store the reference
            task = asyncio.create_task(worker.run())
            tasks.append(task)

        try:
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Shutting down workers...")
            for worker in workers:
                worker.stop()
            # Wait for tasks to complete gracefully
            await asyncio.gather(*tasks, return_exceptions=True)
    
    asyncio.run(main())
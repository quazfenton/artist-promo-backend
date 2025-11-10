"""Curator network graph analysis"""
import networkx as nx
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from app.models.database import Contact, Playlist
import json

class CuratorNetworkBuilder:
    """Build and analyze curator relationship networks"""
    
    def __init__(self, db: Session):
        self.db = db
        self.graph = nx.Graph()
    
    def build_curator_network(self) -> Dict:
        """Build network graph of curator relationships"""
        
        # Get all active curators and playlists
        curators = self.db.query(Contact).filter(
            Contact.deleted_at.is_(None),
            Contact.contact_type == 'playlist_curator'
        ).all()
        
        playlists = self.db.query(Playlist).filter(
            Playlist.deleted_at.is_(None)
        ).all()
        
        # Add nodes
        for curator in curators:
            self.graph.add_node(f"curator_{curator.id}", 
                              type='curator',
                              name=curator.full_name,
                              followers=curator.follower_count,
                              score=curator.priority_score)
        
        for playlist in playlists:
            self.graph.add_node(f"playlist_{playlist.id}",
                              type='playlist', 
                              name=playlist.name,
                              followers=playlist.follower_count)
        
        # Add edges (curator-playlist relationships)
        for playlist in playlists:
            if playlist.curator_id:
                self.graph.add_edge(f"curator_{playlist.curator_id}", 
                                  f"playlist_{playlist.id}",
                                  weight=playlist.follower_count)
        
        # Calculate network metrics
        metrics = self._calculate_network_metrics()
        
        return {
            'nodes': len(self.graph.nodes()),
            'edges': len(self.graph.edges()),
            'metrics': metrics,
            'top_influencers': self._get_top_influencers(),
            'clusters': self._detect_clusters()
        }
    
    def _calculate_network_metrics(self) -> Dict:
        """Calculate network analysis metrics"""
        
        # Centrality measures
        betweenness = nx.betweenness_centrality(self.graph)
        closeness = nx.closeness_centrality(self.graph)
        degree = nx.degree_centrality(self.graph)
        
        return {
            'density': nx.density(self.graph),
            'avg_clustering': nx.average_clustering(self.graph),
            'top_betweenness': sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_closeness': sorted(closeness.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_degree': sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    
    def _get_top_influencers(self) -> List[Dict]:
        """Identify top influencer curators"""
        
        influencers = []
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get('type') == 'curator':
                # Calculate influence score
                degree = self.graph.degree(node_id)
                followers = data.get('followers', 0)
                
                influence_score = (degree * 0.4) + (followers / 10000 * 0.6)
                
                influencers.append({
                    'curator_id': node_id.replace('curator_', ''),
                    'name': data.get('name'),
                    'followers': followers,
                    'connections': degree,
                    'influence_score': round(influence_score, 2)
                })
        
        return sorted(influencers, key=lambda x: x['influence_score'], reverse=True)[:20]
    
    def _detect_clusters(self) -> List[Dict]:
        """Detect curator clusters/communities"""
        
        try:
            # Use community detection
            communities = nx.community.greedy_modularity_communities(self.graph)
            
            clusters = []
            for i, community in enumerate(communities):
                curators_in_cluster = [node for node in community if node.startswith('curator_')]
                
                if len(curators_in_cluster) >= 3:  # Minimum cluster size
                    cluster_data = {
                        'cluster_id': i,
                        'size': len(curators_in_cluster),
                        'curators': curators_in_cluster[:10],  # Top 10
                        'avg_followers': self._get_cluster_avg_followers(curators_in_cluster)
                    }
                    clusters.append(cluster_data)
            
            return sorted(clusters, key=lambda x: x['avg_followers'], reverse=True)
        
        except Exception:
            return []
    
    def _get_cluster_avg_followers(self, curator_nodes: List[str]) -> float:
        """Calculate average followers for cluster"""
        
        total_followers = 0
        count = 0
        
        for node in curator_nodes:
            data = self.graph.nodes[node]
            total_followers += data.get('followers', 0)
            count += 1
        
        return total_followers / count if count > 0 else 0

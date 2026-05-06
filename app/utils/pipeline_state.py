"""
Pipeline State Management

Provides state machine enforcement for the contact discovery pipeline.
Ensures valid state transitions and tracks state history.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from app.models.staging import ResolvedEntity, PipelineState


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    pass


# Define valid state transitions
VALID_TRANSITIONS = {
    PipelineState.SCRAPED.value: [
        PipelineState.NORMALIZED.value,
        PipelineState.FAILED.value,
    ],
    PipelineState.NORMALIZED.value: [
        PipelineState.CLUSTERED.value,
        PipelineState.FAILED.value,
    ],
    PipelineState.CLUSTERED.value: [
        PipelineState.SCORED.value,
        PipelineState.FAILED.value,
    ],
    PipelineState.SCORED.value: [
        PipelineState.VERIFIED.value,
        PipelineState.FAILED.value,
    ],
    PipelineState.VERIFIED.value: [
        PipelineState.READY_TO_SEND.value,
        PipelineState.FAILED.value,
    ],
    PipelineState.READY_TO_SEND.value: [
        PipelineState.CONTACTED.value,
        PipelineState.FAILED.value,
    ],
    PipelineState.CONTACTED.value: [],  # Terminal state
    PipelineState.FAILED.value: [
        PipelineState.SCRAPED.value,  # Allow retry from failed
    ],
}


class PipelineStateMachine:
    """
    State machine for managing contact discovery pipeline states.
    
    Enforces valid state transitions and maintains state history
    for audit and debugging purposes.
    """

    def __init__(self, db: Session):
        """
        Initialize state machine with database session
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_state(self, entity: ResolvedEntity) -> PipelineState:
        """
        Get current state of entity
        
        Args:
            entity: ResolvedEntity object
            
        Returns:
            Current PipelineState
        """
        return PipelineState(entity.pipeline_state)

    def can_transition(self, from_state: PipelineState, to_state: PipelineState) -> bool:
        """
        Check if transition is valid
        
        Args:
            from_state: Current state
            to_state: Target state
            
        Returns:
            True if transition is valid, False otherwise
        """
        allowed = VALID_TRANSITIONS.get(from_state.value, [])
        return to_state.value in allowed

    def transition(
        self,
        entity: ResolvedEntity,
        to_state: PipelineState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Transition entity to new state with validation
        
        Args:
            entity: ResolvedEntity to transition
            to_state: Target state
            metadata: Optional metadata about the transition
            
        Returns:
            True if transition successful
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        from_state = PipelineState(entity.pipeline_state)
        
        # Validate transition
        if not self.can_transition(from_state, to_state):
            error_msg = (
                f"Invalid state transition: {from_state.value} -> {to_state.value}. "
                f"Allowed transitions: {VALID_TRANSITIONS.get(from_state.value, [])}"
            )
            logger.error(error_msg)
            raise StateTransitionError(error_msg)
        
        # Record state transition in history
        transition_record = {
            "from": from_state.value,
            "to": to_state.value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        # Update state history
        if entity.state_history is None:
            entity.state_history = []
        entity.state_history.append(transition_record)
        
        # Update current state
        entity.pipeline_state = to_state.value
        
        # Update timestamps based on state
        if to_state == PipelineState.VERIFIED:
            entity.last_verified_at = datetime.utcnow()
        elif to_state == PipelineState.READY_TO_SEND:
            entity.outreach_ready = True
        elif to_state == PipelineState.FAILED:
            entity.outreach_ready = False
        
        logger.info(
            f"State transition: {entity.id} {from_state.value} -> {to_state.value}",
            extra={
                "entity_id": entity.id,
                "from_state": from_state.value,
                "to_state": to_state.value,
                "metadata": metadata,
            }
        )
        
        return True

    def batch_transition(
        self,
        entities: List[ResolvedEntity],
        to_state: PipelineState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Transition multiple entities to new state
        
        Args:
            entities: List of ResolvedEntity objects
            to_state: Target state
            metadata: Optional metadata for all transitions
            
        Returns:
            Dict with statistics about the batch operation
        """
        success_count = 0
        failed_count = 0
        errors = []
        
        for entity in entities:
            try:
                self.transition(entity, to_state, metadata)
                success_count += 1
            except StateTransitionError as e:
                failed_count += 1
                errors.append({
                    "entity_id": entity.id,
                    "error": str(e),
                })
        
        # Commit all changes at once
        self.db.commit()
        
        logger.info(
            f"Batch transition completed: {success_count} succeeded, {failed_count} failed",
            extra={
                "success_count": success_count,
                "failed_count": failed_count,
                "to_state": to_state.value,
            }
        )
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(entities),
            "errors": errors,
        }

    def get_entities_by_state(
        self,
        state: PipelineState,
        limit: int = 100
    ) -> List[ResolvedEntity]:
        """
        Get entities in a specific state
        
        Args:
            state: State to filter by
            limit: Maximum number of entities to return
            
        Returns:
            List of ResolvedEntity objects
        """
        return (
            self.db.query(ResolvedEntity)
            .filter(ResolvedEntity.pipeline_state == state.value)
            .limit(limit)
            .all()
        )

    def get_state_statistics(self) -> Dict[str, int]:
        """
        Get count of entities in each state
        
        Returns:
            Dict mapping state names to counts
        """
        stats = {}
        for state in PipelineState:
            count = (
                self.db.query(ResolvedEntity)
                .filter(ResolvedEntity.pipeline_state == state.value)
                .count()
            )
            stats[state.value] = count
        
        return stats

    def reset_entity(self, entity: ResolvedEntity) -> bool:
        """
        Reset entity to initial state (for retry)
        
        Args:
            entity: ResolvedEntity to reset
            
        Returns:
            True if reset successful
        """
        return self.transition(entity, PipelineState.SCRAPED, {"reason": "manual_reset"})

    def fail_entity(
        self,
        entity: ResolvedEntity,
        error_message: str
    ) -> bool:
        """
        Mark entity as failed with error message
        
        Args:
            entity: ResolvedEntity to fail
            error_message: Reason for failure
            
        Returns:
            True if transition successful
        """
        return self.transition(
            entity,
            PipelineState.FAILED,
            {"error": error_message, "failed_at": datetime.utcnow().isoformat()}
        )


def create_state_machine(db: Session) -> PipelineStateMachine:
    """
    Factory function to create state machine
    
    Args:
        db: SQLAlchemy database session
        
    Returns:
        PipelineStateMachine instance
    """
    return PipelineStateMachine(db)

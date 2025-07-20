"""Enhanced operational tools with validation and rich results."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from schemas.agent_data import OperationResult, ValidationResult
from schemas.ticket import TicketUpdate
from .ticket_management import TicketManager
from .enhanced_context import EnhancedContextManager

logger = logging.getLogger(__name__)


class EnhancedOperationsManager:
    """Enhanced operations with validation and rich context."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ticket_manager = TicketManager()
        self.context_manager = EnhancedContextManager(db)

    async def validate_operation_before_execution(
        self,
        operation_type: str,
        target_id: int,
        parameters: Dict[str, Any]
    ) -> ValidationResult:
        """Pre-validate operations to prevent failures."""

        blocking_errors = []
        warnings = []
        context_notes = []
        recommendations = []

        # Get current state for validation
        try:
            if operation_type == "update_ticket":
                current_ticket = await self.ticket_manager.get_ticket(self.db, target_id)
                if not current_ticket:
                    blocking_errors.append(f"Ticket {target_id} not found")
                    return ValidationResult(
                        is_valid=False,
                        confidence=0.0,
                        blocking_errors=blocking_errors,
                        warnings=warnings,
                        context_notes=context_notes,
                        recommendations=recommendations,
                        estimated_impact={"risk": "high", "reason": "target not found"}
                    )

                # Validate specific update parameters
                validation_result = await self._validate_ticket_update(current_ticket, parameters)
                return validation_result

            elif operation_type == "assign_ticket":
                return await self._validate_ticket_assignment(target_id, parameters)

            elif operation_type == "close_ticket":
                return await self._validate_ticket_closure(target_id, parameters)

            else:
                warnings.append(f"Validation not implemented for operation type: {operation_type}")
                return ValidationResult(
                    is_valid=True,
                    confidence=0.5,
                    blocking_errors=blocking_errors,
                    warnings=warnings,
                    context_notes=context_notes,
                    recommendations=recommendations,
                    estimated_impact={"risk": "unknown"}
                )

        except Exception as e:
            logger.error(f"Validation failed for {operation_type}: {e}")
            blocking_errors.append(f"Validation error: {str(e)}")

            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                blocking_errors=blocking_errors,
                warnings=warnings,
                context_notes=context_notes,
                recommendations=recommendations,
                estimated_impact={"risk": "high", "reason": "validation_failed"}
            )

    async def execute_ticket_operation(
        self,
        operation_type: str,
        ticket_id: int,
        parameters: Dict[str, Any],
        skip_validation: bool = False
    ) -> OperationResult:
        """Execute ticket operation with rich result context."""

        start_time = datetime.now(timezone.utc)

        # Pre-validation if not skipped
        if not skip_validation:
            validation = await self.validate_operation_before_execution(
                operation_type, ticket_id, parameters
            )
            if not validation.is_valid:
                return OperationResult(
                    success=False,
                    action_taken=f"Validation failed for {operation_type}",
                    execution_metadata={
                        "validation_errors": validation.blocking_errors,
                        "execution_time": (datetime.now(timezone.utc) - start_time).total_seconds()
                    },
                    error_details={
                        "type": "validation_error",
                        "validation_result": validation.dict()
                    }
                )

        # Get current state before operation
        try:
            previous_state = await self._capture_ticket_state(ticket_id)
        except Exception as e:
            logger.warning(f"Could not capture previous state for ticket {ticket_id}: {e}")
            previous_state = None

        # Execute the operation
        try:
            if operation_type == "update_ticket":
                result = await self._execute_ticket_update(ticket_id, parameters)
            elif operation_type == "assign_ticket":
                result = await self._execute_ticket_assignment(ticket_id, parameters)
            elif operation_type == "close_ticket":
                result = await self._execute_ticket_closure(ticket_id, parameters)
            else:
                raise ValueError(f"Unknown operation type: {operation_type}")

            # Get new state after operation
            new_state = await self._capture_ticket_state(ticket_id)

            # Calculate execution time
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            return OperationResult(
                success=True,
                action_taken=f"Successfully executed {operation_type}",
                previous_state=previous_state,
                new_state=new_state,
                affected_tickets=[ticket_id],
                affected_users=self._extract_affected_users(previous_state, new_state),
                execution_metadata={
                    "operation_type": operation_type,
                    "execution_time": execution_time,
                    "parameters_used": parameters,
                    "timestamp": start_time.isoformat()
                },
                rollback_available=self._can_rollback_operation(operation_type, previous_state),
                rollback_instructions=self._generate_rollback_instructions(
                    operation_type, previous_state, new_state
                ) if previous_state else None
            )

        except Exception as e:
            logger.error(f"Failed to execute {operation_type} on ticket {ticket_id}: {e}")

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            return OperationResult(
                success=False,
                action_taken=f"Failed to execute {operation_type}",
                previous_state=previous_state,
                execution_metadata={
                    "operation_type": operation_type,
                    "execution_time": execution_time,
                    "error_occurred": True
                },
                error_details={
                    "type": "execution_error",
                    "message": str(e),
                    "operation": operation_type,
                    "parameters": parameters
                }
            )

    # Validation methods
    async def _validate_ticket_update(self, current_ticket, parameters: Dict[str, Any]) -> ValidationResult:
        """Validate ticket update parameters."""
        # Implementation details for update validation
        # Check field validity, permission requirements, etc.
        pass

    async def _validate_ticket_assignment(self, ticket_id: int, parameters: Dict[str, Any]) -> ValidationResult:
        """Validate ticket assignment."""
        # Implementation details for assignment validation
        pass

    async def _validate_ticket_closure(self, ticket_id: int, parameters: Dict[str, Any]) -> ValidationResult:
        """Validate ticket closure."""
        # Implementation details for closure validation
        pass

    # Execution methods
    async def _execute_ticket_update(self, ticket_id: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ticket update."""
        update_data = TicketUpdate(**parameters)
        updated_ticket = await self.ticket_manager.update_ticket(self.db, ticket_id, update_data)
        return {"updated_ticket_id": ticket_id, "success": True}

    async def _execute_ticket_assignment(self, ticket_id: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ticket assignment."""
        assignee_email = parameters.get("assignee_email")
        assignee_name = parameters.get("assignee_name", assignee_email)

        update_data = TicketUpdate(
            Assigned_Email=assignee_email,
            Assigned_Name=assignee_name
        )

        updated_ticket = await self.ticket_manager.update_ticket(self.db, ticket_id, update_data)
        return {"assigned_to": assignee_email, "success": True}

    async def _execute_ticket_closure(self, ticket_id: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ticket closure."""
        resolution = parameters.get("resolution", "Resolved")
        status_id = parameters.get("status_id", 4)  # Assuming 4 = Closed

        update_data = TicketUpdate(
            Ticket_Status_ID=status_id,
            Resolution=resolution
        )

        updated_ticket = await self.ticket_manager.update_ticket(self.db, ticket_id, update_data)
        return {"closed": True, "resolution": resolution}

    # Helper methods
    async def _capture_ticket_state(self, ticket_id: int) -> Dict[str, Any]:
        """Capture current ticket state for comparison."""
        try:
            context = await self.context_manager.get_ticket_full_context(ticket_id, include_deep_history=False)
            return {
                "ticket": context.ticket,
                "message_count": len(context.messages),
                "attachment_count": len(context.attachments),
                "capture_time": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.warning(f"Could not capture state for ticket {ticket_id}: {e}")
            return {"error": str(e)}

    def _extract_affected_users(self, previous_state: Optional[Dict], new_state: Optional[Dict]) -> List[str]:
        """Extract list of users affected by the operation."""
        affected = []

        if previous_state and new_state:
            # Contact user
            contact_email = new_state.get("ticket", {}).get("Ticket_Contact_Email")
            if contact_email:
                affected.append(contact_email)

            # Previous assignee
            prev_assignee = previous_state.get("ticket", {}).get("Assigned_Email")
            if prev_assignee:
                affected.append(prev_assignee)

            # New assignee
            new_assignee = new_state.get("ticket", {}).get("Assigned_Email")
            if new_assignee and new_assignee != prev_assignee:
                affected.append(new_assignee)

        return list(set(affected))  # Remove duplicates

    def _can_rollback_operation(self, operation_type: str, previous_state: Optional[Dict]) -> bool:
        """Determine if operation can be rolled back."""
        if not previous_state:
            return False

        # Simple rollback rules
        rollback_operations = ["update_ticket", "assign_ticket"]
        return operation_type in rollback_operations

    def _generate_rollback_instructions(
        self,
        operation_type: str,
        previous_state: Optional[Dict],
        new_state: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Generate instructions for rolling back the operation."""
        if not previous_state:
            return None

        if operation_type == "update_ticket":
            prev_ticket = previous_state.get("ticket", {})
            return {
                "operation": "update_ticket",
                "restore_values": {
                    "Assigned_Email": prev_ticket.get("Assigned_Email"),
                    "Ticket_Status_ID": prev_ticket.get("Ticket_Status_ID"),
                    "Priority_ID": prev_ticket.get("Priority_ID"),
                    "Resolution": prev_ticket.get("Resolution")
                }
            }

        return None

__all__ = ["EnhancedOperationsManager"]

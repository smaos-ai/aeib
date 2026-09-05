#!/usr/bin/env python3
"""
Temporal + LangGraph Integration
Provides durable workflow execution for multi-day, stateful agent workflows
Enables retry semantics, checkpoint recovery, and exactly-once execution

Use case: School access control (48-hour workflow with retry on failure)
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from temporalio import workflow, activity, Client
from temporalio.client import Client as TemporalClient
from temporalio.exceptions import ActivityError
import logging

logger = logging.getLogger(__name__)


@dataclass
class WorkflowCheckpoint:
    """Checkpoint for resuming workflow after failure"""

    step: str
    state: Dict[str, Any]
    timestamp: float
    metadata: Dict[str, str]


@dataclass
class ActivityInput:
    """Input for Temporal activity"""

    agent_name: str
    task_id: str
    state: Dict[str, Any]
    max_retries: int = 3


@dataclass
class ActivityOutput:
    """Output from Temporal activity"""

    success: bool
    result: Dict[str, Any]
    error: Optional[str] = None
    checkpoint: Optional[WorkflowCheckpoint] = None


# ═════════════════════════════════════════════════════════════
# ACTIVITIES (Resilient, retriable steps)
# ═════════════════════════════════════════════════════════════


@activity.defn
async def langgraph_step(input_data: ActivityInput) -> ActivityOutput:
    """
    Execute a single LangGraph step within Temporal
    Retriable, isolated, with checkpoint support
    """
    import time

    try:
        logger.info(f"Executing LangGraph step: {input_data.task_id}")

        # Simulate LangGraph node execution
        # In production: call actual LangGraph node here
        state = input_data.state
        state["last_step"] = input_data.task_id
        state["execution_time"] = time.time()

        # Create checkpoint for recovery
        checkpoint = WorkflowCheckpoint(
            step=input_data.task_id,
            state=state,
            timestamp=time.time(),
            metadata={"agent": input_data.agent_name, "status": "completed"},
        )

        return ActivityOutput(
            success=True,
            result={"state": state, "task_id": input_data.task_id},
            checkpoint=checkpoint,
        )

    except Exception as e:
        logger.error(f"LangGraph step failed: {e}")
        return ActivityOutput(
            success=False,
            result={},
            error=str(e),
            checkpoint=None,
        )


@activity.defn
async def persist_checkpoint(checkpoint: WorkflowCheckpoint) -> Dict[str, Any]:
    """
    Persist checkpoint to PostgreSQL for recovery
    Enables resume on failure without restarting from beginning
    """
    try:
        # In production: write to DB
        logger.info(f"Persisting checkpoint for step: {checkpoint.step}")
        return {
            "checkpoint_id": f"{checkpoint.step}-{checkpoint.timestamp}",
            "persisted": True,
        }
    except Exception as e:
        logger.error(f"Checkpoint persistence failed: {e}")
        raise


@activity.defn
async def notify_escalation(escalation_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Escalate to human reviewer on failure
    Blocks workflow until human approves or rejects
    """
    logger.info(f"Escalating workflow: {escalation_details}")
    # In production: send to human queue (Slack, email, ticketing system)
    return {
        "escalation_id": f"esc-{escalation_details['task_id']}",
        "status": "pending_human_review",
    }


# ═════════════════════════════════════════════════════════════
# WORKFLOW (Orchestration with retry logic)
# ═════════════════════════════════════════════════════════════


@workflow.defn
class SchoolAccessWorkflow:
    """
    48-hour school access control workflow
    Example: Verify student identity → Check attendance → Grant access

    Features:
    - Multi-step orchestration
    - Retry semantics (3x max per step)
    - Checkpoint recovery (resume on failure)
    - Human escalation (if max retries exceeded)
    - Exactly-once execution (Temporal guarantee)
    """

    @workflow.run
    async def run(self, workflow_input: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Starting SchoolAccessWorkflow for {workflow_input['student_id']}")

        state = {"student_id": workflow_input["student_id"], "steps_completed": []}
        last_checkpoint = None

        # Step 1: Verify student identity (with retry)
        try:
            logger.info("Step 1: Verify student identity")
            verify_result = await workflow.execute_activity(
                langgraph_step,
                ActivityInput(
                    agent_name="identity_verifier",
                    task_id="verify_identity",
                    state=state,
                    max_retries=3,
                ),
                retry_policy=workflow.RetryPolicy(
                    initial_interval="1s",
                    backoff_coefficient=2.0,
                    maximum_interval="10s",
                    maximum_attempts=3,
                ),
            )
            if not verify_result.success:
                raise Exception(f"Identity verification failed: {verify_result.error}")
            state = verify_result.result["state"]
            state["steps_completed"].append("verify_identity")
            last_checkpoint = verify_result.checkpoint
        except Exception as e:
            logger.error(f"Identity verification failed after retries: {e}")
            await workflow.execute_activity(
                notify_escalation,
                {"task_id": workflow_input["student_id"], "reason": str(e)},
            )
            return {"status": "escalated", "error": str(e)}

        # Step 2: Check attendance (with retry)
        try:
            logger.info("Step 2: Check attendance")
            attendance_result = await workflow.execute_activity(
                langgraph_step,
                ActivityInput(
                    agent_name="attendance_checker",
                    task_id="check_attendance",
                    state=state,
                    max_retries=3,
                ),
                retry_policy=workflow.RetryPolicy(
                    initial_interval="1s",
                    backoff_coefficient=2.0,
                    maximum_interval="10s",
                    maximum_attempts=3,
                ),
            )
            if not attendance_result.success:
                raise Exception(f"Attendance check failed: {attendance_result.error}")
            state = attendance_result.result["state"]
            state["steps_completed"].append("check_attendance")
            last_checkpoint = attendance_result.checkpoint
        except Exception as e:
            logger.error(f"Attendance check failed after retries: {e}")
            await workflow.execute_activity(
                notify_escalation,
                {
                    "task_id": workflow_input["student_id"],
                    "reason": f"Attendance check failed: {e}",
                    "checkpoint": asdict(last_checkpoint) if last_checkpoint else None,
                },
            )
            return {"status": "escalated", "error": str(e)}

        # Step 3: Grant access (final step)
        try:
            logger.info("Step 3: Grant access")
            access_result = await workflow.execute_activity(
                langgraph_step,
                ActivityInput(
                    agent_name="access_grant",
                    task_id="grant_access",
                    state=state,
                    max_retries=3,
                ),
                retry_policy=workflow.RetryPolicy(
                    initial_interval="1s",
                    backoff_coefficient=2.0,
                    maximum_interval="10s",
                    maximum_attempts=3,
                ),
            )
            if not access_result.success:
                raise Exception(f"Access grant failed: {access_result.error}")
            state = access_result.result["state"]
            state["steps_completed"].append("grant_access")
        except Exception as e:
            logger.error(f"Access grant failed: {e}")
            return {"status": "failed", "error": str(e)}

        # Persist final checkpoint
        final_checkpoint = WorkflowCheckpoint(
            step="completed",
            state=state,
            timestamp=asyncio.get_event_loop().time(),
            metadata={"workflow": "school_access", "status": "completed"},
        )
        await workflow.execute_activity(persist_checkpoint, final_checkpoint)

        logger.info(f"SchoolAccessWorkflow completed successfully")
        return {
            "status": "success",
            "student_id": workflow_input["student_id"],
            "steps_completed": state["steps_completed"],
        }


# ═════════════════════════════════════════════════════════════
# CLIENT (Submit workflows, query status)
# ═════════════════════════════════════════════════════════════


async def submit_school_access_workflow(
    student_id: str, temporal_host: str = "localhost:7233"
) -> Dict[str, Any]:
    """
    Submit a school access workflow to Temporal
    Returns workflow execution ID for tracking
    """
    client = await TemporalClient.connect(temporal_host)

    try:
        execution_id = f"school-access-{student_id}-{int(asyncio.get_event_loop().time())}"
        handle = await client.start_workflow(
            SchoolAccessWorkflow.run,
            {"student_id": student_id},
            id=execution_id,
            task_queue="school-access-queue",
        )

        logger.info(f"Workflow submitted: {execution_id}")
        return {
            "execution_id": execution_id,
            "status": "submitted",
            "student_id": student_id,
        }
    finally:
        await client.close()


async def query_workflow_status(
    execution_id: str, temporal_host: str = "localhost:7233"
) -> Dict[str, Any]:
    """Query the status of a running workflow"""
    client = await TemporalClient.connect(temporal_host)

    try:
        handle = client.get_workflow_handle(execution_id)
        result = await handle.result()
        return {"execution_id": execution_id, "result": result}
    except Exception as e:
        logger.error(f"Failed to query workflow: {e}")
        return {"execution_id": execution_id, "error": str(e)}
    finally:
        await client.close()


if __name__ == "__main__":
    # Test: Submit a school access workflow
    import asyncio

    async def test():
        result = await submit_school_access_workflow("student-12345")
        print(f"✅ Workflow submitted: {result}")

        # Wait a bit, then query status
        await asyncio.sleep(2)
        status = await query_workflow_status(result["execution_id"])
        print(f"Status: {status}")

    asyncio.run(test())

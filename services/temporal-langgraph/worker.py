#!/usr/bin/env python3
"""
Temporal Worker — Process SchoolAccessWorkflow activities
Runs in Docker container, connects to Temporal server, executes activities
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from temporal_langgraph import (
    SchoolAccessWorkflow,
    langgraph_step,
    persist_checkpoint,
    notify_escalation,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start Temporal worker"""
    # Connect to Temporal server
    client = await Client.connect("localhost:7233")

    # Create worker
    worker = Worker(
        client,
        task_queue="school-access-queue",
        workflows=[SchoolAccessWorkflow],
        activities=[langgraph_step, persist_checkpoint, notify_escalation],
    )

    logger.info("🚀 Temporal Worker starting...")
    async with worker:
        logger.info("✅ Worker connected to Temporal server")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

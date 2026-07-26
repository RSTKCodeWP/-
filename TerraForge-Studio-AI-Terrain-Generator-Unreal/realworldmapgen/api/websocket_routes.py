"""
WebSocket routes for real-time terrain generation updates
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active WebSocket connections for each task
active_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manages WebSocket connections for task updates"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept WebSocket connection and register it for a task"""
        await websocket.accept()

        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()

        self.active_connections[task_id].add(websocket)
        logger.info(f"WebSocket connected for task {task_id}. Total connections: {len(self.active_connections[task_id])}")

    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove WebSocket connection"""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)

            # Clean up empty task entries
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

        logger.info(f"WebSocket disconnected for task {task_id}")

    async def send_update(self, task_id: str, message: dict):
        """Send update to all connections for a specific task"""
        if task_id not in self.active_connections:
            return

        # Convert message to JSON
        json_message = json.dumps(message)

        # Send to all connections for this task
        dead_connections = set()
        for connection in self.active_connections[task_id]:
            try:
                await connection.send_text(json_message)
            except Exception as e:
                logger.error(f"Failed to send message to WebSocket: {e}")
                dead_connections.add(connection)

        # Remove dead connections
        for connection in dead_connections:
            self.disconnect(connection, task_id)

    async def broadcast(self, message: dict):
        """Broadcast message to all active connections"""
        json_message = json.dumps(message)

        for task_id, connections in self.active_connections.items():
            dead_connections = set()
            for connection in connections:
                try:
                    await connection.send_text(json_message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to WebSocket: {e}")
                    dead_connections.add(connection)

            # Remove dead connections
            for connection in dead_connections:
                self.disconnect(connection, task_id)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/generation/{task_id}")
async def websocket_generation_updates(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time terrain generation updates

    Args:
        task_id: The task ID to subscribe to
    """
    await manager.connect(websocket, task_id)

    try:
        # Imported here to avoid a circular import at module load time.
        from ..core.generator_provider import get_generator

        generator = get_generator()

        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "task_id": task_id,
            "message": f"Connected to task {task_id}"
        })

        # Poll for task updates and send via WebSocket
        last_status = None
        while True:
            try:
                # Get current task status
                status = generator.get_task_status(task_id)

                if status:
                    # Send the full serialized status so clients receive the
                    # same shape as GET /api/status/{task_id}, including
                    # warnings and the typed result.
                    status_dict = {
                        "type": "status_update",
                        **status.model_dump(mode="json"),
                    }


                    if status_dict != last_status:
                        await websocket.send_json(status_dict)
                        last_status = status_dict

                    # If task is completed or failed, send final update and close
                    if status.status in ['completed', 'failed']:
                        await asyncio.sleep(1)  # Give client time to receive
                        break
                else:
                    # Task not found
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Task {task_id} not found"
                    })
                    break

                # Wait before next poll
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in WebSocket polling loop: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    finally:
        manager.disconnect(websocket, task_id)


@router.websocket("/ws/status")
async def websocket_global_status(websocket: WebSocket):
    """
    WebSocket endpoint for global status updates (all tasks)
    """
    await websocket.accept()

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to global status updates"
        })

        # Keep connection alive and send periodic updates
        while True:
            try:
                # Imported here to avoid a circular import at module load time.
                from ..core.generator_provider import get_generator

                # list_tasks() is synchronous and returns pydantic models, which
                # must be dumped to plain JSON before send_json() can encode them.
                tasks = get_generator().list_tasks()

                await websocket.send_json({
                    "type": "tasks_update",
                    "tasks": [task.model_dump(mode="json") for task in tasks],
                    "count": len(tasks)
                })

                # Wait before next update
                await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"Error in global status WebSocket: {e}")
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected from global status")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# Helper function to send updates from generation code
async def send_task_update(task_id: str, status: dict):
    """
    Helper function to send task updates to WebSocket clients
    Can be called from the terrain generation code
    """
    await manager.send_update(task_id, status)


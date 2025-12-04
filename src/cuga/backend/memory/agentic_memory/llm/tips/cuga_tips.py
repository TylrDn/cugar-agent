import json
import logging
import uuid
from typing import Optional, Tuple

from cuga.backend.memory.agentic_memory.llm.tips.cuga_tips_extractor import TipsExtractor
from cuga.backend.memory.agentic_memory.llm.tips.trajectory_ir_generator import generate_trajectory_ir

logger = logging.getLogger(__name__)


async def extract_cuga_tips_from_data(data: Optional[dict]) -> Tuple[dict, Optional[str]]:
    """
    Extract and store CUGA tips from trajectory data.
    Compatible with the existing API endpoint interface.

    Args:
        data: Dictionary containing trajectory data

    Returns:
        Tuple of (tips_by_agent, trajectory_id)
    """
    if data is None:
        return {"message": "No trajectory data provided"}, None

    try:
        # Check if data is raw trajectory or already IR, generate IR if needed
        if "steps" in data and "steps_analyzed" not in data:
            # This is raw trajectory data, need to generate IR first
            logger.info("Detected raw trajectory data. Generating intermediate representation...")
            try:
                ir_data = generate_trajectory_ir(data, analyze_evaluations=True)
                logger.info(f"Successfully generated IR with {ir_data['total_steps']} steps")
            except Exception as e:
                logger.error(f"Failed to generate IR from raw trajectory: {e}")
                return {"error": f"IR generation failed: {str(e)}"}, None
        elif "steps_analyzed" in data:
            # Already in IR format
            logger.info("Detected existing IR format, using as-is")
            ir_data = data
        else:
            # Unknown format
            logger.warning("Data format unclear, attempting to use as-is")
            ir_data = data

        # Convert to text
        if "trajectory_text" in ir_data:
            # Use the processed viewer output text
            trajectory_text = ir_data["trajectory_text"]
            trajectory_id = ir_data.get("trajectory_id", f"api_{uuid.uuid4().hex[:8]}")
        else:
            # Fall back to raw JSON processing (less effective)
            trajectory_text = json.dumps(ir_data, indent=2)
            trajectory_id = ir_data.get("trajectory_id", f"api_{uuid.uuid4().hex[:8]}")

        # Extract task_intent from IR data
        task_intent = ir_data.get("task_intent", "Unknown task")
        logger.info(f"Processing trajectory data via API: {trajectory_id}, task_intent: {task_intent}")

        # Initialize extractor with error handling
        logger.info("Initializing TipsExtractor...")
        extractor = TipsExtractor()

        if not extractor.llm:
            return {"error": "LLM not available for tips extraction"}, trajectory_id

        # Extract tips using async processing with comprehensive error handling
        logger.info("Starting LLM-based tips extraction (this may take several minutes)...")

        try:
            tips_by_agent = await extractor.extract_tips_from_trajectory(
                trajectory_text, trajectory_id, task_intent=task_intent, focus_on_failures=True
            )
            # Check if result is an error response (has "error" key) vs successful tips (has agent names as keys)
            if isinstance(tips_by_agent, dict) and "error" in tips_by_agent and len(tips_by_agent) == 1:
                # This is an error response
                pass
            else:
                logger.info("LLM processing completed successfully!")
            return tips_by_agent, trajectory_id
        except TimeoutError as e:
            logger.error(f"LLM timeout error: {e}")
            return {
                "error": "LLM request timed out. Please try again with a shorter trajectory."
            }, trajectory_id
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {"error": "Failed to parse LLM response. The response may be malformed."}, trajectory_id
        except ValueError as e:
            logger.error(f"Value error: {e}")
            return {"error": f"Invalid data format: {str(e)}"}, trajectory_id
        except Exception as e:
            logger.error(f"Unexpected error during tips extraction: {e}")
            return {"error": f"Tips extraction failed: {str(e)}"}, trajectory_id

    except Exception as e:
        logger.error(f"Failed to process trajectory: {e}")
        return {"error": f"Failed to process trajectory: {str(e)}"}, None


async def store_cuga_tips(tips_by_agent: dict, trajectory_id: str, user_id: str | None = None) -> int:
    from cuga.backend.memory.agentic_memory.utils.utils import store_facts

    # Store tips in memory
    total_tips = 0
    for agent, tips in tips_by_agent.items():
        for tip in tips:
            tip_data = {
                "intent": tip.intent,
                "task_status": tip.task_status,
                "failure_reason": tip.failure_reason,
                "tip": tip.tip_content,
            }

            # Store in memory using the existing store_facts function
            store_facts(
                user_id=user_id,
                message=json.dumps(tip_data),
                metadata_input={
                    "type": "tips",
                    "tip_id": tip.tip_id,
                    "agent": agent,
                    "specific_checks": tip.specific_checks,
                    "intended_use": tip.intended_use,
                    "priority": tip.priority,
                    "trajectory_id": trajectory_id,
                    "tip_type": tip.tip_type,
                    "rationale": tip.rationale,
                    "application": tip.application,
                    "task_category": tip.task_category,
                },
            )
            total_tips += 1
    return total_tips

from typing import List, Literal, Union
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, field_validator, model_validator


class PlanControllerOutput(BaseModel):
    thoughts: List[str] = Field(..., description="Your thoughts")
    subtasks_progress: List[Literal['completed', 'not-started', 'in-progress']] = Field(
        ..., description="Subtasks progress"
    )
    next_subtask: str = Field(
        default="", description="next subtask description (empty if conclude_task is true)"
    )
    next_subtask_type: Union[Literal['api', 'web'], None] = Field(
        default=None, description="next subtask type (null if conclude_task is true)"
    )
    next_subtask_app: str = Field(default="", description="next subtask app (empty if conclude_task is true)")
    conclude_task: bool = Field(..., description="Should the original task be concluded?")
    conclude_final_answer: str = Field(..., description="Final answer in case final task is concluded")

    @field_validator('next_subtask_type', mode='before')
    @classmethod
    def convert_empty_to_none(cls, v):
        if v == "" or v is None:
            return None
        return v

    @model_validator(mode='after')
    def validate_api_task_has_app(self):
        if self.next_subtask_type == 'api' and not self.next_subtask_app:
            raise ValueError(
                "When next_subtask_type is 'api', next_subtask_app must be specified (non-empty string). "
                f"Got next_subtask_type='api' with next_subtask_app='{self.next_subtask_app}'"
            )

        if self.next_subtask_type == 'api' and not self.next_subtask and not self.conclude_task:
            raise ValueError(
                "When next_subtask_type is 'api' and conclude_task is false, next_subtask must be specified (non-empty string). "
                f"Got next_subtask_type='api' with next_subtask='{self.next_subtask}' and conclude_task='{self.conclude_task}'"
            )

        return self


parser = PydanticOutputParser(pydantic_object=PlanControllerOutput)

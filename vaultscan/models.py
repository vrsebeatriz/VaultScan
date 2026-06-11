from enum import Enum
from pydantic import BaseModel, Field, model_validator

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

from typing import List

class Occurrence(BaseModel):
    file_path: str
    line_number: int
    snippet: str = ""
    source: str = "working_tree"

class Finding(BaseModel):
    rule_id: str
    severity: Severity = Severity.MEDIUM
    occurrences: List[Occurrence] = Field(default_factory=list)
    
    # matched_value is the internal real secret, never exposed in JSON serialization
    matched_value: str = Field(exclude=True)
    # masked_value is automatically computed
    masked_value: str = ""

    @model_validator(mode='after')
    def compute_masked_value(self) -> 'Finding':
        if not self.masked_value and self.matched_value:
            val = self.matched_value
            if len(val) <= 8:
                self.masked_value = "*" * len(val)
            else:
                self.masked_value = f"{val[:4]}****{val[-4:]}"
        return self

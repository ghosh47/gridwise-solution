from typing import List
from app.schemas import DirectiveInterpretation

def validate_and_sanitize_directives(raw_data: List[dict]) -> List[DirectiveInterpretation]:
    sanitized = []
    for d in raw_data:
        interp = DirectiveInterpretation(**d)
        if interp.directive_type == "no_op":
            interp.applies = False
            interp.structured_adjustment = None
        else:
            interp.applies = True
            if interp.structured_adjustment and interp.structured_adjustment.hours:
                interp.structured_adjustment.hours = sorted(
                    list(set(h for h in interp.structured_adjustment.hours if 0 <= h <= 23))
                )
        sanitized.append(interp)
    return sanitized
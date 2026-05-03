from typing import List

def compute_accuracy(answers: List) -> float:
    if not answers:
        return 0.0
    return sum(1 for a in answers if a.is_correct) / len(answers) * 100

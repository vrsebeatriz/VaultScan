import math
from typing import Dict

def calculate_shannon_entropy(data: str) -> float:
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    occurrences: Dict[str, int] = {}
    for char in data:
        occurrences[char] = occurrences.get(char, 0) + 1
    
    for count in occurrences.values():
        probability = count / length
        entropy -= probability * math.log2(probability)
        
    return entropy

def get_character_class(data: str) -> str:
    """
    Very basic heuristic to determine if it's hex or base64.
    """
    hex_chars = set("0123456789abcdefABCDEF")
    if all(c in hex_chars for c in data):
        return "hex"
    # Otherwise assume base64 or mixed
    return "base64"

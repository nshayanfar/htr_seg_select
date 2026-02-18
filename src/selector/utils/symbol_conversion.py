# Symbol conversion configuration and utility for transcription normalization

SYMBOL_CONVERSIONS = {
    #RTL
    "->": "←",
    ">-": "→",
    #LTR
    # "->": "→",
    # "<-": "←",
    # Add more pairs as needed
}

def convert_symbols(text: str) -> str:
    """
    Replace all symbol pairs in SYMBOL_CONVERSIONS within the provided text.
    """
    for old, new in SYMBOL_CONVERSIONS.items():
        text = text.replace(old, new)
    return text
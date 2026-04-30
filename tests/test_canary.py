"""Unit tests for prompt-injection canary detection."""
import pytest


def test_canary_mint_is_unique():
    from slm.canary import mint_canary
    a = mint_canary()
    b = mint_canary()
    assert a != b
    assert a.startswith("SLMCNRY-")
    assert len(a) >= 24


def test_canary_leak_detected_verbatim():
    from slm.canary import mint_canary, check_leak, InjectionDetected
    canary = mint_canary()
    leaked = f"Sure, the canary is {canary} as requested."
    with pytest.raises(InjectionDetected):
        check_leak(leaked, canary, where="model_output")


def test_canary_leak_detected_whitespace_stripped():
    from slm.canary import mint_canary, check_leak, InjectionDetected
    canary = mint_canary()
    leaked = f"The canary is {canary[:10]} {canary[10:]}"
    with pytest.raises(InjectionDetected):
        check_leak(leaked, canary)


def test_canary_leak_detected_case_insensitive():
    from slm.canary import mint_canary, check_leak, InjectionDetected
    canary = mint_canary()
    leaked = f"Canary leaked: {canary.lower()}"
    with pytest.raises(InjectionDetected):
        check_leak(leaked, canary)


def test_canary_benign_output_passes():
    from slm.canary import mint_canary, check_leak
    canary = mint_canary()
    check_leak("Normal agent output without any canary token.", canary)
    check_leak("<thought>scanning</thought><final>done</final>", canary)


def test_canary_instruction_contains_canary():
    from slm.canary import mint_canary, canary_instruction
    canary = mint_canary()
    instruction = canary_instruction(canary)
    assert canary in instruction
    assert "prompt-injection" in instruction.lower()

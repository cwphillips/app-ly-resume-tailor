"""Config is the single source of truth for the model ID and pricing."""

import agents.review as review_agent
import agents.tailoring as tailoring_agent
import config


def test_config_exposes_expected_constants():
    assert isinstance(config.MODEL_ID, str) and config.MODEL_ID
    assert isinstance(config.MODEL_DISPLAY_NAME, str) and config.MODEL_DISPLAY_NAME
    assert config.INPUT_PRICE_PER_M > 0
    assert config.OUTPUT_PRICE_PER_M > 0


def test_both_agents_use_the_config_model_id():
    # Neither agent redefines the model — they reference config, so changing
    # config.MODEL_ID updates both.
    assert tailoring_agent.MODEL_ID is config.MODEL_ID
    assert review_agent.MODEL_ID is config.MODEL_ID

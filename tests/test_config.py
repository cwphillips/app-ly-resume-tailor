"""Config is the single source of truth for the model ID and pricing."""

import agents.review as review_agent
import agents.tailoring as tailoring_agent
import config


def test_config_exposes_expected_constants():
    assert isinstance(config.MODEL_ID, str) and config.MODEL_ID
    assert isinstance(config.MODEL_DISPLAY_NAME, str) and config.MODEL_DISPLAY_NAME
    assert config.INPUT_PRICE_PER_M > 0
    assert config.OUTPUT_PRICE_PER_M > 0


def test_max_api_retries_is_a_non_negative_int():
    assert isinstance(config.MAX_API_RETRIES, int)
    assert config.MAX_API_RETRIES >= 0


def test_both_agents_use_the_config_model_id():
    # Neither agent redefines the model — they reference config, so changing
    # config.MODEL_ID updates both.
    assert tailoring_agent.MODEL_ID is config.MODEL_ID
    assert review_agent.MODEL_ID is config.MODEL_ID


def test_both_agents_import_the_shared_retry_count():
    # Both agents wire the SDK client to config.MAX_API_RETRIES.
    assert tailoring_agent.MAX_API_RETRIES is config.MAX_API_RETRIES
    assert review_agent.MAX_API_RETRIES is config.MAX_API_RETRIES

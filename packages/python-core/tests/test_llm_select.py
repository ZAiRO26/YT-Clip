from unittest.mock import AsyncMock, patch

import pytest
from clipforge_core.services.llm_client import llm_client
from clipforge_core.workers.select import _build_selection_prompt


def test_build_selection_prompt():
    transcript = {
        "language": "en",
        "duration_sec": 120.0,
        "segments": [
            {"start": 0.0, "end": 10.0, "text": "Welcome to the show."},
            {"start": 10.0, "end": 35.0, "text": "Here is the key breakthrough in AI technology today."},
        ],
    }
    scenes = [{"scene_id": 1, "start_sec": 0.0, "end_sec": 20.0}]
    campaign_brief = {"tone": "authoritative", "required_mentions": ["ClipForge"]}

    prompt = _build_selection_prompt(
        transcript=transcript,
        scenes=scenes,
        campaign_brief=campaign_brief,
        editorial_template="explainer",
        rights_basis="owned",
        clip_count=3,
        min_length_sec=15,
        max_length_sec=60,
    )

    assert "SOURCE VIDEO INFORMATION" in prompt
    assert "owned" in prompt
    assert "explainer" in prompt
    assert "ClipForge" in prompt
    assert "TRANSCRIPT WITH TIMESTAMPS" in prompt


@pytest.mark.asyncio
async def test_llm_client_mock_json_completion():
    mock_response = {
        "clips": [
            {
                "start_sec": 10.0,
                "end_sec": 35.0,
                "title": "AI Breakthrough",
                "hook_type": "bold_statement",
                "hook_text": "This changes everything in AI.",
                "key_takeaway": "Autonomous tools are accelerating.",
                "virality_score": 0.88,
                "reasoning": "High impact insight",
                "suggested_callouts": ["Key Fact 1"],
            }
        ]
    }

    with patch.object(llm_client, "complete_json", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = mock_response
        result = await llm_client.complete_json("prompt", "system")
        assert "clips" in result
        assert len(result["clips"]) == 1
        assert result["clips"][0]["title"] == "AI Breakthrough"

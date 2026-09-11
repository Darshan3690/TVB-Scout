from agent.llm import EvidenceExtractor


def test_extractor_does_not_call_a_service_without_explicit_configuration():
    extractor = EvidenceExtractor(api_key="", model="")
    assert extractor.enabled is False
    assert extractor.extract("Example", "Jane Doe is founder") == {}


def test_output_text_supports_response_api_message_shape():
    payload = {
        "output": [
            {"content": [{"type": "output_text", "text": '{"industry":"AI"}'}]},
        ]
    }
    assert EvidenceExtractor._output_text(payload) == '{"industry":"AI"}'

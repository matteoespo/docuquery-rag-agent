from unittest.mock import patch, MagicMock
from backend.ai.nodes.generation import grade_answer

def test_grade_answer_retries_limit():
    """Test that it returns 'useful' if retries is >= 2 regardless of LLM output."""
    state = {"query": "What is the meaning of life?", "answer": "42", "retries": 2}
    result = grade_answer(state)
    assert result == "useful"

@patch("backend.ai.nodes.generation.ChatPromptTemplate.from_messages")
def test_grade_answer_useful(mock_from_messages):
    """Test that it returns 'useful' if LLM grades it as yes."""
    mock_chain = MagicMock()
    mock_chain.__or__.return_value = mock_chain
    mock_chain.invoke.return_value = "yes"
    mock_from_messages.return_value = mock_chain
    
    state = {"query": "What is the speed of light?", "answer": "299,792,458 m/s", "retries": 0}
    result = grade_answer(state)
    
    assert result == "useful"

@patch("backend.ai.nodes.generation.ChatPromptTemplate.from_messages")
def test_grade_answer_not_useful(mock_from_messages):
    """Test that it returns 'not_useful' if LLM grades it as no."""
    mock_chain = MagicMock()
    mock_chain.__or__.return_value = mock_chain
    mock_chain.invoke.return_value = "no"
    mock_from_messages.return_value = mock_chain
    
    state = {"query": "What is the speed of light?", "answer": "I don't know.", "retries": 1}
    result = grade_answer(state)
    
    assert result == "not_useful"

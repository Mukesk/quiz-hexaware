import json
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.config import settings

SYSTEM_PROMPT = """You are a strict question quality reviewer for a technical learning platform.
A student has flagged a question as incorrect or problematic.

Your job:
1. Use verify_claim to determine if the report is valid (confidence >= 0.75 = valid).
2. If valid AND the issue is a wrong correct_answer or minor wording fix:
   → Use edit_question_fields to fix in place (action: 'edit').
3. If valid AND the issue is a fundamentally broken question:
   → Use generate_replacement_question to create a full replacement (action: 'replace').
4. If invalid (confidence < 0.75 or report is baseless):
   → Do nothing. Return action: 'reject' with your reasoning.

CRITICAL RULES:
- Never change topic, subtopic, difficulty, or type of the original question.
- Never fabricate facts. If unsure, set confidence < 0.75 and reject.
- Always return a final JSON summary:
  {{"action": "edit|replace|reject", "confidence": 0.0-1.0, "verdict": "...", "is_valid": true|false, "edited_fields": {{...}} or null}}
"""


@tool
def verify_claim(question_json: str, report_reason: str, student_note: str) -> str:
    """Analyse whether the student's report about a question is factually valid.

    Args:
        question_json: The full question as a JSON string
        report_reason: The category of the report (wrong_answer, wrong_question, etc.)
        student_note: Optional free text explanation from the student

    Returns:
        JSON string: {is_valid: bool, confidence: float, reasoning: str}
    """
    # The LLM uses its own knowledge to reason about the claim
    return json.dumps({
        "instruction": (
            f"Verify if this student report is valid.\n"
            f"Question: {question_json}\n"
            f"Reason: {report_reason}\n"
            f"Student note: {student_note}\n"
            f"Return JSON: {{is_valid, confidence (0-1), reasoning}}"
        )
    })


@tool
def generate_replacement_question(question_json: str, issue: str) -> str:
    """Generate a corrected replacement for a flawed question.

    Args:
        question_json: Original question as JSON string
        issue: Description of what is wrong and needs fixing

    Returns:
        JSON string with corrected question matching QuestionCreate schema.
        Must preserve: topic, subtopic, difficulty, type, blooms_level.
    """
    return json.dumps({
        "instruction": (
            f"Generate a corrected replacement question.\n"
            f"Original: {question_json}\n"
            f"Issue to fix: {issue}\n"
            f"Return JSON: {{question_text, options: [{{id, text, is_correct, explanation}}], "
            f"correct_answer, explanation}}\n"
            f"Preserve topic/subtopic/difficulty/type exactly."
        )
    })


@tool
def edit_question_fields(question_json: str, fields_to_fix: str) -> str:
    """Fix specific fields of a question without full replacement.

    Args:
        question_json: Original question as JSON string
        fields_to_fix: Comma-separated fields to fix (e.g. 'correct_answer,explanation')

    Returns:
        JSON string with only the corrected fields, e.g. {correct_answer, explanation, question_text}
    """
    return json.dumps({
        "instruction": (
            f"Fix only these fields: {fields_to_fix}.\n"
            f"Original question: {question_json}\n"
            f"Return JSON with only the corrected fields."
        )
    })


def build_review_agent() -> AgentExecutor:
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.1,  # low temperature for deterministic decisions
        api_key=settings.OPENAI_API_KEY,
    )
    tools = [verify_claim, generate_replacement_question, edit_question_fields]
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=6,
        handle_parsing_errors=True,
    )

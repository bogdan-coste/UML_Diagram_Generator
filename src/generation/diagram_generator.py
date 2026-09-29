from src.llm.llm_client import LLMClient
from src.prompts.prompt_templates import PromptTemplates


class DiagramGeneratorLLM:
    """Ask the LLM for the diagram source that matches a description."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self._llm.system_prompt = PromptTemplates.DIAGRAM_GENERATION_SYSTEM_PROMPT

    def generate(
        self,
        description: str,
        diagram_type: str = "class",
        output_format: str = "plantuml",
        context: str = "",
    ) -> str | None:

        user_msg = PromptTemplates.DIAGRAM_GENERATION_TEMPLATE.substitute(
            description=description.strip(),
            diagram_type=diagram_type,
            output_format=output_format,
            notation_rules=self._notation_rules(output_format),
            context=context.strip() or "(none)",
        )

        response = self._llm.ask_llm(user_msg)
        if response is None:
            return None

        return self._strip_code_fences(response)

    @staticmethod
    def _notation_rules(output_format: str) -> str:
        """
            Notation-specific syntax guidance for the requested format.
        """
        key = output_format.lower().strip()
        return PromptTemplates.NOTATION_RULES.get(
            key, PromptTemplates.NOTATION_RULES["default"]
        )

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Drop a wrapping ``` fence, which models add despite being told not to."""
        cleaned = text.strip()
        if not cleaned.startswith("```"):
            return cleaned

        lines = cleaned.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines).strip()

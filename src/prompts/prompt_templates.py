from string import Template
from textwrap import dedent
from typing import ClassVar


class PromptTemplates:
    """
        Prompt text used by the generation layer.
    """

    DIAGRAM_GENERATION_SYSTEM_PROMPT: ClassVar[str] = dedent(
        """\
        You are an expert software architect who draws UML and software
        architecture diagrams.

        You are given a description of a system and must answer with diagram
        source code in the notation you are asked for.

        Rules:
        - Reply with the diagram source only. No prose, no explanation, no
          markdown code fences, nothing before or after the diagram.
        - Use exactly the requested notation and diagram type. Never mix in
          syntax from another notation.
        - Model only what the description supports. Do not invent classes,
          interfaces, services, components or relationships that are not stated
          or clearly implied.
        - Reuse the exact entity names given in the description.
        - Give every relationship a direction and a short label describing the
          interaction.
        - Keep every identifier valid for the target notation: no spaces or
          punctuation that would break its syntax.
        - If the description is too vague to produce a diagram, reply with a
          single sentence stating what is missing instead of guessing.
        """
    )

    DIAGRAM_GENERATION_TEMPLATE: ClassVar[Template] = Template(
        dedent(
            """\
            Produce a $diagram_type diagram in $output_format syntax for the system
            described below.

            Description:
            $description

            Notation rules for $output_format:
            $notation_rules

            Additional context:
            $context

            Reply with the diagram source only.
            """
        )
    )

    NOTATION_RULES: ClassVar[dict[str, str]] = {
        "plantuml": dedent(
            """\
            - Wrap the diagram in @startuml / @enduml.
            - Declare types as `class Name { ... }` and `interface Name { ... }`.
            - Put members inside the braces, one per line, e.g. `+placeOrder(cartId) : Order`.
            - Relationships: `<|--` inheritance, `<|..` implementation, `*--` composition,
              `..>` dependency, `-->` association.
            - Label an arrow after a colon, e.g. `OrderService ..> PaymentGateway : uses`.
            """
        ),
        "mermaid": dedent(
            """\
            - The first line must be `classDiagram`.
            - Declare types as `class Name { ... }`; mark interfaces with `<<interface>>`.
            - Relationships: `<|--` inheritance, `<|..` realization, `*--` composition,
              `-->` association, `..>` dependency.
            - Use plain identifiers only: replace dots and spaces with underscores.
            """
        ),
        "structurizr": dedent(
            """\
            - Start with `workspace "Name" "Description" {` and use the C4 model:
              `softwareSystem` for systems, `container` for containers, `component` for components.
            - Nest the elements in a `model { ... }` block and declare relationships as
              `source -> destination "description"`.
            - Include a `views { ... }` block with at least one view that does `include *`.
            """
        ),
        "graphviz": dedent(
            """\
            - Start with `digraph Name {` and close with `}`.
            - Declare nodes as `"Name" [label="..."];` and edges as
              `"From" -> "To" [label="..."];`.
            - Quote every identifier.
            """
        ),
        "default": "- Follow the target notation's standard syntax exactly.\n",
    }

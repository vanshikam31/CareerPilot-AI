"""Thin adapter around the Gemini SDK. The agent loop only knows start / generate /
add_tool_results, so tests can swap in a fake model."""
from app.services.gemini_retry import call_with_retry
from app.agents.tools import TOOL_SPECS
from app.agents.types import ToolCall, Turn
from app.core.config import settings


def _schema(types, spec: dict):
    kind = spec["type"]
    kwargs = {"type": getattr(types.Type, kind.upper())}
    if spec.get("description"):
        kwargs["description"] = spec["description"]
    if spec.get("enum"):
        kwargs["enum"] = spec["enum"]
    if kind == "object":
        kwargs["properties"] = {k: _schema(types, v) for k, v in spec.get("properties", {}).items()}
        kwargs["required"] = spec.get("required", [])
    return types.Schema(**kwargs)


class GeminiLLM:
    def __init__(self) -> None:
        from google import genai
        from google.genai import types

        self.types = types
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=30_000),  # milliseconds
        )
        declarations = [
            types.FunctionDeclaration(
                name=spec["name"],
                description=spec["description"],
                parameters=_schema(types, spec["parameters"]) if spec["parameters"].get("properties") else None,
            )
            for spec in TOOL_SPECS
        ]
        self.tool = types.Tool(function_declarations=declarations)

    def start(self, history: list[dict], message: str) -> list:
        t = self.types
        contents = [
            t.Content(role="user" if m["role"] == "user" else "model", parts=[t.Part(text=m["content"])])
            for m in history
        ]
        contents.append(t.Content(role="user", parts=[t.Part(text=message)]))
        return contents

    def generate(self, contents: list, system: str, allow_tools: bool = True) -> Turn:
        t = self.types
        config = t.GenerateContentConfig(
            system_instruction=system,
            temperature=0.3,
            tools=[self.tool] if allow_tools else None,
        )
        response = self.client.models.generate_content(
            model=settings.gemini_model, contents=contents, config=config
        )
        response = call_with_retry(
            lambda: self.client.models.generate_content(
                model=settings.gemini_model, contents=contents, config=config
            )
        )
        calls = [ToolCall(name=fc.name, args=dict(fc.args or {})) for fc in (response.function_calls or [])]
        raw = response.candidates[0].content if response.candidates else None
        return Turn(text="" if calls else (response.text or ""), calls=calls, raw=raw)

    def add_tool_results(self, contents: list, turn: Turn, results: list) -> None:
        t = self.types
        contents.append(turn.raw)  # the model's own message, exactly as received
        contents.append(
            t.Content(
                role="user",
                parts=[t.Part.from_function_response(name=c.name, response={"result": r}) for c, r in results],
            )
        )
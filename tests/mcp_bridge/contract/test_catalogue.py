"""Tests de contrat — catalogue d'outils.

Exigences : MCP-02 (catalogue), SAF-01 (aucun outil d'actionneur), SAF-05 (sévérité 4).
"""

from __future__ import annotations

import jsonschema
import pytest

from bridge_mcp import contract

pytestmark = pytest.mark.contract


async def test_catalogue_has_exactly_the_specified_tools(session):
    """MCP-02 : 22 outils, noms strictement conformes à la spécification §4.2-4.3."""
    tools = await session.list_tools()
    names = {tool.name for tool in tools.tools}
    assert names == set(contract.EXPECTED_TOOLS)
    assert len(tools.tools) == 22


async def test_each_tool_schema_is_valid_json_schema(session):
    """MCP-02 : chaque `inputSchema` valide JSON Schema 2020-12."""
    tools = await session.list_tools()
    for tool in tools.tools:
        assert tool.inputSchema.get("type") == "object", f"{tool.name}: racine non objet"
        jsonschema.Draft202012Validator.check_schema(tool.inputSchema)


async def test_read_only_tools_are_annotated_read_only(session):
    """SAF-01 : les outils de contexte sont annotés lecture seule."""
    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
    for name in contract.READ_ONLY_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None, f"{name}: annotations absentes"
        assert annotations.readOnlyHint is True, f"{name}: doit être readOnlyHint"


async def test_mutation_tools_are_annotated_destructive(session):
    """SAF-01 : toute mutation est signalée comme destructive à l'appelant."""
    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
    for name in contract.MUTATION_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None, f"{name}: annotations absentes"
        assert annotations.destructiveHint is True, f"{name}: doit être destructiveHint"


async def test_no_tool_targets_an_actuator_topic(session):
    """SAF-01 : aucun outil ne prend un topic d'actionneur en paramètre."""
    tools = await session.list_tools()
    forbidden = {topic.lower() for topic in contract.ACTUATOR_TOPICS}
    for tool in tools.tools:
        schema = tool.inputSchema
        properties = schema.get("properties", {})
        for prop in properties:
            assert prop.lower() not in {"topic", "publish_topic", "topic_name"}, (
                f"{tool.name}: paramètre de topic interdit"
            )
        rendered = f"{tool.description or ''} {schema}".lower()
        for topic in forbidden:
            assert topic not in rendered, f"{tool.name}: référence au topic d'actionneur {topic}"


async def test_priority_tools_are_present(session):
    """MCP-15 : `Stop` et l'escalade existent et sont identifiables."""
    names = {tool.name for tool in (await session.list_tools()).tools}
    assert set(contract.PRIORITY_TOOLS) <= names
    assert set(contract.SEVERITY_4_TOOLS) <= names

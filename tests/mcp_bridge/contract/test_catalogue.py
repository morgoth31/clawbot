"""Tests de contrat — catalogue d'outils.

Exigences : MCP-02 (catalogue), SAF-01 (aucun outil d'actionneur), SAF-05 (sévérité 4).
"""

from __future__ import annotations

import jsonschema
import pytest

from bridge_mcp import contract

pytestmark = pytest.mark.contract


def test_catalogue_has_exactly_the_specified_tools(client):
    """MCP-02 : 25 outils, noms strictement conformes à la spécification §4.2-4.3 et §6."""
    tools = client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert names == set(contract.EXPECTED_TOOLS)
    assert len(tools.tools) == 25


def test_each_tool_schema_is_valid_json_schema(client):
    """MCP-02 : chaque `inputSchema` valide JSON Schema 2020-12."""
    tools = client.list_tools()
    for tool in tools.tools:
        assert tool.input_schema.get("type") == "object", f"{tool.name}: racine non objet"
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)


def test_read_only_tools_are_annotated_read_only(client):
    """SAF-01 : les outils de contexte sont annotés lecture seule."""
    tools = {tool.name: tool for tool in (client.list_tools()).tools}
    for name in contract.READ_ONLY_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None, f"{name}: annotations absentes"
        assert annotations.read_only_hint is True, f"{name}: doit être readOnlyHint"


def test_mutation_tools_are_annotated_destructive(client):
    """SAF-01 : toute mutation est signalée comme destructive à l'appelant."""
    tools = {tool.name: tool for tool in (client.list_tools()).tools}
    for name in contract.MUTATION_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None, f"{name}: annotations absentes"
        assert annotations.destructive_hint is True, f"{name}: doit être destructiveHint"


def test_no_tool_can_write_an_actuator_topic(client):
    """SAF-01 : aucun outil de mutation ne prend un topic en paramètre, et aucun outil
    ne cite un topic d'actionneur dans son contrat.

    Un outil de lecture peut nommer un topic à observer (`topic_stats`) : l'invariant porte
    sur l'écriture, pas sur la désignation.
    """
    tools = {tool.name: tool for tool in client.list_tools().tools}
    forbidden = {topic.lower() for topic in contract.ACTUATOR_TOPICS}

    for name in contract.MUTATION_TOOLS:
        properties = tools[name].input_schema.get("properties", {})
        for prop in properties:
            assert prop.lower() not in {"topic", "publish_topic", "topic_name"}, (
                f"{name}: un outil de mutation ne prend pas de topic en paramètre"
            )

    for name, tool in tools.items():
        rendered = f"{tool.description or ''} {tool.input_schema}".lower()
        for topic in forbidden:
            assert topic not in rendered, f"{name}: référence au topic d'actionneur {topic}"


def test_priority_tools_are_present(client):
    """MCP-15 : `Stop` et l'escalade existent et sont identifiables."""
    names = {tool.name for tool in (client.list_tools()).tools}
    assert set(contract.PRIORITY_TOOLS) <= names
    assert set(contract.SEVERITY_4_TOOLS) <= names

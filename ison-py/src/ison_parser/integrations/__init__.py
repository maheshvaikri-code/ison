"""
ISON Framework Integrations

LLM Framework Integrations:
- langchain: LangChain OutputParser for ISON and ISONL responses
- llamaindex: LlamaIndex Reader for ISON and ISONL documents
- autogen: Microsoft AutoGen memory and context management

LLM Provider Integrations:
- openai: OpenAI Function Calling with ISON
- anthropic: Anthropic Tool Use with ISON

MCP (Model Context Protocol) Integrations:
- mcp_server: MCP Server exposing ISON and ISONL tools
- mcp_client: MCP Client consuming ISON and ISONL data

ISONL Streaming Support:
All integrations support ISONL (ISON Lines) streaming format for:
- Fine-tuning datasets
- Event streams and logs
- Large dataset processing with constant memory

ISONantic Support:
All integrations support optional ISONantic models for typed validation.
Install isonantic for typed model features: pip install isonantic
"""

# Lazy load integrations to avoid import errors if dependencies aren't installed
def __getattr__(name):
    """Lazy load optional integrations."""
    if name == 'ISONOutputParser':
        from .langchain_integration import ISONOutputParser
        return ISONOutputParser
    elif name == 'ISONanticOutputParser':
        from .langchain_integration import ISONanticOutputParser
        return ISONanticOutputParser
    elif name == 'ISONListOutputParser':
        from .langchain_integration import ISONListOutputParser
        return ISONListOutputParser
    elif name == 'ISONDictOutputParser':
        from .langchain_integration import ISONDictOutputParser
        return ISONDictOutputParser
    elif name == 'ISONLOutputParser':
        from .langchain_integration import ISONLOutputParser
        return ISONLOutputParser
    elif name == 'ISONLStreamingParser':
        from .langchain_integration import ISONLStreamingParser
        return ISONLStreamingParser
    elif name == 'ISONReader':
        from .llamaindex_integration import ISONReader
        return ISONReader
    elif name == 'ISONNodeParser':
        from .llamaindex_integration import ISONNodeParser
        return ISONNodeParser
    elif name == 'ISONRAGHelper':
        from .llamaindex_integration import ISONRAGHelper
        return ISONRAGHelper
    elif name == 'ISONLReader':
        from .llamaindex_integration import ISONLReader
        return ISONLReader
    elif name == 'ISONLNodeParser':
        from .llamaindex_integration import ISONLNodeParser
        return ISONLNodeParser
    elif name == 'OpenAIISONTools':
        from .openai_integration import OpenAIISONTools
        return OpenAIISONTools
    elif name == 'OpenAIISONChat':
        from .openai_integration import OpenAIISONChat
        return OpenAIISONChat
    elif name == 'AnthropicISONTools':
        from .anthropic_integration import AnthropicISONTools
        return AnthropicISONTools
    elif name == 'AnthropicISONChat':
        from .anthropic_integration import AnthropicISONChat
        return AnthropicISONChat
    elif name == 'ISONMCPServer':
        from .mcp_server import ISONMCPServer
        return ISONMCPServer
    elif name == 'ISONMCPClient':
        from .mcp_client import ISONMCPClient
        return ISONMCPClient
    elif name == 'ISONMCPClientSync':
        from .mcp_client import ISONMCPClientSync
        return ISONMCPClientSync
    elif name == 'ISONMemory':
        from .autogen_integration import ISONMemory
        return ISONMemory
    elif name == 'ISONContextManager':
        from .autogen_integration import ISONContextManager
        return ISONContextManager
    elif name == 'ISONAgentMixin':
        from .autogen_integration import ISONAgentMixin
        return ISONAgentMixin
    elif name == 'ison_context_manager':
        from .autogen_integration import ison_context_manager
        return ison_context_manager
    elif name == 'messages_to_ison':
        from .autogen_integration import messages_to_ison
        return messages_to_ison
    elif name == 'ison_to_messages':
        from .autogen_integration import ison_to_messages
        return ison_to_messages
    elif name == 'create_ison_agent':
        from .autogen_integration import create_ison_agent
        return create_ison_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # LangChain Integrations
    'ISONOutputParser',
    'ISONanticOutputParser',
    'ISONListOutputParser',
    'ISONDictOutputParser',
    'ISONLOutputParser',
    'ISONLStreamingParser',
    # LlamaIndex Integrations
    'ISONReader',
    'ISONNodeParser',
    'ISONRAGHelper',
    'ISONLReader',
    'ISONLNodeParser',
    # OpenAI Integrations
    'OpenAIISONTools',
    'OpenAIISONChat',
    # Anthropic Integrations
    'AnthropicISONTools',
    'AnthropicISONChat',
    # MCP Integrations
    'ISONMCPServer',
    'ISONMCPClient',
    'ISONMCPClientSync',
    # AutoGen Integrations
    'ISONMemory',
    'ISONContextManager',
    'ISONAgentMixin',
    'ison_context_manager',
    'messages_to_ison',
    'ison_to_messages',
    'create_ison_agent',
]

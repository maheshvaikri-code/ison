"""
AutoGen ISON Integration

Provides ISON-based memory and context management for Microsoft AutoGen agents.
Enables token-efficient conversation storage and retrieval.

Usage:
    from autogen import ConversableAgent
    from ison_parser.integrations import ISONMemory, ison_context_manager

    # Create ISON-based memory
    memory = ISONMemory()

    # Use with AutoGen agent
    agent = ConversableAgent(
        name="assistant",
        system_message="You are a helpful assistant.",
    )

    # Store conversation in ISON format
    memory.add_message("user", "Hello!")
    memory.add_message("assistant", "Hi! How can I help?")

    # Get ISON context for LLM
    context = memory.to_ison()

    # With context manager for RAG
    with ison_context_manager() as ctx:
        ctx.add_documents(documents)
        ctx.add_messages(messages)
        ison_context = ctx.build()

Requirements:
    pip install pyautogen
    pip install ison-parser isonantic
"""

from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json

# Import ISON parser
import ison_parser
from ison_parser import Document, Block, Serializer, loads, dumps

# Try to import ISONantic for typed models
try:
    from isonantic import TableModel, ObjectModel, Field, parse_ison
    ISONANTIC_AVAILABLE = True
except ImportError:
    ISONANTIC_AVAILABLE = False
    TableModel = None
    ObjectModel = None

# Try to import AutoGen
try:
    from autogen import ConversableAgent, Agent
    AUTOGEN_AVAILABLE = True
except ImportError:
    try:
        from pyautogen import ConversableAgent, Agent
        AUTOGEN_AVAILABLE = True
    except ImportError:
        AUTOGEN_AVAILABLE = False
        ConversableAgent = None
        Agent = None


__all__ = [
    'ISONMemory',
    'ISONContextManager',
    'ISONAgentMixin',
    'ison_context_manager',
    'messages_to_ison',
    'ison_to_messages',
]


@dataclass
class Message:
    """A conversation message."""
    role: str
    content: str
    name: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ISONMemory:
    """
    ISON-based memory storage for AutoGen agents.

    Stores conversation history in token-efficient ISON format.
    Supports message filtering, summarization, and RAG context.

    Example:
        >>> memory = ISONMemory(max_messages=100)
        >>> memory.add_message("user", "What is ISON?")
        >>> memory.add_message("assistant", "ISON is a token-efficient format...")
        >>> print(memory.to_ison())
        table.messages
        role content
        user "What is ISON?"
        assistant "ISON is a token-efficient format..."
    """

    def __init__(
        self,
        max_messages: Optional[int] = None,
        include_timestamps: bool = False,
        include_metadata: bool = False,
    ):
        """
        Initialize ISON memory.

        Args:
            max_messages: Maximum messages to retain (None for unlimited)
            include_timestamps: Include message timestamps
            include_metadata: Include message metadata
        """
        self.messages: List[Message] = []
        self.max_messages = max_messages
        self.include_timestamps = include_timestamps
        self.include_metadata = include_metadata
        self._context_documents: List[Dict[str, Any]] = []

    def add_message(
        self,
        role: str,
        content: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a message to memory.

        Args:
            role: Message role (user, assistant, system, function)
            content: Message content
            name: Optional sender name
            metadata: Optional metadata dict
        """
        msg = Message(
            role=role,
            content=content,
            name=name,
            timestamp=datetime.now().isoformat() if self.include_timestamps else None,
            metadata=metadata if self.include_metadata else None,
        )
        self.messages.append(msg)

        # Trim if exceeding max
        if self.max_messages and len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def add_context(
        self,
        content: str,
        source: Optional[str] = None,
        score: Optional[float] = None,
    ) -> None:
        """
        Add RAG context document.

        Args:
            content: Document content
            source: Source identifier
            score: Relevance score
        """
        self._context_documents.append({
            'content': content,
            'source': source,
            'score': score,
        })

    def clear(self) -> None:
        """Clear all messages and context."""
        self.messages = []
        self._context_documents = []

    def clear_context(self) -> None:
        """Clear only context documents."""
        self._context_documents = []

    def to_ison(self, include_context: bool = True) -> str:
        """
        Convert memory to ISON format.

        Args:
            include_context: Include context documents

        Returns:
            ISON formatted string
        """
        doc = Document()

        # Add context block if present
        if include_context and self._context_documents:
            fields = ['rank', 'score', 'content', 'source']
            rows = []
            for i, ctx in enumerate(self._context_documents):
                rows.append({
                    'rank': i + 1,
                    'score': ctx.get('score', 1.0),
                    'content': ctx.get('content', ''),
                    'source': ctx.get('source', ''),
                })
            context_block = Block(
                kind='table',
                name='context',
                fields=fields,
                rows=rows,
            )
            doc.blocks.append(context_block)

        # Add messages block
        if self.messages:
            fields = ['role', 'content']
            if self.include_timestamps:
                fields.append('timestamp')
            if any(m.name for m in self.messages):
                fields.insert(1, 'name')

            rows = []
            for msg in self.messages:
                row: Dict[str, Any] = {
                    'role': msg.role,
                    'content': msg.content,
                }
                if 'name' in fields:
                    row['name'] = msg.name or ''
                if 'timestamp' in fields:
                    row['timestamp'] = msg.timestamp or ''
                rows.append(row)

            messages_block = Block(
                kind='table',
                name='messages',
                fields=fields,
                rows=rows,
            )
            doc.blocks.append(messages_block)

        return Serializer().dumps(doc)

    def to_dict(self) -> List[Dict[str, str]]:
        """
        Convert to OpenAI-compatible message list.

        Returns:
            List of message dicts with 'role' and 'content'
        """
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in self.messages
        ]

    def from_ison(self, ison_text: str) -> None:
        """
        Load messages from ISON format.

        Args:
            ison_text: ISON formatted string
        """
        doc = loads(ison_text)

        # Load messages
        messages_block = doc.get('messages')
        if messages_block:
            self.messages = []
            for row in messages_block.rows:
                self.add_message(
                    role=row.get('role', 'user'),
                    content=row.get('content', ''),
                    name=row.get('name'),
                )

        # Load context
        context_block = doc.get('context')
        if context_block:
            self._context_documents = []
            for row in context_block.rows:
                self.add_context(
                    content=row.get('content', ''),
                    source=row.get('source'),
                    score=row.get('score'),
                )

    def get_recent(self, n: int) -> 'ISONMemory':
        """
        Get most recent n messages as new memory.

        Args:
            n: Number of messages

        Returns:
            New ISONMemory with recent messages
        """
        new_memory = ISONMemory(
            max_messages=self.max_messages,
            include_timestamps=self.include_timestamps,
            include_metadata=self.include_metadata,
        )
        new_memory.messages = self.messages[-n:]
        new_memory._context_documents = self._context_documents.copy()
        return new_memory

    def filter_by_role(self, roles: List[str]) -> 'ISONMemory':
        """
        Filter messages by role.

        Args:
            roles: List of roles to include

        Returns:
            New ISONMemory with filtered messages
        """
        new_memory = ISONMemory(
            max_messages=self.max_messages,
            include_timestamps=self.include_timestamps,
            include_metadata=self.include_metadata,
        )
        new_memory.messages = [m for m in self.messages if m.role in roles]
        new_memory._context_documents = self._context_documents.copy()
        return new_memory

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"ISONMemory(messages={len(self.messages)}, context={len(self._context_documents)})"


class ISONContextManager:
    """
    Context manager for building ISON context.

    Example:
        >>> with ISONContextManager() as ctx:
        ...     ctx.add_documents(docs)
        ...     ctx.add_messages(history)
        ...     ctx.add_metadata({"query": "..."})
        ...     ison = ctx.build()
    """

    def __init__(self):
        self._documents: List[Dict[str, Any]] = []
        self._messages: List[Dict[str, str]] = []
        self._metadata: Dict[str, Any] = {}
        self._custom_blocks: List[Block] = []

    def add_document(
        self,
        content: str,
        source: Optional[str] = None,
        score: Optional[float] = None,
        **kwargs,
    ) -> 'ISONContextManager':
        """Add a single document."""
        doc = {'content': content, 'source': source, 'score': score}
        doc.update(kwargs)
        self._documents.append(doc)
        return self

    def add_documents(
        self,
        documents: List[Union[str, Dict[str, Any]]],
    ) -> 'ISONContextManager':
        """Add multiple documents."""
        for doc in documents:
            if isinstance(doc, str):
                self.add_document(doc)
            else:
                self.add_document(**doc)
        return self

    def add_message(
        self,
        role: str,
        content: str,
    ) -> 'ISONContextManager':
        """Add a single message."""
        self._messages.append({'role': role, 'content': content})
        return self

    def add_messages(
        self,
        messages: List[Dict[str, str]],
    ) -> 'ISONContextManager':
        """Add multiple messages."""
        self._messages.extend(messages)
        return self

    def add_metadata(
        self,
        metadata: Dict[str, Any],
    ) -> 'ISONContextManager':
        """Add metadata."""
        self._metadata.update(metadata)
        return self

    def add_block(
        self,
        block: Block,
    ) -> 'ISONContextManager':
        """Add custom ISON block."""
        self._custom_blocks.append(block)
        return self

    def build(self) -> str:
        """Build ISON context string."""
        doc = Document()

        # Add metadata as object block
        if self._metadata:
            fields = list(self._metadata.keys())
            rows = [self._metadata]
            meta_block = Block(
                kind='object',
                name='query',
                fields=fields,
                rows=rows,
            )
            doc.blocks.append(meta_block)

        # Add context documents
        if self._documents:
            fields = ['rank', 'score', 'content', 'source']
            rows = []
            for i, d in enumerate(self._documents):
                rows.append({
                    'rank': i + 1,
                    'score': d.get('score', 1.0),
                    'content': d.get('content', ''),
                    'source': d.get('source', ''),
                })
            ctx_block = Block(
                kind='table',
                name='context',
                fields=fields,
                rows=rows,
            )
            doc.blocks.append(ctx_block)

        # Add messages
        if self._messages:
            fields = ['role', 'content']
            msg_block = Block(
                kind='table',
                name='messages',
                fields=fields,
                rows=self._messages,
            )
            doc.blocks.append(msg_block)

        # Add custom blocks
        for block in self._custom_blocks:
            doc.blocks.append(block)

        return Serializer().dumps(doc)

    def __enter__(self) -> 'ISONContextManager':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


def ison_context_manager() -> ISONContextManager:
    """Create a new ISON context manager."""
    return ISONContextManager()


class ISONAgentMixin:
    """
    Mixin for AutoGen agents to use ISON memory.

    Example:
        >>> class MyAgent(ConversableAgent, ISONAgentMixin):
        ...     pass
        >>> agent = MyAgent(name="assistant")
        >>> agent.init_ison_memory()
        >>> # Agent now uses ISON for message storage
    """

    _ison_memory: Optional[ISONMemory] = None

    def init_ison_memory(
        self,
        max_messages: Optional[int] = None,
        include_timestamps: bool = False,
    ) -> None:
        """Initialize ISON memory for this agent."""
        self._ison_memory = ISONMemory(
            max_messages=max_messages,
            include_timestamps=include_timestamps,
        )

    def get_ison_context(self) -> str:
        """Get conversation history as ISON."""
        if self._ison_memory is None:
            return ""
        return self._ison_memory.to_ison()

    def add_to_ison_memory(
        self,
        role: str,
        content: str,
        name: Optional[str] = None,
    ) -> None:
        """Add message to ISON memory."""
        if self._ison_memory is None:
            self.init_ison_memory()
        self._ison_memory.add_message(role, content, name)


# =============================================================================
# Convenience Functions
# =============================================================================

def messages_to_ison(
    messages: List[Dict[str, str]],
    include_system: bool = True,
) -> str:
    """
    Convert OpenAI-format messages to ISON.

    Args:
        messages: List of message dicts with 'role' and 'content'
        include_system: Include system messages

    Returns:
        ISON formatted string

    Example:
        >>> messages = [
        ...     {"role": "system", "content": "You are helpful."},
        ...     {"role": "user", "content": "Hello!"},
        ... ]
        >>> print(messages_to_ison(messages))
        table.messages
        role content
        system "You are helpful."
        user "Hello!"
    """
    memory = ISONMemory()
    for msg in messages:
        role = msg.get('role', 'user')
        if not include_system and role == 'system':
            continue
        memory.add_message(role, msg.get('content', ''))
    return memory.to_ison()


def ison_to_messages(ison_text: str) -> List[Dict[str, str]]:
    """
    Convert ISON to OpenAI-format messages.

    Args:
        ison_text: ISON formatted string

    Returns:
        List of message dicts

    Example:
        >>> ison = '''
        ... table.messages
        ... role content
        ... user "Hello!"
        ... assistant "Hi there!"
        ... '''
        >>> messages = ison_to_messages(ison)
        >>> print(messages[0])
        {'role': 'user', 'content': 'Hello!'}
    """
    memory = ISONMemory()
    memory.from_ison(ison_text)
    return memory.to_dict()


def create_ison_agent(
    name: str,
    system_message: str = "You are a helpful AI assistant.",
    max_memory: Optional[int] = 50,
    **kwargs,
) -> Any:
    """
    Create an AutoGen agent with ISON memory support.

    Args:
        name: Agent name
        system_message: System prompt
        max_memory: Maximum messages in memory
        **kwargs: Additional agent kwargs

    Returns:
        ConversableAgent with ISON memory

    Example:
        >>> agent = create_ison_agent("assistant")
        >>> agent.add_to_ison_memory("user", "Hello!")
        >>> print(agent.get_ison_context())
    """
    if not AUTOGEN_AVAILABLE:
        raise ImportError(
            "AutoGen not found. Install with: pip install pyautogen"
        )

    class ISONAgent(ConversableAgent, ISONAgentMixin):
        pass

    agent = ISONAgent(
        name=name,
        system_message=system_message,
        **kwargs,
    )
    agent.init_ison_memory(max_messages=max_memory)

    return agent

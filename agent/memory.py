import os
from google.genai import types
import hnswlib
import ollama
import agent.constants
import models.constants

# todo: store temporal information

class Memory:
    """A simple memory class using HNSWLib for vector storage and retrieval."""
    def __init__(self) -> None:
        # existing memory index -> load it
        if os.path.exists(agent.constants.memory_index_path):
            self.index = hnswlib.Index(space='cosine', dim=models.constants.embedding_dimension)
            self.index.load_index(agent.constants.memory_index_path)
            # self.index.set_num_threads(agent.constants.memory_threads)
            return

        # create a new index if none exists
        self.index = hnswlib.Index(space='cosine', dim=models.constants.embedding_dimension)
        self.index.init_index(
            max_elements=agent.constants.memory_capacity_step, 
            ef_construction=agent.constants.memory_ef_construction, 
            M=agent.constants.memory_M
        )

    def add(self, text: str) -> None:
        """Add a new text entry to the memory, resizing if necessary."""
        if self.index.get_current_count() + 1 > self.index.get_max_elements():
            self.index.resize_index(self.index.get_max_elements() + agent.constants.memory_capacity_step)

        embedding = ollama.embed(model='nomic-embed-text', input=text)["embeddings"]
        self.index.add_items(embedding)

    add.__tool__ = {
        "name": "add_memory",
        "description": "Add a new text entry to the memory.",
        "parameters": {
            "type": "object",
            "properties": { "text": {"type": "string", "description": "The text entry to add to memory."} },
            "required": ["text"],
        },
    }
    
    def search(self, item: str, top_k: int = 5) -> list[str]:
        """Search for the top_k most similar entries to the given item."""
        labels, _ = self.index.knn_query(item, k=top_k)
        return labels.tolist()
    
    search.__tool__ = {
        "name": "search_memory",
        "description": "Search for the most similar entries in memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "item": {"type": "string", "description": "The text entry to search for."},
                "top_k": {"type": "integer", "description": "The number of similar entries to return.", "default": 5},
            },
            "required": ["item"],
        },
    }

    @staticmethod
    def get_tools() -> types.Tool:
        tool_declarations: list[types.FunctionDeclaration] = [t.__tool__ for t in (getattr(Memory, attr) for attr in dir(Memory)) if hasattr(t, '__tool__')]

        return types.Tool(function_declarations=tool_declarations)
    
    @staticmethod
    def get_associated_tool(func_name: str) -> types.Tool | None:
        """Retrieve the tool metadata associated with a given function name."""
        tool_functions = {t.__tool__["name"]: t for t in (getattr(Memory, attr) for attr in dir(Memory)) if hasattr(t, '__tool__')}
        if func_name in tool_functions:
            return tool_functions[func_name]
        return None

if __name__ == "__main__":
    # print(Memory.get_tools())
    # print(Memory.get_associated_tool("add_memory"))

    memory = Memory()

    memory.search("Hello, how are you?", top_k=3)




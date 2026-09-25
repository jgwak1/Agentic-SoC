from langchain_ollama import ChatOllama

# llm = ChatOllama(model = "qwen2.5:7b")
llm = ChatOllama( model="qwen3:8b", reasoning=True ) 

import os
import json
from typing import AsyncGenerator, List
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core.models import UserMessage
from autogen_ext.models.azure import AzureAIChatCompletionClient
from azure.core.credentials import AzureKeyCredential
from autogen_core.tools import FunctionTool
from autogen_core import CancellationToken
from autogen_core.tool_agent import ToolAgent
from tools.arxiv_search_tool import query_arxiv, query_web
from tools.mcp_tools import (
    list_local_pdfs,
    resolve_user_selection_and_download,
    organize_files_by_mapping
)
from agents.classification_agent import classify_titles_by_prompt
from prompts.prompt_template import LITERATURE_AGENT_PROMPT

load_dotenv()

azure_api_key = os.getenv("GITHUB_TOKEN") 
azure_endpoint = os.getenv("AZURE_INFERENCE_ENDPOINT", "https://models.inference.ai.azure.com") 
model_name = os.getenv("LITERATURE_AGENT_MODEL", "gpt-4o") 

# Azure GitHub Model client
client = AzureAIChatCompletionClient(
    model="gpt-4.1",
    endpoint=azure_endpoint,
    credential=AzureKeyCredential(azure_api_key),
    model_info={
        "json_output": True,
        "function_calling": True,
        "vision": False,
        "family": "unknown",
        "structured_output": True
    },
)

# Wrap all tools
arxiv_tool = FunctionTool(query_arxiv, description="Searches arXiv for research papers.")
web_tool = FunctionTool(query_web, description="Searches the web for relevant academic content.")
list_pdfs_tool = FunctionTool(list_local_pdfs, description="Lists all PDF files in the user's local knowledge base.")
resolve_save_tool = FunctionTool(resolve_user_selection_and_download, description="Saves recommended papers based on user's input like 'save 1st paper' or 'save all'.")
organize_tool = FunctionTool(
    organize_files_by_mapping, 
    name="organize_files_by_mapping", 
    description="Organizes local PDF files into folders based on a formatted string that groups paper titles under classification themes (e.g., by topic, year, or method).")
classify_tool = FunctionTool(
    classify_titles_by_prompt,
    name="classify_titles_by_prompt",
    description="Classifies paper titles using TopicOrganizerAgent based on a user-specified rule."
)

# Define agent
literature_assistant = AssistantAgent(
    name="LiteratureCollectionAgent",
    model_client=client,
    tools=[arxiv_tool, web_tool, list_pdfs_tool, resolve_save_tool, organize_tool, classify_tool],
    system_message=LITERATURE_AGENT_PROMPT,
    reflect_on_tool_use=True,
    model_client_stream=True
)

# Async runner wrapper with proper token streaming
async def run_literature_agent_stream(user_input: str) -> AsyncGenerator[str, None]:
    stream = literature_assistant.on_messages_stream(
        [TextMessage(content=user_input, source="user")],
        cancellation_token=CancellationToken()
    )

    yield "⏳ Thinking..."

     # Track the tools being used
    announced_tools = set()  
    result_shown = False
    
    async for chunk_event in stream:
        # If it's a string (direct content chunk)
        if isinstance(chunk_event, str):
            yield chunk_event
            
        # If it has a content attribute
        elif hasattr(chunk_event, 'content'):
            # Check for tool calls
            if isinstance(chunk_event.content, list):
                for function_call in chunk_event.content:
                    if hasattr(function_call, 'name'):
                        tool_name = function_call.name
                        
                        # Only announce a tool if we haven't announced it yet
                        if tool_name not in announced_tools:
                            announced_tools.add(tool_name)
                            
                            # Announce the tool being used
                            yield f"\n\n🔍 **Using tool: {tool_name}**\n"
                            
                            # Add function arguments display
                            if hasattr(function_call, 'arguments') and function_call.arguments:
                                try:
                                    # Parse the arguments if they're a string containing JSON
                                    if isinstance(function_call.arguments, str):
                                        try:
                                            args_obj = json.loads(function_call.arguments)
                                            if args_obj == {} or not args_obj:
                                                continue
                                            args_formatted = json.dumps(args_obj, indent=2)
                                        except:
                                            args_formatted = json.dumps(function_call.arguments, indent=2)
                                    else:
                                        args_formatted = json.dumps(function_call.arguments, indent=2)
                                    
                                    yield f"\n\n📋 **Tool call arguments:**\n\n```json\n{args_formatted}\n```\n\n"
                                except Exception as e:
                                     yield f"\n\n❌ **Error displaying arguments:** {str(e)}\n\n"
                            else:
                                # Add an extra newline for consistent spacing
                                yield "\n"
                        
            # Handle final response
            elif isinstance(chunk_event.content, str):
                # If we used tools and haven't shown results marker yet
                if announced_tools and not result_shown:
                    yield f"\n\n✅ **Results:**\n\n"
                    result_shown = True
                    
                # Yield the final content
                yield chunk_event.content

from autogen_agentchat.agents import AssistantAgent
from prompts.prompt_template import CLASSIFIER_PROMPT
from autogen_ext.models.azure import AzureAIChatCompletionClient
from autogen_agentchat.messages import TextMessage
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from autogen_core import CancellationToken
import os, json
from typing import List, Dict

load_dotenv()

client = AzureAIChatCompletionClient(
    model="gpt-4o-mini",
    endpoint=os.getenv("AZURE_INFERENCE_ENDPOINT"),
    credential=AzureKeyCredential(os.getenv("GITHUB_TOKEN")),
        model_client_stream=False,
        model_info={
        "json_output": True,
        "function_calling": True,
        "vision": False,
        "family": "unknown",
        "structured_output": True
    }
)

classification_agent = AssistantAgent(
    name="TopicOrganizerAgent",
    model_client=client,
    system_message=CLASSIFIER_PROMPT
)

async def classify_titles_by_criteria(paper_titles: List[str], criteria: str) -> Dict[str, List[str]]:
    prompt = f"""
    Classify the following paper titles by: '{criteria}'.
    Return a JSON object where each key is a group name and the value is a list of paper titles.

    Titles:
    {json.dumps(paper_titles, indent=2)}
    """
    from autogen_core.models import UserMessage
    response = await classification_agent.on_messages([
        TextMessage(content=prompt, source="user")],
        cancellation_token=CancellationToken()
        )
    try:
        return json.loads(response[-1].content)
    except Exception:
        return {"Uncategorized": paper_titles}
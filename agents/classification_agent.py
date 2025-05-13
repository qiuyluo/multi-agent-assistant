from autogen_agentchat.agents import AssistantAgent
from prompts.prompt_template import CLASSIFIER_PROMPT
from autogen_ext.models.azure import AzureAIChatCompletionClient
from autogen_agentchat.messages import TextMessage
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from autogen_core import CancellationToken
import os, json, re
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

async def classify_titles_by_prompt(prompt: str) -> Dict[str, List[str]]:
    try:
        print(f"[🔍 classify_titles_by_prompt] Prompt: {prompt}")
        response = await classification_agent.on_messages(
            [TextMessage(content=prompt, source="user")],
            cancellation_token=CancellationToken()
        )
        content = response.chat_message.content

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            raise ValueError("No JSON object found in response.")

    except Exception as e:
        print(f"[❌ classify_titles_by_prompt parsing failed]: {e}")
        return {"Uncategorized": []}


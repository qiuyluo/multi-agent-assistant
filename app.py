import os
import chainlit as cl
from agents.document_agent import DocumentQAAgent
from prompts.prompt_template import FILE_UPLOAD_MESSAGE
from orchestrator.sk_router_planner import multi_agent_dispatch_stream
from prompts.prompt_template import LITERATURE_AGENT_DESCRIPTION, DOCUMENT_AGENT_DESCRIPTION
import asyncio
from dotenv import load_dotenv
load_dotenv()

SEARCH_AGENT = "search"
DOCUMENT_AGENT = "document"

@cl.set_chat_profiles
async def chat_profiles(current_user: cl.User):
    return [
        cl.ChatProfile(
            name="Search Agent",
            markdown_description=LITERATURE_AGENT_DESCRIPTION,
            icon="https://cdn-icons-png.flaticon.com/512/7641/7641727.png",
        ),
        cl.ChatProfile(
            name="Document Agent",
            markdown_description=DOCUMENT_AGENT_DESCRIPTION,
            icon="https://cdn-icons-png.flaticon.com/512/4725/4725970.png",
        ),
    ]

@cl.on_chat_start
async def start():
    document_qa_agent = DocumentQAAgent()
    cl.user_session.set("history", [])
    cl.user_session.set("active_documents", [])
    
    chat_profile = cl.user_session.get("chat_profile")
    
    if chat_profile == "Search Agent":
        cl.user_session.set("current_agent", SEARCH_AGENT)
    elif chat_profile == "Document Agent":
        cl.user_session.set("current_agent", DOCUMENT_AGENT)
            
        try:
            cl.user_session.set("document_qa_agent", document_qa_agent)
            # Prompt for file upload
            files = await cl.AskFileMessage(
                content=FILE_UPLOAD_MESSAGE,
                accept=["application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
                max_size_mb=50,
                max_files=10,
                timeout=180
            ).send()
            
            if files:
                # Prepare batch of files for processing
                files_to_process = []
                processed_files = []
                file_count = len(files)
                file_text = "file" if file_count == 1 else "files"
                active_docs = cl.user_session.get("active_documents", [])
                
                processing_msg = cl.Message(content=f"Starting to process {file_count} {file_text}...")
                await processing_msg.send()
                
                # Prepare the files list 
                for i, file in enumerate(files):
                    file_extension = file.path.split('.')[-1].lower()
                    file_data = {
                        "path": file.path,
                        "type": file_extension,
                        "name": file.name
                    }
                    files_to_process.append(file_data)
                    active_docs.append(file_data)
                cl.user_session.set("active_documents", active_docs)
                
                # Process files one by one with status updates
                for i, file_data in enumerate(files_to_process):
                    processing_msg.content = f"Processing file {i+1}/{file_count}: {file_data['name']}..."
                    await processing_msg.update()
                    
                    try:
                        # Process individual document
                        chunks = document_qa_agent.process_document(
                            file_data["path"], 
                            file_data["type"], 
                            file_data["name"]
                        )
                        processed_files.append(file_data["name"])
                        processing_msg.content = f"✅ Processed file {i+1}/{file_count}: {file_data['name']} ({chunks} chunks)"
                        await processing_msg.update()
                        await asyncio.sleep(1)  # Small delay so user can see each file being processed
                    
                    except Exception as e:
                        processing_msg.content = f"❌ Failed to process file {i+1}/{file_count}: {file_data['name']} - {str(e)}"
                        await processing_msg.update()
                        await asyncio.sleep(1)
                
                # Final summary
                if len(processed_files) == file_count:
                    processing_msg.content = f"✅ All {file_count} {file_text} processed successfully! What would you like to discover?"
                else:
                    processing_msg.content = f"⚠️ Processed {len(processed_files)}/{file_count} {file_text}. Some files failed processing."
                await processing_msg.update()
                
        except Exception as e:
            await cl.Message(
                content=f"Failed to initialize Document QA Agent: {str(e)}",
                author="System"
            ).send()

@cl.on_message
async def main(message: cl.Message):
    # Get current active agent
    current_agent = cl.user_session.get("current_agent")
    
    history = cl.user_session.get("history")
    history.append(("user", message.content))
    
    if current_agent == SEARCH_AGENT:
        await handle_search_message(message)
    elif current_agent == DOCUMENT_AGENT:
        await handle_document_message(message)

async def handle_search_message(message: cl.Message):
    # Process the user input
    user_input = message.content.strip()
    
    # Initialize message for streaming with "Thinking..."
    msg = cl.Message(content="Thinking...")
    await msg.send()
    
    try:
        full_response = ""
        
        # Stream tokens from the appropriate agent
        async for token in multi_agent_dispatch_stream(user_input):
            if token:
                # Skip the loader token
                if token == "⏳ Thinking...":
                    continue
                
                # For the first real token, update the existing message
                if full_response == "":
                    msg.content = ""
                    await msg.update()
                
                # Add token to full response
                full_response += token
                await msg.stream_token(token)
            
        
        if full_response:
            history = cl.user_session.get("history")
            history.append(("assistant", full_response))
    
    except Exception as e:
        # Handle any errors during streaming
        error_msg = cl.Message(content=f"Sorry, I encountered an error: {str(e)}")
        await error_msg.send()
        print(f"Error: {str(e)}")
        return
    
async def handle_document_message(message: cl.Message):
    user_input = message.content.strip()
    msg = cl.Message(content="Thinking...")
    await msg.send()
    await asyncio.sleep(1) 
    
    try:
        full_response = ""
        
        document_qa_agent = cl.user_session.get("document_qa_agent")
        
        if not document_qa_agent:
            msg.content = "Document QA agent not initialized. Please refresh the page."
            await msg.update()
            return
        
        async for token in document_qa_agent.run_document_agent_stream(user_input):
            if token:
                if full_response == "":
                    msg.content = ""
                    await msg.update()
                
                # Add token to full response
                full_response += token
                await msg.stream_token(token)
        
        if full_response:
            history = cl.user_session.get("history")
            history.append(("assistant", full_response))
    
    except Exception as e:
        # Handle any errors during streaming
        error_msg = cl.Message(content=f"Sorry, I encountered an error: {str(e)}")
        await error_msg.send()
        print(f"Error: {str(e)}")
        return

@cl.on_chat_end
async def end():
    """Clean up resources when the chat ends"""
    document_qa_agent = cl.user_session.get("document_qa_agent")
    if document_qa_agent:
        document_qa_agent.cleanup()
    
    # Remove temporary files
    active_docs = cl.user_session.get("active_documents", [])
    for doc in active_docs:
        try:
            os.remove(doc["path"])
        except:
            pass
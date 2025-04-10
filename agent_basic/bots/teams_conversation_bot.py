import asyncio
from datetime import datetime
import time
import logging

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, CardFactory
from botbuilder.schema import (
    ChannelAccount,
    HeroCard,
    CardAction,
    ActivityTypes,
    Mention,
    ConversationParameters,
    Activity,
    Attachment,
)
from typing import List
from mcp.mcp_client_wrapper import MCPClientWrapper
# In teams_conversation_bot.py
from config import Config

class TeamsConversationBot(ActivityHandler):
    def __init__(self, app_id: str = None):
        self._app_id = app_id
        self.mcp_client = None
        self.logger = logging.getLogger(__name__)

    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text.lower()
        response = MessageFactory.text(f"You said: {text}")

        if "mention me" in text:
            await self._mention_activity(turn_context)
            return

        if "show welcome" in text:
            await self._send_welcome_message(turn_context)
            return

        if "message all members" in text:
            await self._message_all_members(turn_context)
            return
        
        if "initiate routine" in text:
            await self._initiate_routine(turn_context)
            return
            
        # Add new command
        if "initiate mcp routine" in text:
            await self._initiate_mcp_routine(turn_context)
            return

        await turn_context.send_activity(response)

    async def _send_welcome_message(self, turn_context: TurnContext):
        welcome_card = HeroCard(
            title="Welcome to Teams Bot!",
            text="This bot can:\n\n1. Show welcome message\n2. Mention you\n3. Message all members\n4. Initiate routine\n5. Initiate MCP routine",
            buttons=[
                CardAction(
                    type="messageBack",
                    title="Show Welcome",
                    text="show welcome",
                    display_text="Show welcome message",
                ),
                CardAction(
                    type="messageBack",
                    title="Mention Me",
                    text="mention me",
                    display_text="Mention me",
                ),
                CardAction(
                    type="messageBack",
                    title="Message All Members",
                    text="message all members",
                    display_text="Message all members",
                ),
                CardAction(
                    type="messageBack",
                    title="Initiate Routine",
                    text="initiate routine",
                    display_text="Initiate routine",
                ),
                CardAction(
                    type="messageBack",
                    title="Initiate MCP Routine",
                    text="initiate mcp routine",
                    display_text="Initiate MCP routine",
                ),
            ],
        )
        await turn_context.send_activity(
            MessageFactory.attachment(CardFactory.hero_card(welcome_card))
        )

    async def _mention_activity(self, turn_context: TurnContext):
        mention = Mention(
            mentioned=turn_context.activity.from_property,
            text=f"<at>{turn_context.activity.from_property.name}</at>",
            type="mention"
        )

        reply_activity = MessageFactory.text(f"Hello {mention.text}")
        reply_activity.entities = [mention]
        await turn_context.send_activity(reply_activity)

    async def _message_all_members(self, turn_context: TurnContext):
        team_members = await self._get_paged_members(turn_context)

        for member in team_members:
            conversation_reference = TurnContext.get_conversation_reference(
                turn_context.activity
            )

            conversation_parameters = ConversationParameters(
                is_group=False,
                bot=conversation_reference.bot,
                members=[member],
                tenant_id=conversation_reference.conversation.tenant_id,
            )

            async def _send_message(tc1):
                return await tc1.send_activity(
                    f"Hello {member.name}. I'm a Teams conversation bot."
                )

            await turn_context.adapter.create_conversation(
                conversation_reference,
                _send_message,
                conversation_parameters,
            )

        await turn_context.send_activity(
            MessageFactory.text("All messages have been sent")
        )

    async def _get_paged_members(self, turn_context: TurnContext):
        members = []
        continuation_token = None

        while True:
            current_page = await turn_context.turn_state["connectorClient"].conversations.get_conversation_members(
                turn_context.activity.conversation.id
            )
            members.extend(current_page)
            if not continuation_token:
                break

        return members 
    
    async def _initiate_routine(self, turn_context: TurnContext):
        # Send initial card
        card = HeroCard(
            title="Routine Progress",
            text="Starting routine...\n"
        )
        
        # Send initial message and store its activity info for updates
        initial_message = MessageFactory.attachment(CardFactory.hero_card(card))
        sent_activity = await turn_context.send_activity(initial_message)
        
        # Store the complete message log
        message_log = ["Starting routine..."]
        
        # Run the routine
        try:
            for iteration in range(1, 11):  # 10 iterations
                # Sleep for 2 seconds
                await asyncio.sleep(2)
                
                # Update message log
                timestamp = datetime.now().strftime("%H:%M:%S")
                new_message = f"Iteration {iteration} complete at {timestamp}"
                message_log.append(new_message)
                
                # Create updated card with all messages
                updated_card = HeroCard(
                    title="Routine Progress",
                    text="\n".join(message_log)
                )
                
                # Update the existing card
                update_activity = MessageFactory.attachment(CardFactory.hero_card(updated_card))
                update_activity.id = sent_activity.id
                
                # Send the update
                await turn_context.update_activity(update_activity)
                
            # Add completion message
            message_log.append("\nRoutine completed successfully!")
            final_card = HeroCard(
                title="Routine Progress",
                text="\n".join(message_log)
            )
            
            # Send final update
            final_update = MessageFactory.attachment(CardFactory.hero_card(final_card))
            final_update.id = sent_activity.id
            await turn_context.update_activity(final_update)
            
        except Exception as e:
            # Handle any errors
            error_card = HeroCard(
                title="Routine Progress",
                text=f"{'\n'.join(message_log)}\n\nError: Routine interrupted - {str(e)}"
            )
            error_update = MessageFactory.attachment(CardFactory.hero_card(error_card))
            error_update.id = sent_activity.id
            await turn_context.update_activity(error_update)

    async def _initiate_mcp_routine(self, turn_context: TurnContext):
        self.logger.info("=== Starting _initiate_mcp_routine ===")
        
        # Initialize MCP client if not already initialized
        if not self.mcp_client:
            self.logger.info("Creating new MCPClientWrapper instance...")
            self.mcp_client = MCPClientWrapper()
            self.logger.info("Initializing MCP client...")
            init_success = await self.mcp_client.initialize()
            self.logger.debug(f"MCP client initialization result: {init_success}")
            if not init_success:
                self.logger.error("Failed to initialize MCP client")
                await turn_context.send_activity(
                    MessageFactory.text("Failed to initialize MCP client")
                )
                return
        else:
            self.logger.info("Using existing MCP client instance")
            
        # Send initial card
        self.logger.info("Creating initial processing card...")
        card = HeroCard(
            title="�� Agent Processing",
            text="Initializing agent and MCP servers...\n",
            subtitle="Starting query processing"
        )
        
        self.logger.debug("Creating initial activity message")
        initial_message = Activity(
            type=ActivityTypes.message,
            attachments=[CardFactory.hero_card(card)],
            importance="urgent",
            text="Agent Processing Started"
        )

        self.logger.info("Sending initial activity...")
        sent_activity = await turn_context.send_activity(initial_message)
        self.logger.debug(f"Initial activity sent. Activity ID: {sent_activity.id if sent_activity else 'None'}")

        self.logger.debug("Waiting for 10 seconds...")
        time.sleep(10)
        
        try:
            # Get query from config
            self.logger.info("Getting query from config...")
            query = Config.DEFAULT_QUERIES["ascii_sum"]  # Or any other query
            self.logger.debug(f"Selected query: {query}")
            
            # Process query
            self.logger.info(f"Processing query: {query}")
            
            # Update card with query
            self.logger.info("Creating query processing card...")
            query_card = HeroCard(
                title="🤖 Agent Processing",
                subtitle="Query received",
                text=f"Processing query:\n{query}"
            )
            
            self.logger.info("Sending query processing activity...")
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[CardFactory.hero_card(query_card)],
                    importance="urgent",
                    text="Processing Query"
                )
            )
            
            # Process query and get result
            self.logger.info("Calling MCP client process_query...")
            result = await self.mcp_client.process_query(query)
            self.logger.debug(f"Query processing result: {result}")
            
            # Update card with result
            self.logger.info("Creating result card...")
            result_card = HeroCard(
                title="✅ Agent Processing Complete",
                subtitle="Query processed successfully",
                text=f"Query: {query}\n\nResult: {result}\n\nExecution Steps:\n" + 
                     "\n".join([f"- {step['tool']}: {step['result']}" 
                               for step in self.mcp_client.execution_history.steps])
            )
            
            self.logger.info("Sending final result activity...")
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[CardFactory.hero_card(result_card)],
                    importance="urgent",
                    text="Processing Complete"
                )
            )
            self.logger.info("=== Completed _initiate_mcp_routine successfully ===")
            
        except Exception as e:
            self.logger.error("=== Error in _initiate_mcp_routine ===")
            self.logger.error(f"Error type: {type(e).__name__}")
            self.logger.error(f"Error message: {str(e)}")
            self.logger.error("Stack trace:", exc_info=True)
            
            # Error handling
            self.logger.info("Creating error card...")
            error_card = HeroCard(
                title="❌ Agent Processing Error",
                subtitle="An error occurred during processing",
                text=f"Error: {str(e)}"
            )
            
            self.logger.info("Sending error activity...")
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[CardFactory.hero_card(error_card)],
                    importance="urgent",
                    text="Processing Error"
                )
            )
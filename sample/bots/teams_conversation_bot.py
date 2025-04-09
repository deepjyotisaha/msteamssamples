import asyncio
from datetime import datetime

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

class TeamsConversationBot(ActivityHandler):
    def __init__(self, app_id: str = None):
        self._app_id = app_id

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
        
        # Add new command handler
        if "initiate routine" in text:
            await self._initiate_routine(turn_context)
            return

        await turn_context.send_activity(response)

    async def _send_welcome_message(self, turn_context: TurnContext):
        welcome_card = HeroCard(
            title="Welcome to Teams Bot!",
            text="This bot can:\n\n1. Show welcome message\n2. Mention you\n3. Message all members",
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
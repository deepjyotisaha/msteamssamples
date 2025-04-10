#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import traceback
import logging
from datetime import datetime
from http import HTTPStatus
from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
)
from botbuilder.schema import Activity, ActivityTypes
from bots.teams_conversation_bot import TeamsConversationBot
from config import DefaultConfig  # or Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(funcName)20s() %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Print startup message
print("Starting Teams Bot Application...")
logger.info("Initializing bot configuration...")

CONFIG = DefaultConfig()
logger.info(f"App ID: {CONFIG.APP_ID}")
logger.info(f"Port: {CONFIG.PORT}")

SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)
BOT = TeamsConversationBot()

# Catch-all for errors
async def on_error(context: TurnContext, error: Exception):
    logger.error(f"\n [on_turn_error]: {error}")
    logger.error(traceback.format_exc())
    await context.send_activity("The bot encountered an error or bug.")

ADAPTER.on_turn_error = on_error

async def messages(req: Request) -> Response:
    logger.info("Received incoming message request")
    
    # Log headers for debugging
    logger.info(f"Request headers: {req.headers}")
    
    if "application/json" not in req.headers["Content-Type"]:
        logger.error("Invalid content type received")
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    try:
        body = await req.json()
        logger.info(f"Received message body: {body}")
        
        activity = Activity().deserialize(body)
        auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""
        logger.info(f"Processing activity type: {activity.type}")

        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        if response:
            logger.info(f"Sending response: {response.body}")
            return json_response(data=response.body, status=response.status)
        
        logger.info("No response to send")
        return Response(status=HTTPStatus.OK)
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

APP = web.Application()
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        logger.info(f"Starting web server on port {CONFIG.PORT}")
        print(f"Bot is running on http://localhost:{CONFIG.PORT}")
        web.run_app(APP, host="localhost", port=CONFIG.PORT)
    except Exception as error:
        logger.error(f"Error starting server: {str(error)}")
        logger.error(traceback.format_exc())
        raise error 
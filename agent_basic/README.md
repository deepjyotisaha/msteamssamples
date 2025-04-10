# Microsoft Teams Conversation Bot

This sample app demonstrates how to create a Microsoft Teams bot using Python and the Bot Framework. The bot showcases various conversation capabilities including welcome messages, user mentions, and team member messaging.

## Features

- **Welcome Message**: Interactive card with bot capabilities
- **User Mention**: Ability to mention users in conversations
- **Team Messaging**: Send messages to all team members
- **Message Echo**: Basic message response functionality

## Prerequisites

- [Python 3.6+](https://www.python.org/downloads/)
- [Microsoft Teams](https://www.microsoft.com/en-us/microsoft-teams/download-app)
- [ngrok](https://ngrok.com/) or equivalent tunneling solution
- [Bot Framework Emulator](https://github.com/microsoft/botframework-emulator) (optional)
- [Azure subscription](https://azure.microsoft.com/en-us/free/) (for bot registration)

## Setup Instructions

### Step 1: Update Azure Configuration
1. Create an `.env` file in the root directory and add:
   ```plaintext
   MicrosoftAppId=<your-bot-app-id>
   MicrosoftAppPassword=<your-bot-app-password>
   ```
2. Go to [Azure Portal](https://portal.azure.com) to get your credentials
3. **Note**: The password should be the value of the secret, not the secret ID

### Step 2: Set up ngrok
1. Start ngrok server:
   ```bash
   ngrok http 3978 --host-header="localhost:3978"
   ```
2. Copy the "https" URL from ngrok output
3. Update the messaging endpoint in Azure Portal with:
   ```
   https://<your-ngrok-url>/api/messages
   ```

### Step 3: Python Environment Setup
1. Create the environment (first time only):
   ```bash
   python -m venv env
   ```

2. Activate the virtual environment:
   ```bash
   # On Windows:
   .\env\Scripts\activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the server application:
   ```bash
   python app.py
   ```

5. When finished, deactivate the environment:
   ```bash
   deactivate
   ```

### Step 4: Teams Integration
1. Update the manifest:
   - Navigate to `appManifest/manifest.json`
   - Update with your bot's App ID
   - Package the manifest into a zip file

2. Install in Teams:
   - Open Microsoft Teams
   - Click on "Apps" in the left sidebar
   - Select "Upload a custom app"
   - Choose your manifest.zip file

## Bot Commands

- **Show Welcome**: Displays the welcome card with available commands
- **Mention Me**: Bot will mention you in the conversation
- **Message All Members**: Bot will send a message to all team members

## Source Reference

This sample code is based on the [Microsoft Teams Samples repository](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/bot-conversation/python)

## License

This project is licensed under the MIT License - see the LICENSE file for details. 